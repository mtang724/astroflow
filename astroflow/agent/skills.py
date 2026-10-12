"""Skills: distilled processing know-how the agent loads on demand (progressive disclosure, same layout as Claude
Agent Skills so both can use them):

    skills/<name>/SKILL.md          YAML-ish front matter (name, description) + instructions
    skills/<name>/references/*.md   details the instructions point to

Only the index (name + description) goes into the system prompt; the agent calls `load_skill` when a task matches
and `read_skill_file` for a reference. Works with any model that can call tools.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from .. import config

_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


@dataclass
class Skill:
    name: str
    description: str
    path: Path

    @property
    def body(self):
        return _split(self.path.read_text(encoding="utf-8"))[1]

    def files(self):
        return sorted(p.relative_to(self.path.parent).as_posix() for p in self.path.parent.rglob("*")
                      if p.is_file() and p.name != "SKILL.md")


def _split(text):
    m = _FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, m.group(2)


def discover(root=None):
    root = Path(root) if root else config.SKILLS
    out = []
    for f in sorted(root.glob("*/SKILL.md")):
        meta, _ = _split(f.read_text(encoding="utf-8"))
        out.append(Skill(meta.get("name") or f.parent.name, meta.get("description", ""), f))
    return out


def index_text(skills):
    return "\n".join(f"- {s.name}: {s.description}" for s in skills)


def find(name, root=None):
    for s in discover(root):
        if s.name == name:
            return s
    raise KeyError(f"no skill named {name!r} (have: {', '.join(s.name for s in discover(root))})")


def read_file(name, relpath, root=None):
    s = find(name, root)
    base = s.path.parent.resolve()
    p = (base / relpath).resolve()
    if base not in p.parents:
        raise ValueError("path must stay inside the skill folder")
    return p.read_text(encoding="utf-8")
