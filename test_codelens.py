import re, subprocess, sys, os, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("codelens", os.path.join(here, "codelens.py"))
cl = importlib.util.module_from_spec(spec); spec.loader.exec_module(cl)
demo = os.path.join(here, "examples", "demo")
CJK = re.compile(r"[\u4e00-\u9fff]")

def run(*args):
    return subprocess.run([sys.executable, os.path.join(here, "codelens.py"), *args], capture_output=True, text=True, cwd=demo)

def test_keys_match():
    assert set(cl.STRINGS["zh"]) == set(cl.STRINGS["en"])

def test_placeholders_match():
    f = lambda s: sorted(re.findall(r"\{(\w+)\}", s))
    for k in cl.STRINGS["zh"]:
        assert f(cl.STRINGS["zh"][k]) == f(cl.STRINGS["en"][k]), k

def test_en_report_has_no_cjk():
    r = run("map", ".", "-o", "/tmp/en.md", "--lang", "en"); assert r.returncode == 0, r.stderr
    assert not CJK.search(open("/tmp/en.md", encoding="utf-8").read())

def test_zh_report_is_chinese():
    run("map", ".", "-o", "/tmp/zh.md", "--lang", "zh")
    s = open("/tmp/zh.md", encoding="utf-8").read()
    assert "项目地图" in s and "吞掉异常" in s

def test_same_findings_both_langs():
    run("map", ".", "-o", "/tmp/en.md", "--lang", "en"); run("map", ".", "-o", "/tmp/zh.md", "--lang", "zh")
    loc = lambda p: re.findall(r"^- `([\w.]+:\d+)`", open(p, encoding="utf-8").read(), re.M)
    assert loc("/tmp/en.md") == loc("/tmp/zh.md") and len(loc("/tmp/en.md")) == 5

def test_dependency_edges():
    run("map", ".", "-o", "/tmp/en.md", "--lang", "en")
    s = open("/tmp/en.md", encoding="utf-8").read()
    assert "shop_app[shop.app] --> shop_services_orders[shop.services.orders]" in s
    assert "shop_services_orders[shop.services.orders] --> shop_services_pricing[shop.services.pricing]" in s

def test_trace_langs():
    en = run("trace", ".", "check_stock", "--lang", "en").stdout
    zh = run("trace", ".", "check_stock", "--lang", "zh").stdout
    assert "Upstream" in en and "shop.app.main" in en and not CJK.search(en)
    assert "上游" in zh and "shop.app.main" in zh

def test_auto_lang_from_env():
    for loc, word in (("zh_CN.UTF-8", "上游"), ("en_US.UTF-8", "Upstream")):
        env = dict(os.environ, LC_ALL=loc)
        r = subprocess.run([sys.executable, os.path.join(here, "codelens.py"), "trace", ".", "check_stock"],
                           capture_output=True, text=True, cwd=demo, env=env)
        assert word in r.stdout

def test_not_found():
    assert "not found" in run("trace", ".", "nope", "--lang", "en").stdout
