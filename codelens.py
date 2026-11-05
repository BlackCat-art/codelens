#!/usr/bin/env python3
"""CodeLens: 帮人类读懂 AI 生成的 Python 项目(零依赖)。
用法:
  python codelens.py map  <项目目录> [-o CODELENS.md]   # 生成项目地图报告
  python codelens.py trace <项目目录> <函数名>          # 查看某函数的上游/下游调用链(定位bug用)
"""
import ast, sys, os, argparse, subprocess, collections

SKIP = {".git", "venv", ".venv", "node_modules", "__pycache__", "build", "dist"}

def py_files(root):
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            if f.endswith(".py"):
                yield os.path.join(d, f)

def modname(root, path):
    rel = os.path.relpath(path, root)[:-3].replace(os.sep, ".")
    return rel[:-9] if rel.endswith(".__init__") else rel

def complexity(fn):
    n = 1
    for x in ast.walk(fn):
        if isinstance(x, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With,
                          ast.IfExp, ast.Assert, ast.comprehension)):
            n += 1
        elif isinstance(x, ast.BoolOp):
            n += len(x.values) - 1
    return n

def call_name(c):
    f = c.func
    if isinstance(f, ast.Name): return f.id
    if isinstance(f, ast.Attribute): return f.attr
    return None

def is_stub(fn):
    body = [b for b in fn.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant))]
    if not body: return True
    if len(body) == 1:
        b = body[0]
        if isinstance(b, ast.Pass): return True
        if isinstance(b, ast.Raise) and "NotImplemented" in ast.dump(b): return True
    return False

def resolve(names, dotted):
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in names: return cand
    return None

def analyze(root):
    funcs, mods, imports, issues = {}, {}, collections.defaultdict(set), []
    names = {modname(root, p) for p in py_files(root)}
    for p in py_files(root):
        m = modname(root, p)
        try:
            src = open(p, encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception as e:
            issues.append((m, 0, f"无法解析: {e}")); continue
        mods[m] = {"path": p, "doc": ast.get_docstring(tree) or "", "lines": src.count("\n") + 1, "entry": False}
        for i, line in enumerate(src.splitlines(), 1):
            if any(("# " + t) in line or ("#" + t) in line for t in ("TODO", "FIXME", "XXX", "placeholder", "Placeholder")):
                issues.append((m, i, "遗留标记: " + line.strip()[:70]))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    t = resolve(names, a.name)
                    if t and t != m: imports[m].add(t)
            elif isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    t = resolve(names, n.module + "." + a.name) or resolve(names, n.module)
                    if t and t != m: imports[m].add(t)
            elif isinstance(n, ast.If) and "__main__" in ast.dump(n.test):
                mods[m]["entry"] = True
            elif isinstance(n, ast.ExceptHandler):
                if n.type is None or (isinstance(n.type, ast.Name) and n.type.id == "Exception"):
                    if all(isinstance(b, (ast.Pass, ast.Continue)) for b in n.body):
                        issues.append((m, n.lineno, "吞掉异常(except 后什么都不做),bug会被隐藏"))
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = {call_name(c) for c in ast.walk(n) if isinstance(c, ast.Call)} - {None}
                decos = [ast.unparse(d) for d in n.decorator_list]
                key = f"{m}.{n.name}"
                funcs[key] = dict(mod=m, name=n.name, line=n.lineno, end=n.end_lineno,
                                  cc=complexity(n), calls=calls, doc=(ast.get_docstring(n) or "").split("\n")[0],
                                  decos=decos, stub=is_stub(n), params=len(n.args.args))
                if is_stub(n) and not any("abstract" in d for d in decos):
                    issues.append((m, n.lineno, f"空实现函数 {n.name}()(AI常见的'搭了架子没写内容')"))
    by_name = collections.defaultdict(list)
    for k, f in funcs.items(): by_name[f["name"]].append(k)
    callers = collections.defaultdict(set); callees = collections.defaultdict(set)
    for k, f in funcs.items():
        for c in f["calls"]:
            for t in by_name.get(c, []):
                if t != k: callees[k].add(t); callers[t].add(k)
    dup = {n: v for n, v in by_name.items() if len(v) > 1 and not n.startswith("__") and n not in ("main", "run")}
    return dict(funcs=funcs, mods=mods, imports=imports, issues=issues, callers=callers, callees=callees, dup=dup)

def churn(root):
    try:
        out = subprocess.run(["git", "-C", root, "log", "--name-only", "--pretty=format:", "-n", "300"],
                             capture_output=True, text=True, timeout=15).stdout
        return collections.Counter(l for l in out.splitlines() if l.endswith(".py")).most_common(8)
    except Exception:
        return []

def report(root):
    a = analyze(root); F = a["funcs"]; L = []
    L.append(f"# CodeLens 项目地图\n\n模块 {len(a['mods'])} 个 / 函数 {len(F)} 个 / 疑点 {len(a['issues'])} 处\n")
    L.append("## 1. 从哪里读起(入口)\n")
    for m, i in a["mods"].items():
        if i["entry"]: L.append(f"- `{m}` ({i['path']}) — 含 `__main__` 入口")
    for k, f in F.items():
        if any(x in d for d in f["decos"] for x in ("route", "get(", "post(", "command", "task")):
            L.append(f"- `{k}` 第{f['line']}行 — 装饰器 {f['decos']}")
    L.append("\n## 2. 模块职责与依赖\n\n| 模块 | 行数 | 依赖 | 被依赖 | 说明 |\n|---|---|---|---|---|")
    rev = collections.defaultdict(set)
    for m, ds in a["imports"].items():
        for d in ds: rev[d].add(m)
    for m, i in sorted(a["mods"].items()):
        L.append(f"| {m} | {i['lines']} | {len(a['imports'].get(m, []))} | {len(rev[m])} | {i['doc'].splitlines()[0] if i['doc'] else '(无文档,需补)'} |")
    L.append("\n```mermaid\ngraph LR")
    for m, ds in sorted(a["imports"].items()):
        for d in sorted(ds): L.append(f"  {m.replace('.', '_')}[{m}] --> {d.replace('.', '_')}[{d}]")
    L.append("```\n\n## 3. 高风险热点(先看这些)\n")
    hot = sorted(F.items(), key=lambda kv: -(kv[1]["cc"] * 2 + (kv[1]["end"] - kv[1]["line"]) / 10 + len(a["callers"][kv[0]])))[:10]
    L.append("| 函数 | 位置 | 复杂度 | 行数 | 被调用 |\n|---|---|---|---|---|")
    for k, f in hot:
        L.append(f"| {k} | {a['mods'][f['mod']]['path']}:{f['line']} | {f['cc']} | {f['end']-f['line']+1} | {len(a['callers'][k])} |")
    L.append("\n## 4. 疑点清单(AI常见坑)\n")
    for m, ln, msg in a["issues"][:40]: L.append(f"- `{m}:{ln}` {msg}")
    if a["dup"]:
        L.append("\n### 同名函数(可能是AI重复实现了同一功能)\n")
        for n, v in list(a["dup"].items())[:15]: L.append(f"- `{n}`: " + ", ".join(v))
    ch = churn(root)
    if ch:
        L.append("\n## 5. 最常被改动的文件(出bug概率高)\n")
        for f, n in ch: L.append(f"- {f} — {n} 次提交")
    return "\n".join(L)

def trace(root, name, depth=3):
    a = analyze(root)
    keys = [k for k in a["funcs"] if a["funcs"][k]["name"] == name or k == name]
    if not keys: print("未找到函数", name); return
    def tree(k, rel, d, seen, pre=""):
        for n in sorted(rel[k]):
            f = a["funcs"][n]
            print(f"{pre}└─ {n} ({a['mods'][f['mod']]['path']}:{f['line']}) {f['doc']}")
            if d > 1 and n not in seen: tree(n, rel, d - 1, seen | {n}, pre + "   ")
    for k in keys:
        f = a["funcs"][k]
        print(f"\n== {k} ({a['mods'][f['mod']]['path']}:{f['line']}-{f['end']}) 复杂度={f['cc']} ==")
        print("【谁调用了它(上游,找触发路径)】"); tree(k, a["callers"], depth, {k})
        print("【它调用了谁(下游,找出错点)】"); tree(k, a["callees"], depth, {k})

if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="codelens")
    sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("map"); m.add_argument("root"); m.add_argument("-o", default="CODELENS.md")
    t = sp.add_parser("trace"); t.add_argument("root"); t.add_argument("func"); t.add_argument("-d", type=int, default=3)
    x = ap.parse_args()
    if x.cmd == "map":
        open(x.o, "w", encoding="utf-8").write(report(x.root)); print("已生成", x.o)
    else:
        trace(x.root, x.func, x.d)
