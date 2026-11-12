---
name: refactoringminer-review
description: Proactively review Java changes at code-review, implementation, refactoring and bug-fix checkpoints, before reporting a candidate ready. Use for Java 代码审查 and 修复后审查 throughout a chat or project, even when the user does not name RefactoringMiner. Skip tasks without Java changes.
---

# RefactoringMiner review checkpoints

Apply this workflow throughout the active project. When reviewing Java changes, or after a meaningful Java edit/fix batch and before reporting it ready, collect refactoring, AST and text-diff evidence. If subsequent edits changed the candidate, review that updated candidate before delivery. Do not rerun for every message, every keystroke or unchanged reviewed content.

Use the connected RefactoringMiner `review`/`directories` tools when available. Otherwise use this skill's launcher with the installed SDK:

```sh
python "<skill-dir>/scripts/run.py" describe
python "<skill-dir>/scripts/run.py" call --request request.json
```

The launcher reads an optional `runtime.local.json` created by `install-skill` to locate the installed Python environment and Java cache. Keep that machine-specific file local. Without it, the current Python must have `refactoringminer-agent` installed. Use `doctor` for setup problems; do not diagnose before every call. Use `prepare` once when environment setup is within the requested task; otherwise report the unavailable engine explicitly.

Choose one request with the user's actual project and baseline:

```json
{"operation":"review","repo":"PROJECT","base":"BASE_SHA","include_untracked":true}
```

Include untracked Java files only when they belong to the requested change. Worktree review includes staged and unstaged files; `head` selects a committed comparison instead. Preserve the task's baseline before edits when the task needs a before/after review; do not silently substitute an unrelated revision. For source snapshots without Git, use `directories` with `before` and `after`.

Keep the complete JSON report outside the target project. Record the resolved commits or snapshot fingerprint, selected scope, report reference, status and coverage in the task's handoff. On a new chat or agent handoff, read that record and verify that it still describes the candidate before reusing it. A missing matching report means that the checkpoint still needs analysis; report storage alone does not perform a review.

Read ordinary diff, relevant callers and tests alongside AST/refactoring evidence. A detected refactoring may include behavior changes. Treat `partial`, skipped inputs and failures as visible coverage gaps, not a clean review. Support findings with file/line and evidence; distinguish inferred causes and unrun tests. Historical investigation may use a separately available history tool when it is relevant, but this skill works independently.

These are proactive agent instructions. A host that requires every checkpoint to be enforced must register the corresponding workflow event and verify its result; this skill does not create a background scheduler or grant extra permissions.
