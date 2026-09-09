"""One shape for every refusal.

A rejected edit is ordinary traffic here — a C-rate outside the cell window, a
step index past the end of a module, an unproven `.sch` field. The client needs
the reason in Korean, so it is carried in the body rather than only in a status
code.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """A refusal that is the caller's to fix, reported with its reason."""

    def __init__(self, message: str, *, status: int = 400, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"ok": False, "error": self.message}
        if self.detail is not None:
            body["detail"] = self.detail
        return body


__all__ = ["ApiError"]
