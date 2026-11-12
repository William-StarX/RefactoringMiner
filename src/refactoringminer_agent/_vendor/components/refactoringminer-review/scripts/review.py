#!/usr/bin/env python3
"""Collect bounded, immutable Java change snapshots and real RefactoringMiner evidence."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import time

from reporting import render_result

COMPONENT = "refactoringminer-review"
SKILL_DIR = Path(__file__).resolve().parents[1]
IGNORE_DIRS = {".git", ".hg", ".svn", "target", "build", "node_modules", ".gradle", ".idea"}
LIMITATIONS = [
    "Refactoring and AST edit evidence is not proof of behavior preservation or absence of defects.",
    "The engine analyzes changed UTF-8 Java source snapshots; it does not build or run the target project.",
    "AST action locations and refactoring ranges are not a complete node mapping or an exact semantic diff.",
    "Textual diff includes refactoring edits; do not subtract refactoring ranges and assume the rest is all behavior change.",
]


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def runtime_module():
    import runtime
    return runtime


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def git(repo: Path, args: list[str], *, limit: int = 16_000_000, timeout: int = 30, input: bytes | None = None) -> bytes:
    """Never run a target build, custom diff driver, checkout, hook, or remote operation."""
    # An inherited GIT_DIR/GIT_WORK_TREE must not redirect the explicit --repo.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    command = ["git", "-c", "core.fsmonitor=false", "--literal-pathspecs", "-C", str(repo), *args]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        completed = subprocess.run(command, input=input, stdout=out, stderr=err, env=env, timeout=timeout)
        if completed.returncode:
            err.seek(0)
            message = err.read(4000).decode("utf-8", "replace").strip()
            raise RuntimeError("Git read failed: " + message)
        size = out.tell()
        if size > limit:
            raise RuntimeError(f"Git output exceeds the {limit}-byte read limit")
        out.seek(0)
        return out.read()


def resolve_commit(repo: Path, value: str) -> str:
    return git(repo, ["rev-parse", "--verify", "--end-of-options", value + "^{commit}"]).decode().strip()


def safe_relative(name: str) -> PurePosixPath:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise RuntimeError(f"Unsupported or unsafe repository path: {name!r}")
    if not relative.parts or ".git" in relative.parts:
        raise RuntimeError(f"Unsupported repository path: {name!r}")
    return relative


def read_local(root: Path, name: str, limit: int) -> tuple[bytes | None, str | None]:
    relative = safe_relative(name)
    path = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return None, "symlink omitted"
    try:
        before = path.stat()
    except FileNotFoundError:
        return None, None
    if not stat.S_ISREG(before.st_mode):
        return None, "non-regular file omitted"
    if before.st_size > limit:
        return None, f"file exceeds {limit} bytes"
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    after = path.stat()
    if len(data) > limit:
        return None, f"file exceeds {limit} bytes"
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise RuntimeError(f"File changed while being captured: {name}")
    return data, None


def tree_entries(repo: Path, sha: str, paths: list[str]) -> dict[str, tuple[str, str, str, int | None]]:
    if not paths:
        return {}
    data = git(repo, ["ls-tree", "-r", "-l", "-z", sha, "--", *paths])
    result = {}
    for record in data.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, kind, oid, size = header.decode("ascii").split()
        name = raw_path.decode("utf-8", "strict")
        result[name] = (mode, kind, oid, None if size == "-" else int(size))
    return result


class GitBlobs:
    """Batch immutable objects, keeping only one bounded batch in memory per side."""

    def __init__(self, repo: Path, entries: dict, limit: int):
        self.repo, self.entries, self.limit = repo, entries, limit
        self.sizes, self.groups, self.group_for = {}, [], {}
        self.loaded_group, self.loaded = None, {}
        self.sizes = {oid: size for mode, kind, oid, size in entries.values()
                      if kind == "blob" and mode in {"100644", "100755"}}
        group, used = [], 0
        for oid, size in self.sizes.items():
            if size is None or size < 0:
                raise RuntimeError("Unavailable Git blob size: " + oid)
            if size > limit:
                continue
            if group and (len(group) >= 32 or used + size > 4_000_000):
                self.groups.append(group)
                group, used = [], 0
            self.group_for[oid] = len(self.groups)
            group.append(oid)
            used += size
        if group:
            self.groups.append(group)

    def __call__(self, name: str) -> tuple[bytes | None, str | None]:
        entry = self.entries.get(name)
        if entry is None:
            return None, None
        mode, kind, oid, _ = entry
        if kind != "blob" or mode not in {"100644", "100755"}:
            return None, "symlink or submodule omitted"
        if self.sizes[oid] > self.limit:
            return None, f"file exceeds {self.limit} bytes"
        index = self.group_for[oid]
        if index != self.loaded_group:
            group = self.groups[index]
            data = git(self.repo, ["cat-file", "--batch"],
                       input=("\n".join(group) + "\n").encode("ascii"),
                       limit=sum(self.sizes[item] + 128 for item in group))
            stream, loaded = io.BytesIO(data), {}
            for item in group:
                header = stream.readline().decode("ascii").split()
                size = self.sizes[item]
                if header != [item, "blob", str(size)]:
                    raise RuntimeError("Unexpected Git batch header")
                loaded[item] = stream.read(size)
                if len(loaded[item]) != size or stream.read(1) != b"\n":
                    raise RuntimeError("Incomplete Git batch content")
            self.loaded_group, self.loaded = index, loaded
        return self.loaded[oid], None


def directory_paths(root: Path, limit: int, warnings: list[str]) -> set[str]:
    paths: set[str] = set()
    for current, directories, files in os.walk(root, followlinks=False):
        parent = Path(current)
        kept = []
        for name in sorted(directories):
            if name in IGNORE_DIRS:
                continue
            path = parent / name
            if path.is_symlink():
                warnings.append(f"Directory symlink omitted: {path.relative_to(root).as_posix()}")
            else:
                kept.append(name)
        directories[:] = kept
        for name in sorted(files):
            if name.endswith(".java"):
                paths.add((parent / name).relative_to(root).as_posix())
                if len(paths) > limit:
                    raise RuntimeError(f"Directory scan exceeds --max-files {limit}; select a smaller module")
    return paths


def make_sources(args, report):
    warnings = report["warnings"]
    if args.command == "review":
        requested = Path(args.repo).expanduser().resolve()
        if not requested.is_dir():
            raise RuntimeError("--repo must be an existing local Git worktree")
        repo = Path(git(requested, ["rev-parse", "--show-toplevel"]).decode().strip()).resolve()
        base = resolve_commit(repo, args.base)
        head = resolve_commit(repo, args.head) if args.head else None
        diff_args = ["diff", "--no-ext-diff", "--no-textconv", "--ignore-submodules=all", "--no-renames", "--name-only", "-z", base]
        if head:
            diff_args.append(head)
        diff_args.append("--")
        paths = {item.decode("utf-8", "strict") for item in git(repo, diff_args).split(b"\0") if item}
        if args.include_untracked and not head:
            paths.update(item.decode("utf-8", "strict") for item in git(repo, ["ls-files", "--others", "--exclude-standard", "-z"]).split(b"\0") if item)
        if args.include_untracked and head:
            raise RuntimeError("--include-untracked applies only to a worktree review")
        if len(paths) > args.max_files:
            raise RuntimeError(f"Change set has {len(paths)} files, exceeding --max-files {args.max_files}")
        names = sorted(paths)
        for name in names:
            safe_relative(name)
        previous = tree_entries(repo, base, names)
        following = tree_entries(repo, head, names) if head else None
        report["target"].update({
            "repository": str(repo), "base_commit": base,
            "head_commit": head, "mode": "commits" if head else "worktree",
            "includes_untracked": bool(args.include_untracked),
        })
        if head:
            report["limitations"].append("Commit mode reviews only the two resolved Git snapshots; current working-tree edits are excluded.")
        else:
            report["limitations"].append("Worktree mode captures the current working files against base, combining staged and unstaged edits; index-only contents are not reviewed separately.")
        return names, GitBlobs(repo, previous, args.max_bytes_per_file), \
            GitBlobs(repo, following, args.max_bytes_per_file) if following is not None else \
            (lambda name: read_local(repo, name, args.max_bytes_per_file)), [repo]
    before = Path(args.before).expanduser().resolve()
    after = Path(args.after).expanduser().resolve()
    if not before.is_dir() or not after.is_dir():
        raise RuntimeError("--before and --after must be existing directories")
    report["target"].update({"mode": "directories", "before_directory": str(before), "after_directory": str(after)})
    paths = directory_paths(before, args.max_files, warnings) | directory_paths(after, args.max_files, warnings)
    if len(paths) > args.max_files:
        raise RuntimeError(f"Combined directory scan exceeds --max-files {args.max_files}")
    report["limitations"].append("Directory mode scans Java files only and excludes common build/dependency directories; non-Java configuration changes are not included.")
    return sorted(paths), lambda name: read_local(before, name, args.max_bytes_per_file), \
        lambda name: read_local(after, name, args.max_bytes_per_file), [before, after]


def digest(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def snapshot_and_review(args, report):
    names, get_before, get_after, protected_roots = make_sources(args, report)
    ensure_output(args.output, protected_roots)
    before_data: dict[str, bytes] = {}
    after_data: dict[str, bytes] = {}
    records = []
    diff_parts = []
    used_diff_bytes = 0
    total_bytes = 0
    skipped = 0
    for name in names:
        old, old_problem = get_before(name)
        new, new_problem = get_after(name)
        problems = [problem for problem in [old_problem, new_problem] if problem]
        if problems:
            skipped += 1
            report["warnings"].append(f"{name}: " + "; ".join(problems))
            records.append({"path": name, "status": "omitted", "reasons": problems})
            continue
        if old == new:
            continue
        total_bytes += len(old or b"") + len(new or b"")
        if total_bytes > args.max_total_bytes:
            raise RuntimeError(f"Snapshot exceeds --max-total-bytes {args.max_total_bytes}; select a smaller change")
        java = name.endswith(".java")
        binary = b"\0" in (old or b"") or b"\0" in (new or b"")
        entry = {"path": name, "status": "added" if old is None else "deleted" if new is None else "modified",
                 "before_sha256": digest(old), "after_sha256": digest(new), "java": java, "binary": binary,
                 "before_bytes": len(old or b""), "after_bytes": len(new or b"")}
        records.append(entry)
        if binary:
            skipped += 1
            report["warnings"].append(f"{name}: binary content omitted from textual and AST analysis")
            continue
        try:
            old_text = (old or b"").decode("utf-8")
            new_text = (new or b"").decode("utf-8")
        except UnicodeDecodeError:
            skipped += 1
            report["warnings"].append(f"{name}: non-UTF-8 source omitted; convert a copy before analysis")
            continue
        if java:
            if old is not None:
                before_data[name] = old
            if new is not None:
                after_data[name] = new
        patch_lines = difflib.unified_diff(old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                                          fromfile="a/" + name, tofile="b/" + name, n=3)
        patch = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in patch_lines)
        raw = patch.encode("utf-8")
        remaining = max(0, args.max_diff_bytes - used_diff_bytes)
        if remaining:
            diff_parts.append(raw[:remaining].decode("utf-8", "ignore"))
        used_diff_bytes += len(raw)
    fingerprint = hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    report["target"]["snapshot_sha256"] = fingerprint
    report["evidence"] = {
        "changed_files": records, "changed_file_count": len(records), "snapshot_bytes": total_bytes,
        "unified_diff": "\n".join(diff_parts), "diff_truncated": used_diff_bytes > args.max_diff_bytes,
        "refactorings": [], "ast_diffs": [],
    }
    if used_diff_bytes > args.max_diff_bytes:
        report["warnings"].append("Textual diff truncated at --max-diff-bytes; review missing context separately")
    if before_data or after_data:
        with tempfile.TemporaryDirectory(prefix="refactoringminer-review-", dir=runtime_module().temporary_root()) as temporary:
            previous = Path(temporary) / "before"
            following = Path(temporary) / "after"
            previous.mkdir()
            following.mkdir()
            for directory, contents in [(previous, before_data), (following, after_data)]:
                for name, data in contents.items():
                    target = directory.joinpath(*safe_relative(name).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            engine = runtime_module().run_java_bridge(SKILL_DIR, COMPONENT,
                                                      ["directories", str(previous), str(following)],
                                                      timeout=args.timeout, memory_mb=args.memory_mb)
        if "error" in engine:
            raise RuntimeError(engine["error"])
        report["engine"] = {"name": engine.get("engine"), "version": engine.get("version"), "executed": True,
                            "adapter_version": engine.get("adapter_version"), "edit_distance": engine.get("edit_distance"),
                            "core_overrides": engine.get("core_overrides")}
        if engine.get("runtime_diagnostics"):
            report["runtime_diagnostics"] = engine["runtime_diagnostics"]
        for key in ["refactorings", "refactoring_count", "ast_diffs", "ast_diff_count", "move_ast_diff_count", "ast_action_count"]:
            report["evidence"][key] = engine.get(key)
        report["timings"]["engine_ms"] = engine.get("elapsed_ms")
        if engine.get("truncated"):
            report["warnings"].append("Engine result truncated (1000 refactorings / 2000 AST actions); narrow the change set")
    else:
        report["engine"] = {"name": "RefactoringMiner", "version": "3.0.11", "executed": False}
        report["warnings"].append("No eligible changed Java source; RefactoringMiner was not invoked")
    if skipped or report["warnings"] and any("truncated" in item.lower() or "omitted" in item.lower() for item in report["warnings"]):
        report["status"] = "partial"


def ensure_output(output: str | None, protected_roots: list[Path]):
    if not output:
        return
    destination = Path(output).expanduser().resolve()
    if destination.exists():
        raise RuntimeError("Output file already exists; choose a new path")
    for root in protected_roots:
        if destination == root or root in destination.parents:
            raise RuntimeError("Write reports outside the analyzed repository/directories to keep inputs read-only")


def arguments():
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Report runtime and engine availability")
    doctor.add_argument("--output")
    prepare = commands.add_parser("prepare", help="Build the pinned engine in the external component cache")
    prepare.add_argument("--timeout", type=positive_int, default=300)
    prepare.add_argument("--output")
    review = commands.add_parser("review", help="Review a local Git worktree or two commits")
    review.add_argument("--repo", required=True)
    review.add_argument("--base", default="HEAD")
    review.add_argument("--head", help="Review this commit instead of the working files")
    review.add_argument("--include-untracked", action="store_true")
    directories = commands.add_parser("directories", help="Compare two Java source directories")
    directories.add_argument("--before", required=True)
    directories.add_argument("--after", required=True)
    for sub in [review, directories]:
        sub.add_argument("--format", choices=["full", "compact"], default="full",
                         help="stdout view; --output always saves full evidence")
        sub.add_argument("--timeout", type=positive_int, default=120)
        sub.add_argument("--memory-mb", type=positive_int, default=2048)
        sub.add_argument("--max-files", type=positive_int, default=100)
        sub.add_argument("--max-bytes-per-file", type=positive_int, default=1_000_000)
        sub.add_argument("--max-total-bytes", type=positive_int, default=16_000_000)
        sub.add_argument("--max-diff-bytes", type=positive_int, default=200_000)
        sub.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    try:
        args = arguments()
    except ValueError as error:
        sys.stdout.write(render_result({"schema_version": "1.0", "component": COMPONENT,
            "operation": "unknown", "status": "error", "target": {}, "evidence": {},
            "warnings": [], "limitations": [],
            "error": {"code": "INVALID_ARGUMENT", "message": str(error)}}))
        return 2
    started = time.monotonic()
    report = {"schema_version": "1.0", "component": COMPONENT, "operation": args.command,
              "status": "ok", "target": {}, "evidence": {}, "warnings": [], "limitations": list(LIMITATIONS), "timings": {}}
    if args.command == "review":
        report["target"] = {"requested_repository": args.repo, "requested_base": args.base,
                            "requested_head": args.head, "mode": "commits" if args.head else "worktree"}
    elif args.command == "directories":
        report["target"] = {"mode": "directories", "requested_before": args.before, "requested_after": args.after}
    try:
        if args.command == "doctor":
            environment = runtime_module().doctor(SKILL_DIR, COMPONENT)
            report["evidence"]["environment"] = environment
            report["status"] = environment.get("status", "error")
        elif args.command == "prepare":
            report["evidence"]["engine_jar"] = runtime_module().prepare_engine(SKILL_DIR, COMPONENT, timeout=args.timeout)
        else:
            snapshot_and_review(args, report)
    except (RuntimeError, OSError, UnicodeError, subprocess.TimeoutExpired, ValueError) as error:
        report["status"] = "error"
        report["error"] = str(error)
    report["timings"]["total_ms"] = round((time.monotonic() - started) * 1000)
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output and report["status"] != "error":
        try:
            ensure_output(args.output, [])
            Path(args.output).expanduser().parent.mkdir(parents=True, exist_ok=True)
            with Path(args.output).expanduser().open("x", encoding="utf-8") as handle:
                handle.write(content)
        except (RuntimeError, OSError) as error:
            report["status"] = "error"
            report["error"] = "Could not save output: " + str(error)
            content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.write(render_result(report, getattr(args, "format", "full"),
                                   args.output if report["status"] != "error" else None))
    return 2 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
