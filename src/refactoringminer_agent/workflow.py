"""Portable guidance for agent checkpoints; the host owns task scheduling."""

INSTRUCTIONS = (
    "Use RefactoringMiner proactively when reviewing Java changes and after a meaningful Java edit/fix batch, "
    "before reporting the candidate ready. Call review for Git changes or directories for source pairs. "
    "Use the task's actual baseline; include in-scope untracked Java files. Reuse evidence only for the identical "
    "target and content. Preserve partial/error status. Tool availability does not prove a checkpoint ran.\n\n"
    "Follow these checkpoints throughout the project, without requiring the user to name this tool again. "
    "Review the final candidate again if later edits changed the reviewed content. Avoid rerunning after each "
    "message, for unchanged content, or for tasks without Java changes. Inspect full refactoring/AST evidence, "
    "ordinary diff, affected callers and relevant tests; refactorings can include behavior changes. "
    "Record resolved commits or snapshot fingerprint, report reference, coverage and findings in the task handoff. "
    "On resume, verify the target and content before reusing a previous report. Keep complete reports outside "
    "the target project. An unavailable engine or partial/error result must remain visible as a coverage gap. "
    "Historical investigation can complement this analysis when a separate history tool is available. "
    "Do not infer passing tests or behavior preservation from this tool. The host must implement an explicit "
    "checkpoint gate if it requires deterministic enforcement; these instructions do not schedule work themselves."
)

CHECKPOINTS = [
    {"phase": "review_requested", "tools": ["review", "directories"],
     "when": "A Java worktree, commit range or source pair is being reviewed; choose the matching tool."},
    {"phase": "java_edit_batch_finished", "tools": ["review", "directories"],
     "when": "A meaningful Java implementation, refactoring or bug-fix batch is ready for review."},
    {"phase": "before_delivery", "tools": ["review", "directories"],
     "when": "The final Java candidate has no matching current review evidence; rerun after later edits."},
]
