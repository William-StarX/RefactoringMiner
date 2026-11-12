"""Typed convenience methods shared by the local and HTTP clients."""
from os import PathLike
from typing import Any
from .models import AnalysisResult


class Operations:
    def call(self, operation: str, **arguments: Any) -> AnalysisResult:
        raise NotImplementedError

    def review(self, repo: str | PathLike, *, base: str = "HEAD", head: str | None = None, **options: Any) -> AnalysisResult:
        if head is not None:
            options["head"] = head
        return self.call("review", repo=repo, base=base, **options)

    def directories(self, before: str | PathLike, after: str | PathLike, **options: Any) -> AnalysisResult:
        return self.call("directories", before=before, after=after, **options)
