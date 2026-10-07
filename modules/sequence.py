"""A reusable ordered group; children retain their editable module parameters."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..ir.cell_profile import CellProfile
from ..ir.project import ModuleNode
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("sequence")
@dataclass
class SequenceModule:
    name: str = "내 블록"
    children: list[dict] = field(default_factory=list)
    repeat_count: int = 1

    @classmethod
    def from_params(cls, params: dict) -> SequenceModule:
        return cls(**{key: value for key, value in params.items() if key in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        from .catalog import get_module_spec

        errors = []
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 120:
            errors.append("블록 이름은 1–120자로 입력하세요.")
        if isinstance(self.repeat_count, bool) or not isinstance(self.repeat_count, int) or not 1 <= self.repeat_count <= 10000:
            errors.append("블록 반복 횟수는 1–10000 정수여야 합니다.")
        if not isinstance(self.children, list) or not 1 <= len(self.children) <= 100:
            return errors + ["블록에는 1–100개 모듈이 필요합니다."]
        ids = set()
        for child in self.children:
            if not isinstance(child, dict) or not isinstance(child.get("params", {}), dict):
                errors.append("블록 내부 모듈 형식이 잘못되었습니다.")
                continue
            kind = child.get("module_type")
            spec = get_module_spec(kind)
            if kind == "sequence" or spec is None or spec.internal_only:
                errors.append("중첩 블록·내부 검사용 모듈은 묶을 수 없습니다.")
            identifier = child.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in ids:
                errors.append("블록 내부 모듈 ID는 비어 있지 않고 고유해야 합니다.")
            ids.add(str(identifier))
        return errors

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        from ..ir.composer import compose_module_steps

        # Child LOOP targets are resolved relative to this whole group first;
        # the parent composer then rebases them when the group moves.
        children = [ModuleNode.from_dict(child) for child in self.children]
        body = [replace(step, ref_id=None) for step in compose_module_steps(children, cell, append_end=False)]
        if not body:
            raise ValueError("실행 스텝이 없는 블록입니다.")
        if self.repeat_count > 1:
            body.append(StepIntent(step_type="loop", label=f"{self.name} {self.repeat_count}회 반복", loop_goto_step=1, loop_count=self.repeat_count))
        return body
