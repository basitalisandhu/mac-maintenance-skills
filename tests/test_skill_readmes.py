"""Every skill has a README.md whose sample is the real output of its command on the demo home. The comparison
with a fresh run is macOS-only: sizes come from the file system's block counts, which differ on Linux."""

from __future__ import annotations

import importlib.util
import sys

import pytest
from conftest import ROOT, SKILLS


def load():
    spec = importlib.util.spec_from_file_location("skill_readmes", ROOT / "scripts" / "skill_readmes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_skill_has_a_readme_with_a_sample():
    for skill_md in SKILLS.glob("*/SKILL.md"):
        text = (skill_md.parent / "README.md").read_text(encoding="utf-8")
        assert "<!-- sample-output: start -->" in text and "## Try it" in text, skill_md.parent.name


@pytest.mark.skipif(sys.platform != "darwin", reason="sizes depend on the file system's block size")
def test_readme_samples_match_a_fresh_run(capsys):
    assert load().main(["--check"]) == 0, capsys.readouterr().err
