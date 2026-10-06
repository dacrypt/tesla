"""Exercise publication guards in isolated repositories using synthetic markers."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tarfile
import uuid
import warnings
import zipfile
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SCANNER = os.environ.get("GITLEAKS_BIN") or shutil.which("gitleaks")
REQUIRES_SCANNER = pytest.mark.skipif(not SCANNER, reason="Set GITLEAKS_BIN to Gitleaks 8.30.1")
ZERO = "0" * 40
CONFIG = r"""
[extend]
useDefault = true

[[rules]]
id = "synthetic-test-marker"
regex = '''SYNTHETIC_[A-Z0-9]{24}'''

[[rules]]
id = "synthetic-test-vin"
regex = '''\b(?:5YJ|7SA)[A-HJ-NPR-Z0-9]{14}\b'''

[[rules]]
id = "synthetic-test-reservation"
regex = '''\bRN[0-9]{9}\b'''
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, "Isolated Git setup failed"
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "--initial-branch=main")
    git(tmp_path, "config", "user.name", "Synthetic Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    for relative in ("scripts/secret-scan.sh", ".githooks/pre-push"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / relative, destination)
        destination.chmod(0o755)
    (tmp_path / ".gitleaks.toml").write_text(CONFIG)
    (tmp_path / "sample.txt").write_text("Safe initial content\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "Create isolated synthetic fixture")
    return tmp_path


def marker() -> str:
    return "SYNTHETIC_" + uuid.uuid4().hex[:24].upper()


def run_guard(repo: Path, *args: str, refs: str | None = None, scanner: str | None = None):
    env = os.environ.copy()
    env["GITLEAKS_BIN"] = scanner or SCANNER or str(repo / "missing-scanner")
    executable = ".githooks/pre-push" if refs is not None else "scripts/secret-scan.sh"
    return subprocess.run(
        [str(repo / executable), *args],
        cwd=repo,
        env=env,
        input=refs,
        capture_output=True,
        text=True,
    )


def assert_private(result, sensitive: str):
    if sensitive in result.stdout or sensitive in result.stderr:
        pytest.fail("Guard disclosed a synthetic sensitive value", pytrace=False)


@REQUIRES_SCANNER
def test_clean_repository_passes(repo):
    assert run_guard(repo).returncode == 0


def test_missing_scanner_blocks_publication(repo):
    result = run_guard(repo, scanner=str(repo / "absent-gitleaks"))
    assert result.returncode != 0


@REQUIRES_SCANNER
def test_intermediate_secret_cannot_be_hidden_by_removal(repo):
    sensitive = marker()
    (repo / "sample.txt").write_text(sensitive + " # gitleaks:allow\n")
    git(repo, "add", "sample.txt")
    git(repo, "commit", "-m", "Add synthetic marker")
    (repo / "sample.txt").write_text("Marker removed\n")
    git(repo, "commit", "-am", "Remove synthetic marker")
    result = run_guard(repo)
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
def test_current_tracked_ignored_file_is_scanned(repo):
    git(repo, "commit", "--allow-empty", "-m", "Ensure history is clean")
    (repo / ".gitignore").write_text("sample.txt\n")
    sensitive = marker()
    (repo / "sample.txt").write_text(sensitive)
    result = run_guard(repo)
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("personal_type", ["vin", "reservation"])
def test_current_personal_data_blocks(repo, personal_type):
    sensitive = "5YJ" + "A" * 14 if personal_type == "vin" else "RN" + "9" * 9
    (repo / "sample.txt").write_text(sensitive)
    result = run_guard(repo)
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("tag", [False, True])
def test_hook_scans_complete_history_of_new_branch_or_tag(repo, tag):
    sensitive = marker()
    (repo / "sample.txt").write_text(sensitive)
    git(repo, "commit", "-am", "Add synthetic marker")
    (repo / "sample.txt").write_text("Safe tip\n")
    git(repo, "commit", "-am", "Remove synthetic marker")
    if tag:
        git(repo, "tag", "-a", "synthetic-tag", "-m", "Synthetic annotated tag")
        local_ref = "refs/tags/synthetic-tag"
    else:
        local_ref = "refs/heads/main"
    oid = git(repo, "rev-parse", local_ref)
    result = run_guard(repo, refs=f"{local_ref} {oid} {local_ref} {ZERO}\n")
    assert result.returncode != 0
    assert_private(result, sensitive)


def test_deletion_only_push_needs_no_scanner(repo):
    oid = git(repo, "rev-parse", "HEAD")
    result = run_guard(
        repo,
        refs=f"(delete) {ZERO} refs/heads/obsolete {oid}\n",
        scanner=str(repo / "absent-gitleaks"),
    )
    assert result.returncode == 0


def test_hook_rejects_invalid_object_without_executing_it(repo):
    sentinel = repo / "injected"
    result = run_guard(
        repo, refs=f"refs/heads/main $(touch${{IFS}}{sentinel}) refs/heads/main {ZERO}\n"
    )
    assert result.returncode != 0
    assert not sentinel.exists()


@REQUIRES_SCANNER
def test_history_in_another_branch_is_scanned(repo):
    git(repo, "checkout", "-b", "secondary")
    sensitive = marker()
    (repo / "sample.txt").write_text(sensitive)
    git(repo, "commit", "-am", "Add synthetic marker to secondary ref")
    git(repo, "checkout", "main")
    result = run_guard(repo)
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("leak", [False, True])
@pytest.mark.parametrize("wheel", [False, True])
def test_distribution_archive_is_scanned(repo, leak, wheel):
    sensitive = marker()
    source = repo / "synthetic-private.txt"
    source.write_text(sensitive if leak else "Safe distribution contents\n")
    artifacts = repo / "dist"
    artifacts.mkdir()
    if wheel:
        with zipfile.ZipFile(artifacts / "package.whl", "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(source, arcname="sample.txt")
    else:
        with tarfile.open(artifacts / "package.tar.gz", "w:gz") as archive:
            archive.add(source, arcname="sample.txt")
    source.unlink()
    result = run_guard(repo, "--artifacts", str(artifacts))
    assert result.returncode == (1 if leak else 0)
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("tag", [False, True])
def test_commit_and_annotated_tag_messages_block(repo, tag):
    sensitive = marker()
    if tag:
        git(repo, "tag", "-a", "synthetic-message", "-m", sensitive)
        ref = "refs/tags/synthetic-message"
    else:
        git(repo, "commit", "--allow-empty", "-m", sensitive)
        ref = "refs/heads/main"
    oid = git(repo, "rev-parse", ref)
    result = run_guard(repo, refs=f"{ref} {oid} {ref} {ZERO}\n")
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
def test_binary_diff_and_exact_ref_snapshot_are_scanned(repo):
    sensitive = marker()
    (repo / ".gitattributes").write_text("sample.txt binary\n")
    (repo / "sample.txt").write_bytes(b"\x00" + sensitive.encode() + b"\x00")
    git(repo, "add", ".gitattributes", "sample.txt")
    git(repo, "commit", "-m", "Add synthetic binary fixture")
    oid = git(repo, "rev-parse", "HEAD")
    (repo / "sample.txt").write_text("Safe working tree that differs from the pushed ref\n")
    result = run_guard(repo, refs=f"refs/heads/main {oid} refs/heads/main {ZERO}\n")
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("kind", ["telegram", "vin", "vin-new-wmi", "reservation", "fixture"])
def test_real_repository_policy(repo, kind):
    shutil.copyfile(PROJECT / ".gitleaks.toml", repo / ".gitleaks.toml")
    git(repo, "add", ".gitleaks.toml")
    git(repo, "commit", "-m", "Use the real repository scanning policy")
    if kind == "telegram":
        sensitive = "1234567890" + ":" + "A" * 35
    elif kind == "vin":
        sensitive = "5YJ" + "A" * 14
    elif kind == "vin-new-wmi":
        sensitive = "7SA" + "A" * 14
    elif kind == "reservation":
        sensitive = "RN" + "8" * 9
    else:
        # Audited, explicitly allowed test data in the repository's policy.
        sensitive = "5YJ3E1EA1PF000001" + " RN123456789"
    (repo / "sample.txt").write_text(sensitive)
    result = run_guard(repo)
    assert result.returncode == (0 if kind == "fixture" else 1)
    assert_private(result, sensitive)


@REQUIRES_SCANNER
def test_removed_wheel_in_intermediate_commit_blocks_the_hook(repo):
    sensitive = marker()
    archive = repo / "synthetic.whl"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as wheel:
        wheel.writestr("sample.txt", sensitive)
    git(repo, "add", "synthetic.whl")
    git(repo, "commit", "-m", "Add synthetic compressed fixture")
    git(repo, "rm", "synthetic.whl")
    git(repo, "commit", "-m", "Remove synthetic compressed fixture")
    oid = git(repo, "rev-parse", "HEAD")
    result = run_guard(repo, refs=f"refs/heads/main {oid} refs/heads/main {ZERO}\n")
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("tag", [False, True])
def test_clean_branch_and_annotated_tag_pass_the_hook(repo, tag):
    if tag:
        git(repo, "tag", "-a", "safe-tag", "-m", "Safe annotated tag")
        ref = "refs/tags/safe-tag"
    else:
        ref = "refs/heads/main"
    oid = git(repo, "rev-parse", ref)
    result = run_guard(repo, refs=f"{ref} {oid} {ref} {ZERO}\n")
    assert result.returncode == 0


@REQUIRES_SCANNER
def test_wheel_cannot_write_an_absolute_archive_path(repo):
    escaped = repo / "escaped"
    artifacts = repo / "dist"
    artifacts.mkdir()
    with zipfile.ZipFile(artifacts / "unsafe.whl", "w") as archive:
        archive.writestr(str(escaped), "Safe synthetic archive content")
    result = run_guard(repo, "--artifacts", str(artifacts))
    assert result.returncode != 0
    assert not escaped.exists()


@REQUIRES_SCANNER
@pytest.mark.parametrize(
    ("first_path", "second_path"),
    [
        ("sample.txt", "sample.txt"),
        ("sample.txt", "./sample.txt"),
        ("sample.txt", "SAMPLE.txt"),
        ("caf\u00e9.txt", "cafe\u0301.txt"),
    ],
)
def test_duplicate_normalized_wheel_members_cannot_hide_a_secret(repo, first_path, second_path):
    sensitive = marker()
    artifacts = repo / "dist"
    artifacts.mkdir()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(artifacts / "duplicate.whl", "w", zipfile.ZIP_DEFLATED) as wheel:
            wheel.writestr(first_path, sensitive)
            wheel.writestr(second_path, "Safe replacement that must not hide the first entry")
    result = run_guard(repo, "--artifacts", str(artifacts))
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("leak", [False, True])
def test_uppercase_wheel_extension_is_scanned(repo, leak):
    sensitive = marker()
    artifacts = repo / "dist"
    artifacts.mkdir()
    with zipfile.ZipFile(artifacts / "package.WHL", "w", zipfile.ZIP_DEFLATED) as wheel:
        wheel.writestr("sample.txt", sensitive if leak else "Safe uppercase wheel")
    result = run_guard(repo, "--artifacts", str(artifacts))
    assert result.returncode == (1 if leak else 0)
    assert_private(result, sensitive)


@REQUIRES_SCANNER
@pytest.mark.parametrize("tar", [False, True])
@pytest.mark.parametrize("leak", [False, True])
def test_wheel_nested_in_zip_or_tar_is_scanned(repo, tar, leak):
    sensitive = marker()
    wheel_bytes = io.BytesIO()
    with zipfile.ZipFile(wheel_bytes, "w", zipfile.ZIP_DEFLATED) as wheel:
        wheel.writestr("sample.txt", sensitive if leak else "Safe nested wheel")
    artifacts = repo / "dist"
    artifacts.mkdir()
    if tar:
        with tarfile.open(artifacts / "outer.tar.gz", "w:gz") as archive:
            member = tarfile.TarInfo("inner.WHL")
            member.size = len(wheel_bytes.getvalue())
            archive.addfile(member, io.BytesIO(wheel_bytes.getvalue()))
    else:
        with zipfile.ZipFile(artifacts / "outer.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("inner.WHL", wheel_bytes.getvalue())
    result = run_guard(repo, "--artifacts", str(artifacts))
    assert result.returncode == (1 if leak else 0)
    assert_private(result, sensitive)


@REQUIRES_SCANNER
def test_reused_historical_wheel_blob_with_bin_name_still_blocks(repo):
    sensitive = marker()
    wheel = repo / "sample.WHL"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sample.txt", sensitive)
    content = wheel.read_bytes()
    git(repo, "add", "sample.WHL")
    git(repo, "commit", "-m", "Add synthetic uppercase archive")
    git(repo, "rm", "sample.WHL")
    git(repo, "commit", "-m", "Remove synthetic archive")
    (repo / "sample.bin").write_bytes(content)
    git(repo, "add", "sample.bin")
    git(repo, "commit", "-m", "Reuse synthetic archive with a different name")
    git(repo, "rm", "sample.bin")
    git(repo, "commit", "-m", "Remove reused synthetic archive from the safe tip")
    oid = git(repo, "rev-parse", "HEAD")
    result = run_guard(repo, refs=f"refs/heads/main {oid} refs/heads/main {ZERO}\n")
    assert result.returncode != 0
    assert_private(result, sensitive)


@REQUIRES_SCANNER
def test_nested_archives_beyond_inspection_limit_fail_closed(repo):
    content = b"Safe synthetic nested content"
    for _ in range(7):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("inner.whl", content)
        content = archive_bytes.getvalue()
    artifacts = repo / "dist"
    artifacts.mkdir()
    (artifacts / "deep.zip").write_bytes(content)
    result = run_guard(repo, "--artifacts", str(artifacts))
    assert result.returncode != 0
