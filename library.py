"""A saved-method library: reusable procedures, versioned, per equipment.

A protocol that took an afternoon to get right should be reachable next month
without rebuilding it. The unit of reuse here is a **method** — an ordered list
of modules with their parameters — not a whole project, because the cell being
tested changes far more often than the procedure being run on it.

Two rules keep a saved method from becoming a quiet hazard:

* **It records the equipment it was written for.** A schedule tuned for a 500 mA
  unit is not automatically safe on a smaller one, so loading onto a different
  profile is allowed but reported, never silent.
* **Saving never overwrites.** Each save appends a version; the old one stays
  readable. A method someone else is mid-experiment with cannot be edited out
  from under them, and "what did we run in March" stays answerable.

Nothing here writes equipment files or bypasses a gate. A method is exactly the
module list a user could have typed, so loading one lands in the same preflight
and the same export ladder as anything else.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

LIBRARY_SCHEMA = "pne_scheduler.method/v1"

# Keep letters and digits of any script: a Korean-named method must get a
# Korean id. Stripping to ASCII collapsed every Korean name onto the same
# fallback, which silently filed unrelated methods as versions of each other.
_SLUG_UNSAFE = re.compile(r"[^\w]+", re.UNICODE)
_SLUG_MAX = 60


def default_library_dir() -> Path:
    return Path.home() / ".pne_scheduler" / "library"


def _slug(name: str) -> str:
    """A filesystem-safe id that still resembles the name a person typed.

    Normalised to NFC first: macOS hands back decomposed Hangul from the
    filesystem, so a composed and a decomposed spelling of the same name would
    otherwise become two different methods.
    """
    normalized = unicodedata.normalize("NFC", name.strip().lower())
    slug = _SLUG_UNSAFE.sub("-", normalized).strip("-")
    return slug[:_SLUG_MAX] or "method"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    )
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, path)
    except BaseException:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)
        raise


@dataclass(frozen=True, slots=True)
class MethodVersion:
    method_id: str
    version: int
    name: str
    description: str
    equipment_unit: str
    equipment_layout: str
    modules: tuple[dict[str, Any], ...]
    saved_at: str
    path: Path | None = None

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def label(self) -> str:
        return f"{self.name} · v{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LIBRARY_SCHEMA,
            "method_id": self.method_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "equipment": {
                "unit": self.equipment_unit,
                "layout": self.equipment_layout,
            },
            "modules": [dict(module) for module in self.modules],
            "saved_at": self.saved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: Path | None = None) -> MethodVersion:
        equipment = data.get("equipment") or {}
        return cls(
            method_id=str(data.get("method_id", "")),
            version=int(data.get("version", 1)),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            equipment_unit=str(equipment.get("unit", "")),
            equipment_layout=str(equipment.get("layout", "")),
            modules=tuple(data.get("modules") or ()),
            saved_at=str(data.get("saved_at", "")),
            path=path,
        )


@dataclass(frozen=True, slots=True)
class LoadPlan:
    """What loading this method into the current project would mean."""

    method: MethodVersion
    modules: tuple[dict[str, Any], ...] = ()
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.modules)


class MethodLibrary:
    """Versioned method storage on disk, one JSON file per version."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else default_library_dir()

    # ------------------------------------------------------------- writing

    def save(
        self,
        *,
        name: str,
        modules: list[Any],
        equipment_unit: str = "",
        equipment_layout: str = "",
        description: str = "",
        method_id: str | None = None,
    ) -> MethodVersion:
        """Append a new version. An existing version is never rewritten."""
        if not name.strip():
            raise ValueError("이름을 입력하세요.")
        if not modules:
            raise ValueError("저장할 구간이 없습니다.")

        identifier = method_id or _slug(name)
        version = self.latest_version_number(identifier) + 1
        path = self.root / identifier / f"v{version:04d}.json"
        entry = MethodVersion(
            method_id=identifier,
            version=version,
            name=name.strip(),
            description=description.strip(),
            equipment_unit=equipment_unit,
            equipment_layout=equipment_layout,
            modules=tuple(
                module if isinstance(module, dict) else module.to_dict()
                for module in modules
            ),
            saved_at=datetime.now().isoformat(timespec="seconds"),
            path=path,
        )
        _atomic_write(path, json.dumps(entry.to_dict(), ensure_ascii=False, indent=2))
        return entry

    # ------------------------------------------------------------- reading

    def latest_version_number(self, method_id: str) -> int:
        versions = [entry.version for entry in self.versions(method_id)]
        return max(versions) if versions else 0

    def versions(self, method_id: str) -> tuple[MethodVersion, ...]:
        directory = self.root / method_id
        if not directory.is_dir():
            return ()
        found: list[MethodVersion] = []
        for path in sorted(directory.glob("v*.json")):
            entry = self._read(path)
            if entry is not None:
                found.append(entry)
        return tuple(sorted(found, key=lambda item: item.version))

    def latest(self, method_id: str) -> MethodVersion | None:
        versions = self.versions(method_id)
        return versions[-1] if versions else None

    def methods(self) -> tuple[MethodVersion, ...]:
        """The newest version of every saved method, newest save first."""
        if not self.root.is_dir():
            return ()
        latest = [
            entry
            for directory in sorted(self.root.iterdir())
            if directory.is_dir()
            for entry in (self.latest(directory.name),)
            if entry is not None
        ]
        return tuple(sorted(latest, key=lambda item: item.saved_at, reverse=True))

    def _read(self, path: Path) -> MethodVersion | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or data.get("schema") != LIBRARY_SCHEMA:
            return None
        return MethodVersion.from_dict(data, path=path)

    # ------------------------------------------------------------- loading

    def plan_load(
        self,
        method: MethodVersion,
        *,
        equipment_unit: str = "",
        equipment_layout: str = "",
    ) -> LoadPlan:
        """Check a method against the current equipment before it is applied."""
        errors: list[str] = []
        warnings: list[str] = []
        notes: list[str] = []

        if not method.modules:
            errors.append("이 버전에는 구간이 없습니다.")
            return LoadPlan(method=method, errors=tuple(errors))

        notes.append(
            f"{method.label} · 구간 {method.module_count}개 · 저장 {method.saved_at}"
        )
        if method.equipment_unit and equipment_unit and (
            method.equipment_unit != equipment_unit
        ):
            warnings.append(
                f"이 방법은 {method.equipment_unit} 용으로 저장되었고 현재 장비는 "
                f"{equipment_unit} 입니다. 전류 한계와 레이아웃을 다시 확인하세요."
            )
        elif not equipment_unit:
            warnings.append(
                "현재 프로젝트에 장비 프로파일이 없어 전류 한계를 대조할 수 없습니다."
            )
        if method.equipment_layout and equipment_layout and (
            method.equipment_layout != equipment_layout
        ):
            warnings.append(
                f"SCH 레이아웃이 다릅니다 (저장 {method.equipment_layout} / "
                f"현재 {equipment_layout})."
            )

        warnings.append(
            "불러온 구간도 다른 구간과 똑같이 검증과 내보내기 게이트를 거칩니다. "
            "저장되었다는 것이 검증되었다는 뜻은 아닙니다."
        )
        return LoadPlan(
            method=method,
            modules=tuple(dict(module) for module in method.modules),
            notes=tuple(notes),
            warnings=tuple(warnings),
        )


def save_project_as_method(
    store: MethodLibrary,
    project: Any,
    *,
    name: str,
    description: str = "",
    method_id: str | None = None,
) -> MethodVersion:
    """Save a project's module list, reading the equipment off the project.

    The CLI and the API both needed this; having it twice meant a method saved
    one way could carry a different equipment record than the same project saved
    the other.
    """
    equipment = project.equipment
    return store.save(
        name=name,
        description=description,
        method_id=method_id,
        modules=[node.to_dict() for node in project.modules],
        equipment_unit=equipment.unit if equipment else "",
        equipment_layout=(equipment.layout_key or "") if equipment else "",
    )


__all__ = [
    "save_project_as_method",
    "LIBRARY_SCHEMA",
    "LoadPlan",
    "MethodLibrary",
    "MethodVersion",
    "default_library_dir",
]
