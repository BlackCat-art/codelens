import importlib.util
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(HERE, "codelens.py")
DEMO = os.path.join(HERE, "examples", "demo")
CJK = re.compile(r"[\u4e00-\u9fff]")

spec = importlib.util.spec_from_file_location("codelens", CL)
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)


def run(*args, lc_all=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if lc_all:
        env["LC_ALL"] = lc_all
    return subprocess.run([sys.executable, CL, *args], capture_output=True, text=True,
                          encoding="utf-8", cwd=DEMO, env=env)


def report(tmp_path, lang):
    out = tmp_path / f"{lang}.md"
    r = run("map", ".", "-o", str(out), "--lang", lang)
    assert r.returncode == 0, r.stderr
    return out.read_text(encoding="utf-8")


def test_keys_match():
    assert set(cl.STRINGS["zh"]) == set(cl.STRINGS["en"])


def test_placeholders_match():
    names = lambda s: sorted(re.findall(r"\{(\w+)\}", s))
    for k in cl.STRINGS["zh"]:
        assert names(cl.STRINGS["zh"][k]) == names(cl.STRINGS["en"][k]), k


def test_en_report_has_no_cjk(tmp_path):
    assert not CJK.search(report(tmp_path, "en"))


def test_zh_report_is_chinese(tmp_path):
    s = report(tmp_path, "zh")
    assert "项目地图" in s and "吞掉异常" in s


def test_same_findings_both_langs(tmp_path):
    loc = lambda s: re.findall(r"^- `([\w.]+:\d+)`", s, re.M)
    en, zh = loc(report(tmp_path, "en")), loc(report(tmp_path, "zh"))
    assert en == zh and len(en) == 5


def test_dependency_edges(tmp_path):
    s = report(tmp_path, "en")
    assert "shop_app[shop.app] --> shop_services_orders[shop.services.orders]" in s
    assert "shop_services_orders[shop.services.orders] --> shop_services_pricing[shop.services.pricing]" in s


def test_trace_langs():
    en = run("trace", ".", "check_stock", "--lang", "en").stdout
    zh = run("trace", ".", "check_stock", "--lang", "zh").stdout
    assert "Upstream" in en and "shop.app.main" in en and "complexity=2" in en and not CJK.search(en)
    assert "上游" in zh and "shop.app.main" in zh and "复杂度=2" in zh


def test_auto_lang_from_env():
    assert "上游" in run("trace", ".", "check_stock", lc_all="zh_CN.UTF-8").stdout
    assert "Upstream" in run("trace", ".", "check_stock", lc_all="en_US.UTF-8").stdout


def test_not_found():
    assert "not found" in run("trace", ".", "nope", "--lang", "en").stdout


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def test_version_flag_matches_module():
    r = run("--version")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"codelens {cl.__version__}"


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", cl.__version__)


def test_pyproject_version_is_dynamic():
    text = read("pyproject.toml")
    assert 'dynamic = ["version"]' in text
    assert not re.search(r"^version\s*=\s*[\"']", text, re.M)


def test_readme_pins_current_version():
    for name in ("README.md", "README.zh.md"):
        assert f"@v{cl.__version__}" in read(name), name
