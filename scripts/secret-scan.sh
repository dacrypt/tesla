#!/bin/sh
# Requires the pinned development tool; never print scanner findings.
set -eu
umask 077

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

ref=
artifacts=
if [ "$#" -gt 0 ]; then
    [ "$#" -eq 2 ] || fail 'Usage: secret-scan.sh [--ref OBJECT_ID | --artifacts DIRECTORY]'
    case "$1" in
        --ref)
            ref=$2
            case "$ref" in
                ''|*[!0-9a-fA-F]*) fail 'Invalid object ID.' ;;
            esac
            [ "${#ref}" -eq 40 ] || [ "${#ref}" -eq 64 ] || fail 'Invalid object ID.'
            ;;
        --artifacts)
            artifacts=$(cd -- "$2" 2>/dev/null && pwd -P) || fail 'Artifact directory does not exist.'
            ;;
        *) fail 'Usage: secret-scan.sh [--ref OBJECT_ID | --artifacts DIRECTORY]' ;;
    esac
fi

root=$(git rev-parse --show-toplevel 2>/dev/null) || fail 'Run the scanner inside a Git checkout.'
config=$root/.gitleaks.toml
[ -f "$config" ] || fail 'Missing repository secret-scanning configuration.'
scanner=${GITLEAKS_BIN:-gitleaks}
command -v "$scanner" >/dev/null 2>&1 || fail 'Gitleaks 8.30.1 is required; install the pinned tool or set GITLEAKS_BIN.'
version=$("$scanner" version 2>/dev/null) || fail 'Cannot run Gitleaks.'
[ "$version" = '8.30.1' ] || fail 'Gitleaks 8.30.1 is required.'

scratch=$(mktemp -d) || fail 'Cannot create a private scan directory.'
trap 'rm -rf "$scratch"' EXIT HUP INT TERM
mkdir "$scratch/tree"
: > "$scratch/empty-ignore"

scan() {
    if ! "$scanner" "$@" --config "$config" --redact=100 --ignore-gitleaks-allow \
        --gitleaks-ignore-path "$scratch/empty-ignore" --no-banner --log-level error \
        --max-archive-depth 3 --max-decode-depth 5 >/dev/null 2>&1; then
        fail 'Secret scan blocked: sensitive data detected or the scanner failed. Review privately before publishing.'
    fi
}

scan_tree() {
    scan dir "$1"
    # Export ZIP/TAR members recursively by content: wheels, including nested or
    # renamed wheels, are otherwise missed. Ambiguous/unsafe archives fail closed.
    exported=$(mktemp -d "$scratch/archives.XXXXXX") || fail 'Cannot create a private archive directory.'
    if ! python3 - "$1" "$exported" <<'PY'
import io
import itertools
import stat
import sys
import tarfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

source, target = map(Path, sys.argv[1:])
archive_ids = itertools.count()
total_bytes = 0
total_members = 0
MAX_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 100000
MAX_DEPTH = 5
archive_extensions = (".whl", ".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")

def export(data, name, depth=1):
    global total_bytes, total_members
    if len(data) > MAX_BYTES:
        raise ValueError("Archive exceeds inspection limits")
    if zipfile.is_zipfile(io.BytesIO(data)):
        archive = zipfile.ZipFile(io.BytesIO(data))
        is_zip = True
    else:
        try:
            archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
        except tarfile.TarError:
            if name.lower().endswith(archive_extensions):
                raise ValueError("Archive cannot be inspected") from None
            return
        is_zip = False
    if depth > MAX_DEPTH:
        archive.close()
        raise ValueError("Nested archive exceeds inspection depth")
    destination_root = target / str(next(archive_ids))
    seen = set()
    with archive:
        for member in archive.infolist() if is_zip else archive:
            total_members += 1
            if total_members > MAX_MEMBERS:
                raise ValueError("Archive exceeds member limits")
            path = PurePosixPath(member.filename if is_zip else member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe archive member")
            normalized = unicodedata.normalize("NFC", path.as_posix()).casefold()
            if normalized in seen:
                raise ValueError("Duplicate normalized archive member")
            seen.add(normalized)
            if is_zip:
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Archive symlink requires separate inspection")
                directory, size = member.is_dir(), member.file_size
            else:
                if not member.isdir() and not member.isfile():
                    raise ValueError("Archive links/devices require separate inspection")
                directory, size = member.isdir(), member.size
            if directory:
                continue
            remaining = MAX_BYTES - total_bytes
            if size > remaining:
                raise ValueError("Archive exceeds inspection limits")
            reader = archive.open(member) if is_zip else archive.extractfile(member)
            with reader:
                content = reader.read(remaining + 1)
            total_bytes += len(content)
            if total_bytes > MAX_BYTES:
                raise ValueError("Archive exceeds inspection limits")
            destination = destination_root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            export(content, path.as_posix(), depth + 1)

try:
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("Archive symlink requires separate inspection")
        if path.is_file():
            with path.open("rb") as reader:
                data = reader.read(MAX_BYTES + 1)
            export(data, path.name)
except Exception:
    sys.exit(1)
PY
    then
        fail 'Cannot safely inspect archives: invalid members or inspection limits exceeded.'
    fi
    scan dir "$exported"
}

if [ -n "$artifacts" ]; then
    scan_tree "$artifacts"
else
    commit=
    if [ -n "$ref" ]; then
        commit=$(git rev-parse --verify "$ref^{commit}" 2>/dev/null) || fail 'Published refs must resolve to an existing commit.'
        scan git "$root" "--log-opts=--text $commit"
    else
        scan git "$root" '--log-opts=--all --text'
    fi
    # Diff scanning omits commit/tag messages. Also export the exact ref tree
    # for hooks, or tracked working files (including ignored ones) for CI/dev.
    # Symlinks are scanned as text and are never followed outside the checkout.
    if ! python3 - "$root" "$scratch" "$ref" "$commit" <<'PY'
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

root, scratch = map(Path, sys.argv[1:3])
ref, commit = sys.argv[3:]
target = scratch / "tree"

def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)

def destination(raw):
    relative = Path(os.fsdecode(raw))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid tracked path")
    result = target / relative
    result.parent.mkdir(parents=True, exist_ok=True)
    return relative, result

try:
    metadata = scratch / "metadata"
    metadata.mkdir()
    with (metadata / "messages.txt").open("wb") as messages:
        messages.write(git("log", "--format=%B", commit or "--all"))
        tags = [ref.encode()] if ref else git("for-each-ref", "--format=%(objectname)", "refs/tags").splitlines()
        for tag in tags:
            oid = tag.decode("ascii")
            while git("cat-file", "-t", oid).strip() == b"tag":
                content = git("cat-file", "tag", oid)
                messages.write(b"\n" + content)
                match = re.match(rb"object ([0-9a-f]{40}|[0-9a-f]{64})\n", content)
                if not match:
                    raise ValueError("Invalid tag object")
                oid = match.group(1).decode("ascii")
    # Inspect every reachable blob by content. rev-list may give a reused blob
    # its latest filename, hiding an older archive extension behind a .bin name.
    archives = scratch / "history-archives"
    archives.mkdir()
    objects = git("rev-list", "--objects", "--no-object-names", commit or "--all").splitlines()
    with subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as batch:
        for index, oid in enumerate(objects):
            batch.stdin.write(oid + b"\n")
            batch.stdin.flush()
            header = batch.stdout.readline().split()
            if len(header) != 3:
                raise ValueError("Cannot inspect a reachable object")
            size = int(header[2])
            if size > 256 * 1024 * 1024:
                raise ValueError("Reachable object exceeds inspection limits")
            content = batch.stdout.read(size)
            if len(content) != size or batch.stdout.read(1) != b"\n":
                raise ValueError("Incomplete reachable object")
            if header[1] != b"blob":
                continue
            suffix = ".zip" if zipfile.is_zipfile(io.BytesIO(content)) else None
            if suffix is None:
                try:
                    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*"):
                        if content.startswith(b"\x1f\x8b"):
                            suffix = ".tar.gz"
                        elif content.startswith(b"BZh"):
                            suffix = ".tar.bz2"
                        elif content.startswith(b"\xfd7zXZ\x00"):
                            suffix = ".tar.xz"
                        else:
                            suffix = ".tar"
                except tarfile.TarError:
                    pass
            if suffix:
                (archives / (str(index) + suffix)).write_bytes(content)
        batch.stdin.close()
        if batch.wait() != 0:
            raise ValueError("Reachable object inspection failed")
    if commit:
        for record in git("ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
            if not record:
                continue
            header, raw = record.split(b"\t", 1)
            _, kind, oid = header.split()
            if kind != b"blob":
                raise ValueError("Submodules require a separate scan")
            _, exported = destination(raw)
            exported.write_bytes(git("cat-file", "blob", oid.decode("ascii")))
    else:
        for raw in git("ls-files", "-z").split(b"\0"):
            if not raw:
                continue
            relative, exported = destination(raw)
            source = root / relative
            if not source.exists() and not source.is_symlink():
                continue
            if source.is_symlink():
                exported.write_text(os.readlink(source))
            elif source.is_file():
                shutil.copyfile(source, exported)
            else:
                raise ValueError("Tracked directory requires a separate scan")
except Exception:
    sys.exit(1)
PY
    then
        fail 'Cannot safely export Git metadata and tracked files for scanning.'
    fi
    scan dir "$scratch/metadata"
    scan_tree "$scratch/history-archives"
    scan_tree "$scratch/tree"
fi
printf '%s\n' 'Secret scan passed.'
