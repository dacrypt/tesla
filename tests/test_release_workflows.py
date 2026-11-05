"""Release-on-merge wiring: release.yml tags and dispatches publish.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _load(name):
    data = yaml.safe_load((WF / name).read_text())
    # PyYAML parses the bare `on:` key as boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def test_release_runs_on_main_and_dispatches_publish():
    rel = _load("release.yml")
    assert rel["on"]["push"]["branches"] == ["main"]
    tag = rel["jobs"]["tag"]
    assert tag["needs"] == ["detect", "verify"]
    assert tag["permissions"] == {"contents": "write", "actions": "write"}
    steps = " ".join(s.get("run", "") for s in tag["steps"])
    assert 'gh workflow run publish.yml --ref "$TAG"' in steps
    assert "git push origin" in steps


def test_publish_accepts_dispatch_and_guards_tag_ref():
    pub = _load("publish.yml")
    assert "workflow_dispatch" in pub["on"]
    assert pub["on"]["push"]["tags"] == ["v*"]
    verify = " ".join(s.get("run", "") for s in pub["jobs"]["verify"]["steps"])
    assert "refs/tags/v*" in verify
    assert pub["jobs"]["build-and-publish"]["environment"]["name"] == "pypi"
    assert pub["jobs"]["github-release"]["needs"] == ["build-and-publish", "docker"]


def test_release_requires_changelog_section_and_untagged_version():
    detect = " ".join(s.get("run", "") for s in _load("release.yml")["jobs"]["detect"]["steps"])
    assert "refs/tags/v$v" in detect
    assert "CHANGELOG.md" in detect
