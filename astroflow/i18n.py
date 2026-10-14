"""Messages in the user's language. The source text is Chinese (the app's first language) and is its own key, as with
gettext: other languages look it up in astroflow/locales/<lang>.py and fall back to the Chinese.

    tr("缺少暗场：{need}", need="300 s")          # the message, placeholders filled in
    tr("{n} 帧", n=3)                             # an English plural: the catalog entry is ("{n} frame", "{n} frames")
    mark("宽带星云")                              # a message translated later (tr(value) where it is shown)

The language is the setting preferences.language: "zh", "en", or "auto" (the system's: the desktop app passes it in
ASTROFLOW_SYSTEM_LANG, else Python's locale). tests/test_i18n.py checks that every Chinese string in the code goes
through tr() or mark() and has an English entry.
"""
import locale
import os

from . import settings

LANGUAGES = ("zh", "en")


def normalize(value):
    """'zh-CN', 'zh-Hans-CN', 'Chinese (Simplified)_China' -> 'zh'; any other language -> 'en'; '' / 'auto' -> None."""
    v = str(value or "").strip().lower()
    if not v or v == "auto":
        return None
    return "zh" if v.startswith(("zh", "chinese")) else "en"


def system_language():
    return normalize(os.environ.get("ASTROFLOW_SYSTEM_LANG")) or normalize(locale.getlocale()[0]) or "en"


def language():
    """The language messages are written in: the setting, else the system's."""
    return normalize(settings.get().preferences.get("language")) or system_language()


def mark(text):
    """A message to translate where it is shown (tr(value)); marks it for the catalog check."""
    return text


def tr(text, **values):
    """`text` in the user's language with {placeholders} filled in from `values`."""
    out = text
    if language() == "en":
        from .locales import en
        entry = en.MESSAGES.get(text)
        if isinstance(entry, tuple):
            entry = entry[0] if values.get("n") == 1 else entry[1]
        out = entry or text
    return out.format(**values) if values else out
