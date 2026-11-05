#!/usr/bin/env python3
"""CodeLens: turn an AI-generated Python project into a map a human can read (zero dependencies).
Usage:
  python codelens.py map   <project_dir> [-o CODELENS.md] [--lang auto|zh|en]
  python codelens.py trace <project_dir> <function> [-d 3] [--lang auto|zh|en]
"""
import ast, os, argparse, subprocess, collections

__version__ = "0.2.1"
SKIP = {".git", "venv", ".venv", "node_modules", "__pycache__", "build", "dist"}

STRINGS = {
    "zh": {
        "title": "# CodeLens 项目地图",
        "summary": "模块 {m} 个 / 函数 {f} 个 / 疑点 {i} 处",
        "h_entry": "## 1. 从哪里读起(入口)",
        "entry_main": "含 `__main__` 入口",
        "entry_deco": "第{line}行 — 装饰器 {decos}",
        "h_deps": "## 2. 模块职责与依赖",
        "th_deps": "| 模块 | 行数 | 依赖 | 被依赖 | 说明 |",
        "no_doc": "(无文档,需补)",
        "h_hot": "## 3. 高风险热点(先看这些)",
        "th_hot": "| 函数 | 位置 | 复杂度 | 行数 | 被调用 |",
        "h_smell": "## 4. 疑点清单(AI常见坑)",
        "h_dup": "### 同名函数(可能是AI重复实现了同一功能)",
        "h_churn": "## 5. 最常被改动的文件(出bug概率高)",
        "commits": "{n} 次提交",
        "smell_swallow": "吞掉异常(except 后什么都不做),bug会被隐藏",
        "smell_stub": "空实现函数 {name}()(AI常见的'搭了架子没写内容')",
        "smell_todo": "遗留标记: {text}",
        "smell_parse": "无法解析: {err}",
        "trace_head": "复杂度={cc}",
        "trace_up": "【谁调用了它(上游,找触发路径)】",
        "trace_down": "【它调用了谁(下游,找出错点)】",
        "not_found": "未找到函数 {name}",
        "generated": "已生成 {path}",
    },
    "en": {
        "title": "# CodeLens Project Map",
        "summary": "{m} modules / {f} functions / {i} findings",
        "h_entry": "## 1. Where to start reading (entry points)",
        "entry_main": "has a `__main__` entry",
        "entry_deco": "line {line} — decorators {decos}",
        "h_deps": "## 2. Modules and dependencies",
        "th_deps": "| Module | Lines | Imports | Imported by | Description |",
        "no_doc": "(no docstring, please add one)",
        "h_hot": "## 3. Hotspots (read these first)",
        "th_hot": "| Function | Location | Complexity | Lines | Callers |",
        "h_smell": "## 4. Findings (common AI-code smells)",
        "h_dup": "### Same-named functions (possible duplicate implementations)",
        "h_churn": "## 5. Most frequently changed files (bug-prone)",
        "commits": "{n} commits",
        "smell_swallow": "swallowed exception (an `except` that does nothing hides bugs)",
        "smell_stub": "empty stub function {name}() (scaffolding with no implementation)",
        "smell_todo": "leftover marker: {text}",
        "smell_parse": "cannot parse: {err}",
        "trace_head": "complexity={cc}",
        "trace_up": "[Upstream: who calls it, to find the trigger path]",
        "trace_down": "[Downstream: what it calls, to find the fault]",
        "not_found": "function not found: {name}",
        "generated": "generated {path}",
    },
}
LANG = "en"

def detect_lang():
    env = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower()
    return "zh" if env.startswith("zh") else "en"

def t(key, **kw):
    table = STRINGS.get(LANG, STRINGS["en"])
    return table.get(key, STRINGS["en"][key]).format(**kw)

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
            issues.append((m, 0, t("smell_parse", err=e))); continue
        mods[m] = {"path": p, "doc": ast.get_docstring(tree) or "", "lines": src.count("\n") + 1, "entry": False}
        for i, line in enumerate(src.splitlines(), 1):
            if any(("# " + k) in line or ("#" + k) in line for k in ("TODO", "FIXME", "XXX", "placeholder", "Placeholder")):
                issues.append((m, i, t("smell_todo", text=line.strip()[:70])))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    r = resolve(names, a.name)
                    if r and r != m: imports[m].add(r)
            elif isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    r = resolve(names, n.module + "." + a.name) or resolve(names, n.module)
                    if r and r != m: imports[m].add(r)
            elif isinstance(n, ast.If) and "__main__" in ast.dump(n.test):
                mods[m]["entry"] = True
            elif isinstance(n, ast.ExceptHandler):
                if n.type is None or (isinstance(n.type, ast.Name) and n.type.id == "Exception"):
                    if all(isinstance(b, (ast.Pass, ast.Continue)) for b in n.body):
                        issues.append((m, n.lineno, t("smell_swallow")))
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = {call_name(c) for c in ast.walk(n) if isinstance(c, ast.Call)} - {None}
                decos = [ast.unparse(d) for d in n.decorator_list]
                key = f"{m}.{n.name}"
                funcs[key] = dict(mod=m, name=n.name, line=n.lineno, end=n.end_lineno,
                                  cc=complexity(n), calls=calls, doc=(ast.get_docstring(n) or "").split("\n")[0],
                                  decos=decos, stub=is_stub(n), params=len(n.args.args))
                if is_stub(n) and not any("abstract" in d for d in decos):
                    issues.append((m, n.lineno, t("smell_stub", name=n.name)))
    by_name = collections.defaultdict(list)
    for k, f in funcs.items(): by_name[f["name"]].append(k)
    callers = collections.defaultdict(set); callees = collections.defaultdict(set)
    for k, f in funcs.items():
        for c in f["calls"]:
            for tgt in by_name.get(c, []):
                if tgt != k: callees[k].add(tgt); callers[tgt].add(k)
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
    L.append(t("title") + "\n\n" + t("summary", m=len(a["mods"]), f=len(F), i=len(a["issues"])) + "\n")
    L.append(t("h_entry") + "\n")
    for m, i in a["mods"].items():
        if i["entry"]: L.append(f"- `{m}` ({i['path']}) — {t('entry_main')}")
    for k, f in F.items():
        if any(x in d for d in f["decos"] for x in ("route", "get(", "post(", "command", "task")):
            L.append(f"- `{k}` " + t("entry_deco", line=f["line"], decos=f["decos"]))
    L.append("\n" + t("h_deps") + "\n\n" + t("th_deps") + "\n|---|---|---|---|---|")
    rev = collections.defaultdict(set)
    for m, ds in a["imports"].items():
        for d in ds: rev[d].add(m)
    for m, i in sorted(a["mods"].items()):
        desc = i["doc"].splitlines()[0] if i["doc"] else t("no_doc")
        L.append(f"| {m} | {i['lines']} | {len(a['imports'].get(m, []))} | {len(rev[m])} | {desc} |")
    L.append("\n```mermaid\ngraph LR")
    for m, ds in sorted(a["imports"].items()):
        for d in sorted(ds): L.append(f"  {m.replace('.', '_')}[{m}] --> {d.replace('.', '_')}[{d}]")
    L.append("```\n\n" + t("h_hot") + "\n")
    hot = sorted(F.items(), key=lambda kv: -(kv[1]["cc"] * 2 + (kv[1]["end"] - kv[1]["line"]) / 10 + len(a["callers"][kv[0]])))[:10]
    L.append(t("th_hot") + "\n|---|---|---|---|---|")
    for k, f in hot:
        L.append(f"| {k} | {a['mods'][f['mod']]['path']}:{f['line']} | {f['cc']} | {f['end']-f['line']+1} | {len(a['callers'][k])} |")
    L.append("\n" + t("h_smell") + "\n")
    for m, ln, msg in a["issues"][:40]: L.append(f"- `{m}:{ln}` {msg}")
    if a["dup"]:
        L.append("\n" + t("h_dup") + "\n")
        for n, v in list(a["dup"].items())[:15]: L.append(f"- `{n}`: " + ", ".join(v))
    ch = churn(root)
    if ch:
        L.append("\n" + t("h_churn") + "\n")
        for f, n in ch: L.append(f"- {f} — {t('commits', n=n)}")
    return "\n".join(L)

def trace(root, name, depth=3):
    a = analyze(root)
    keys = [k for k in a["funcs"] if a["funcs"][k]["name"] == name or k == name]
    if not keys: print(t("not_found", name=name)); return
    def tree(k, rel, d, seen, pre=""):
        for n in sorted(rel[k]):
            f = a["funcs"][n]
            print(f"{pre}└─ {n} ({a['mods'][f['mod']]['path']}:{f['line']}) {f['doc']}")
            if d > 1 and n not in seen: tree(n, rel, d - 1, seen | {n}, pre + "   ")
    for k in keys:
        f = a["funcs"][k]
        print(f"\n== {k} ({a['mods'][f['mod']]['path']}:{f['line']}-{f['end']}) {t('trace_head', cc=f['cc'])} ==")
        print(t("trace_up")); tree(k, a["callers"], depth, {k})
        print(t("trace_down")); tree(k, a["callees"], depth, {k})

def main(argv=None):
    global LANG
    ap = argparse.ArgumentParser(prog="codelens")
    ap.add_argument("--version", action="version", version=f"codelens {__version__}")
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("map", "trace"):
        s = sp.add_parser(name)
        s.add_argument("root")
        s.add_argument("--lang", choices=["auto", "zh", "en"], default="auto")
        if name == "map": s.add_argument("-o", default="CODELENS.md")
        else:
            s.add_argument("func"); s.add_argument("-d", type=int, default=3)
    x = ap.parse_args(argv)
    LANG = detect_lang() if x.lang == "auto" else x.lang
    if x.cmd == "map":
        open(x.o, "w", encoding="utf-8").write(report(x.root)); print(t("generated", path=x.o))
    else:
        trace(x.root, x.func, x.d)

if __name__ == "__main__":
    main()
