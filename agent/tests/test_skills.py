import re
from pathlib import Path

import yaml

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def test_frontmatter_contract():
    files = sorted(SKILLS.glob("*/SKILL.md"))
    assert len(files) >= 4
    for f in files:
        text = f.read_text()
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        assert match, f
        meta = yaml.safe_load(match.group(1))
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", meta["name"])
        assert meta["name"] == f.parent.name
        assert 20 <= len(meta["description"]) <= 300
