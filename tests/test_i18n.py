"""Languages: every message the user can see goes through the catalogs, and each has its English text."""
import ast
import json
import re
import string
from pathlib import Path

import pytest

from astroflow import i18n, organize, settings, share
from astroflow.locales import en

ROOT = Path(__file__).resolve().parent.parent
CJK = re.compile(r"[一-鿿]")
# Chinese text that is not for the user: prompts the LLM reads, the tutorial-video tool, command-line examples.
EXEMPT_MODULES = {"astroflow/video.py", "astroflow/darks.py", "astroflow/__main__.py", "astroflow/agent/run.py",
                  "astroflow/i18n.py", "astroflow/locales/en.py"}
EXEMPT_NAMES = {"astroflow/agent/session.py": {"ROLE", "PRINCIPLES", "system_prompt", "target_section", "user_message",
                                               "prompted_tools_text"},
                "astroflow/agent/tools.py": {"VISION_SYSTEM", "look"},
                "astroflow/share.py": {"CHINESE_NAMES"}}
UI = ROOT / "desktop" / "src" / "renderer" / "src"


def _placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def _python_messages():
    """{message: [file:line]} of every tr() / mark() call in the backend, and the Chinese strings outside them."""
    messages, stray = {}, []
    for path in sorted((ROOT / "astroflow").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            up = parents.get(node)
            if isinstance(up, ast.Call) and getattr(up.func, "id", None) in ("tr", "mark") and up.args[0] is node:
                messages.setdefault(node.value, []).append(f"{rel}:{node.lineno}")
                continue
            if not CJK.search(node.value):
                continue
            if rel in EXEMPT_MODULES or isinstance(up, ast.Expr):               # docstrings
                continue
            names = set()
            while up is not None:
                if isinstance(up, (ast.FunctionDef, ast.ClassDef)):
                    names.add(up.name)
                elif isinstance(up, ast.Assign):
                    names |= {t.id for t in up.targets if isinstance(t, ast.Name)}
                up = parents.get(up)
            if not names & EXEMPT_NAMES.get(rel, set()):
                stray.append(f"{rel}:{node.lineno} {node.value[:40]!r}")
    return messages, stray


def test_every_backend_message_has_english():
    messages, stray = _python_messages()
    assert not stray, "Chinese text the user may see must go through tr() or mark():\n" + "\n".join(stray)
    missing = [f"{m!r} ({where[0]})" for m, where in messages.items() if m not in en.MESSAGES]
    assert not missing, "no English for:\n" + "\n".join(missing)
    for source, target in en.MESSAGES.items():
        for text in target if isinstance(target, tuple) else (target,):
            assert _placeholders(text) == _placeholders(source), f"placeholders differ: {source!r} -> {text!r}"
    unused = set(en.MESSAGES) - set(messages)
    assert not unused, f"English messages no longer used: {sorted(unused)}"


def _ui_messages():
    """Messages of the desktop app: tr('...') and mark('...') literals, and Chinese text outside them."""
    literal = re.compile(r"""\b(?:tr|mark)\(\s*'((?:[^'\\]|\\.)*)'""")
    messages, stray = {}, []
    for path in sorted(p for p in UI.rglob("*") if p.suffix in (".ts", ".tsx") and p.name not in ("schema.d.ts", "i18n.ts")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in literal.finditer(line):
                messages.setdefault(m.group(1).replace("\\'", "'"), []).append(f"{path.name}:{n}")
            if CJK.search(literal.sub("", line)):
                stray.append(f"{path.relative_to(UI).as_posix()}:{n} {line.strip()[:60]}")
    return messages, stray


def test_every_ui_message_has_english():
    catalog = json.loads((UI / "locales" / "en.json").read_text(encoding="utf-8"))
    messages, stray = _ui_messages()
    assert not stray, "Chinese text in the app must go through tr('...') or mark('...'):\n" + "\n".join(stray)
    missing = [f"{m!r} ({where[0]})" for m, where in messages.items() if m not in catalog]
    assert not missing, "no English for:\n" + "\n".join(missing)
    for source, target in catalog.items():
        for text in target if isinstance(target, list) else [target]:
            assert set(re.findall(r"\{(\w+)\}", text)) == set(re.findall(r"\{(\w+)\}", source)), source
    unused = set(catalog) - set(messages)
    assert not unused, f"English messages no longer used: {sorted(unused)}"


def test_language_follows_the_setting_and_the_system(monkeypatch):
    assert [i18n.normalize(v) for v in ("zh-CN", "zh-Hans-CN", "Chinese (Simplified)_China", "en-US", "de", "auto", "")] \
        == ["zh", "zh", "zh", "en", "en", None, None]
    s = settings.get()
    s.preferences["language"] = "auto"
    monkeypatch.setenv("ASTROFLOW_SYSTEM_LANG", "en-GB")
    assert i18n.language() == "en"
    monkeypatch.setenv("ASTROFLOW_SYSTEM_LANG", "zh-Hans-CN")
    assert i18n.language() == "zh"
    s.preferences["language"] = "en"
    assert i18n.language() == "en"
    assert i18n.tr("跳过了 {n} 张 ASIAIR 预览图（Preview_*）", n=1) == "Skipped 1 ASIAIR preview (Preview_*)"
    assert i18n.tr("跳过了 {n} 张 ASIAIR 预览图（Preview_*）", n=3) == "Skipped 3 ASIAIR previews (Preview_*)"
    assert i18n.tr("一段没有翻译的话") == "一段没有翻译的话"                    # falls back to the Chinese


@pytest.fixture
def english():
    s = settings.get()
    s.preferences["language"] = "en"
    return s


def test_messages_come_in_english(english, tmp_settings, monkeypatch):
    from astroflow import doctor, pi
    monkeypatch.setattr(doctor, "read_pi_settings", lambda: None)            # this computer's PixInsight aside
    monkeypatch.setattr(doctor, "find_pixinsight", list)
    monkeypatch.setattr(pi, "running_instances", list)
    tmp, _ = tmp_settings
    english.astro_root = (tmp / "Astro").as_posix()
    settings.save(english)
    _, notes = organize.build_plan(sources=[tmp / "nothing"])
    assert notes == ["No usable images found (FITS or camera RAW files)"]
    text = json.dumps(doctor.run(), ensure_ascii=False)
    assert not CJK.search(text), "Chinese left in the English setup check"
    cap = share.suggest(tmp / "M8", {"exposures_s": {300.0: 11}, "total_h": 0.92, "camera": "ZWO ASI2600MC"},
                        ["2026May17", "2026May20"])
    assert cap[0] == "M8 Lagoon Nebula" and "(55 min)" in cap[1] and cap[2] == "2026-05-17 to 2026-05-20 (2 nights)"
