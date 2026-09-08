"""The one word that says how far an artifact has been verified.

Every file this tool produces is somewhere on a ladder that only a person can
climb: software can prove a schedule is self-consistent, never that CTSEditorPro
opened it or that the lab agreed to run it.  Naming that position on the artifact
itself is what stops a file from being trusted for more than it earned once it has
travelled away from the session that made it.

The label is bound to a **content hash**, not to a project.  An approval recorded
for one byte sequence says nothing about a different one, so editing a schedule
after review silently invalidates the approval — and this module makes that
silence loud: `label_for` returns `analysis-only` again the moment the digest
stops matching the reviewed one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReleaseLabel = Literal[
    "analysis-only",
    "software-checked",
    "CTSPro-reopen-verified",
    "equipment-verified",
]

# Ordered weakest to strongest; index doubles as the comparison rank.
LABEL_LADDER: tuple[ReleaseLabel, ...] = (
    "analysis-only",
    "software-checked",
    "CTSPro-reopen-verified",
    "equipment-verified",
)

LABEL_LABELS_KO: dict[str, str] = {
    "analysis-only": "분석 전용",
    "software-checked": "소프트웨어 검증됨",
    "CTSPro-reopen-verified": "CTSPro 재열기 확인됨",
    "equipment-verified": "장비 실행 승인됨",
}

LABEL_MEANING_KO: dict[str, str] = {
    "analysis-only": "읽고 분석하는 용도입니다. 장비로 보내지 마십시오.",
    "software-checked": "구조 검증만 통과했습니다. 사람이 연 적은 없습니다.",
    "CTSPro-reopen-verified": "이 해시의 파일을 CTSEditorPro 에서 열어 확인했습니다.",
    "equipment-verified": "이 해시의 파일에 대해 장비 실행 승인이 기록되었습니다.",
}


def label_rank(label: str) -> int:
    try:
        return LABEL_LADDER.index(label)  # type: ignore[arg-type]
    except ValueError:
        return 0


@dataclass(frozen=True, slots=True)
class LabelDecision:
    label: ReleaseLabel
    label_ko: str
    meaning_ko: str
    reasons: tuple[str, ...] = ()
    digest_mismatch: bool = False

    @property
    def equipment_executable(self) -> bool:
        return self.label == "equipment-verified"

    def as_manifest_fields(self) -> dict[str, object]:
        """The subset a validation manifest carries."""
        return {
            "release_label": self.label,
            "equipment_executable": self.equipment_executable,
            "release_label_reasons": list(self.reasons),
        }


def label_for(
    *,
    software_ok: bool,
    ctspro_reviewed: bool,
    equipment_approved: bool,
    reviewed_sha256: str = "",
    artifact_sha256: str = "",
) -> LabelDecision:
    """Rank an artifact, refusing to carry an approval across a content change.

    ``artifact_sha256`` is the digest of the thing being labelled.  When it is
    given and differs from the digest that was reviewed, every human approval is
    dropped: those approvals were about a file that no longer exists.
    """
    reasons: list[str] = []
    mismatch = bool(
        artifact_sha256 and reviewed_sha256 and artifact_sha256 != reviewed_sha256
    )

    if mismatch:
        reasons.append(
            "검토 기록의 해시와 현재 파일의 해시가 다릅니다. "
            f"검토됨 {reviewed_sha256[:12]}… / 현재 {artifact_sha256[:12]}… — "
            "승인은 그 파일에 대한 것이므로 이 파일에는 적용되지 않습니다."
        )
        ctspro_reviewed = False
        equipment_approved = False
    elif artifact_sha256 and ctspro_reviewed and not reviewed_sha256:
        reasons.append(
            "CTSPro 확인이 기록되었지만 대상 파일 해시가 남아 있지 않아 "
            "이 파일과 같은 파일인지 확인할 수 없습니다."
        )
        ctspro_reviewed = False
        equipment_approved = False

    if not software_ok:
        reasons.append("소프트웨어 검증을 통과하지 못했습니다.")
        label: ReleaseLabel = "analysis-only"
    elif not ctspro_reviewed:
        reasons.append("CTSPro 재열기 확인 기록이 없습니다.")
        label = "software-checked"
    elif not equipment_approved:
        reasons.append("장비 실행 승인 기록이 없습니다.")
        label = "CTSPro-reopen-verified"
    else:
        label = "equipment-verified"

    return LabelDecision(
        label=label,
        label_ko=LABEL_LABELS_KO[label],
        meaning_ko=LABEL_MEANING_KO[label],
        reasons=tuple(reasons),
        digest_mismatch=mismatch,
    )


__all__ = [
    "LABEL_LABELS_KO",
    "LABEL_LADDER",
    "LABEL_MEANING_KO",
    "LabelDecision",
    "ReleaseLabel",
    "label_for",
    "label_rank",
]
