"""Gate D verification suite — machine-enforceable checklist (V1–V8)."""

from __future__ import annotations

import json
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..engine.c_rate import WRITER_Q_NOM_SOURCE, current_mA_from_c_rate
from ..engine.compiler import compile_steps
from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from ..ir.project import ModuleNode
from ..modules.base import expand_module, get_module_class, list_module_types
from ..schema.ensol_v612 import OFF_CURRENT_MA
from .gate_d_harness import run_module_pipeline
from .topology import fixture_type_family, intent_type_family, load_golden_by_id

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "planning" / "Q_NOM_POLICY.json"
FIXTURE_ROOT = ROOT / "example" / "fixtures"
DEFAULT_REPORT_PATH = ROOT / "planning" / "GATE_D_VALIDATION_REPORT.json"

DEFAULT_CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)

# Gate D module matrix — verification profiles (see GATE_D_VERIFICATION.md).
GATE_D_MODULE_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "id": "formation",
        "module_type": "formation",
        "params": {"cycle_count": 1, "rest_s": 60.0},
        "required_tokens": ("charge", "rest", "discharge", "end"),
        "required_warning_substrings": (),
    },
    {
        "id": "rest",
        "module_type": "rest",
        "params": {"duration_s": 120.0},
        "required_tokens": ("rest", "end"),
        "required_warning_substrings": (),
    },
    {
        "id": "cycle_life",
        "module_type": "cycle_life",
        "params": {"loop_count": 2, "rest_s": 30.0},
        "required_tokens": ("cycle", "charge", "discharge", "loop", "end"),
        "required_warning_substrings": (),
    },
    {
        "id": "rpt",
        "module_type": "rpt",
        "params": {
            "soc_fractions": [0.8, 0.5],
            "rest_s": 10.0,
            "dcir_pulse_s": 2.0,
        },
        "required_tokens": ("discharge", "rest", "end"),
        "required_warning_substrings": ("dcr_start_s", "fEndC"),
    },
    {
        "id": "dcir",
        "module_type": "dcir",
        "params": {"soc_fractions": [0.8], "rest_s": 10.0, "pulse_s": 2.0},
        "required_tokens": ("discharge", "rest", "end"),
        "required_warning_substrings": ("dcr_start_s", "fEndC"),
    },
    {
        "id": "hppc",
        "module_type": "hppc",
        "params": {
            "soc_fractions": [0.9, 0.5],
            "rest_between_s": 5.0,
            "pulse_s": 2.0,
        },
        "required_tokens": ("charge", "discharge", "rest", "end"),
        "required_warning_substrings": ("fEndC",),
    },
    {
        "id": "capacheck",
        "module_type": "capacheck",
        "params": {"measurement_cycles": 1, "rest_s": 10.0, "loop_count": 1},
        "required_tokens": ("cycle", "loop", "charge", "discharge", "end"),
        "required_warning_substrings": (),
    },
    {
        "id": "qpeed_full",
        "module_type": "qpeed",
        "params": {
            "variant": "full",
            "soc_fractions": [0.5],
            "rest_between_s": 5.0,
            "pulse_s": 2.0,
        },
        "required_tokens": ("charge", "discharge", "rest", "end"),
        "required_warning_substrings": ("fEndC",),
    },
    {
        "id": "qpeed_soc_setting",
        "module_type": "qpeed",
        "params": {
            "variant": "soc_setting",
            "soc_fractions": [0.5],
            "rest_between_s": 5.0,
        },
        "required_tokens": ("discharge", "rest", "loop", "end"),
        "required_warning_substrings": ("fEndC",),
    },
    {
        "id": "insitu_cycle",
        "module_type": "insitu_cycle",
        "params": {"loop_count": 2, "rest_s": 5.0},
        "required_tokens": ("cycle", "charge", "discharge", "loop", "end"),
        "required_warning_substrings": (),
        "label_substring": "in-situ",
    },
)

# ``module_ref`` names the GATE_D_MODULE_MATRIX row whose expansion must share
# the required families with the golden. Rows without it are fixture-parseability
# checks only (GATE_D_VERIFICATION.md §4 marks rpt/qpeed as "(fixture only)").
GATE_D_FAMILY_CHECKS: tuple[dict[str, Any], ...] = (
    {
        "id": "family_formation",
        "golden_id": "golden-formation-696",
        "required_shared": frozenset({"charge", "rest"}),
        "module_ref": "formation",
    },
    {
        "id": "family_cycle",
        "golden_id": "golden-cycle-612-long",
        "required_shared": frozenset({"charge", "discharge", "rest", "loop", "end"}),
        "module_ref": "cycle_life",
    },
    {
        "id": "family_hppc",
        "golden_id": "golden-hppc-612",
        "required_shared": frozenset({"charge", "discharge", "rest"}),
        "module_ref": "hppc",
    },
    {
        "id": "family_capacheck",
        "golden_id": "golden-capacheck-612-b0",
        "required_shared": frozenset(
            {"cycle", "loop", "charge", "discharge", "rest", "end"}
        ),
        "module_ref": "capacheck",
    },
    {
        "id": "family_rpt_parseable",
        "golden_id": "golden-rpt-612",
        "required_shared": frozenset({"charge", "discharge", "rest", "end"}),
    },
    {
        "id": "family_qpeed_parseable",
        "golden_id": "golden-qpeed-612",
        "required_shared": frozenset({"charge", "discharge", "rest", "end"}),
    },
)

# Smoke / probe modules are Gate C, not Gate D matrix members.
_GATE_D_REGISTERED_TYPES = frozenset(row["module_type"] for row in GATE_D_MODULE_MATRIX)
_NON_GATE_D_MODULES = frozenset(
    {"smoke_rest_cc_end", "smoke_writer_probe"}
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    id: str
    layer: str
    status: str  # pass | fail | skip
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "layer": self.layer,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class GateDVerificationReport:
    gate_d_passed: bool
    checks: tuple[CheckResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "pne_scheduler.gate_d_validation_report/v1",
            "method_ref": "planning/GATE_D_VERIFICATION.md",
            "audit_ref": "planning/GATE_D_VERIFICATION_AUDIT.md",
            "gate_d_passed": self.gate_d_passed,
            "summary": {
                "pass": sum(1 for c in self.checks if c.status == "pass"),
                "fail": sum(1 for c in self.checks if c.status == "fail"),
                "skip": sum(1 for c in self.checks if c.status == "skip"),
                "total": len(self.checks),
            },
            "checks": [c.to_dict() for c in self.checks],
        }


def run_gate_d_verification(
    *,
    cell: CellProfile | None = None,
    work_dir: Path | None = None,
) -> GateDVerificationReport:
    """Execute V1–V8 Gate D verification and return an aggregate report."""
    cell = cell or DEFAULT_CELL
    checks: list[CheckResult] = []
    own_tmpdir = None
    if work_dir is None:
        own_tmpdir = tempfile.TemporaryDirectory(prefix="gate_d_verify_")
        work_dir = Path(own_tmpdir.name)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        checks.extend(_check_v1_capacity(cell))
        checks.extend(_check_v7_registry())
        checks.extend(_check_v2_v3_v4_v5_modules(cell, work_dir))
        checks.extend(_check_v6_families())
    finally:
        if own_tmpdir is not None:
            own_tmpdir.cleanup()

    # V8: report itself. A skipped check is not a pass — a missing golden means
    # that comparison never ran, so counting it as "not a failure" let
    # gate_d_passed stay true with zero golden comparisons actually executed
    # (L4: exit criteria must match delivered depth). Skips therefore block the
    # exit claim, while staying distinguishable from real mismatches in the report.
    failed = [c for c in checks if c.status == "fail"]
    skipped = [c for c in checks if c.status == "skip"]
    if failed:
        v8_status = "fail"
        v8_detail = f"{len(failed)} failed: " + ", ".join(c.id for c in failed[:8])
    elif skipped:
        v8_status = "fail"
        v8_detail = (
            f"{len(skipped)} check(s) never ran, so the exit claim is unproven: "
            + ", ".join(c.id for c in skipped[:8])
        )
    else:
        v8_status = "pass"
        v8_detail = f"all {len(checks)} checks executed and passed"
    checks.append(CheckResult(id="v8_exit_aggregate", layer="V8", status=v8_status, detail=v8_detail))
    gate_passed = not failed and not skipped
    return GateDVerificationReport(gate_d_passed=gate_passed, checks=tuple(checks))


def write_gate_d_verification_report(
    report: GateDVerificationReport,
    path: Path | None = None,
) -> Path:
    out = path or DEFAULT_REPORT_PATH
    out.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def _check_v1_capacity(cell: CellProfile) -> list[CheckResult]:
    results: list[CheckResult] = []
    if not POLICY_PATH.is_file():
        return [
            CheckResult(
                "v1_policy_file",
                "V1",
                "fail",
                f"missing {POLICY_PATH}",
            )
        ]
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    writer = policy.get("writer", {})
    ok = (
        writer.get("source") == WRITER_Q_NOM_SOURCE
        and writer.get("explicit_value_required") is True
        and writer.get("allow_filename_inference") is False
        and writer.get("allow_stack_geometry_inference") is False
    )
    results.append(
        CheckResult(
            "v1_policy_lock",
            "V1",
            "pass" if ok else "fail",
            f"writer.source={writer.get('source')!r}",
        )
    )
    record = compile_steps(
        [StepIntent(step_type="charge", mode="CC", c_rate=0.5, voltage_v=4.2)],
        cell,
    )[0]
    packed = struct.unpack_from("<f", record, OFF_CURRENT_MA)[0]
    expected = current_mA_from_c_rate(0.5, cell)
    results.append(
        CheckResult(
            "v1_compile_uses_cell_q_nom",
            "V1",
            "pass" if abs(packed - expected) < 1e-3 else "fail",
            f"packed={packed} expected={expected}",
        )
    )
    return results


def _check_v7_registry() -> list[CheckResult]:
    registered = set(list_module_types())
    missing = sorted(_GATE_D_REGISTERED_TYPES - registered)
    extras = sorted(
        (registered - _GATE_D_REGISTERED_TYPES) - _NON_GATE_D_MODULES
    )
    results = [
        CheckResult(
            "v7_matrix_registered",
            "V7",
            "pass" if not missing else "fail",
            "ok" if not missing else f"missing modules: {missing}",
        )
    ]
    # Extras are informational — fail only if a Gate D type is missing.
    # Unknown non-matrix modules (future) stay allowed but noted.
    results.append(
        CheckResult(
            "v7_non_matrix_modules_noted",
            "V7",
            "pass",
            f"non-matrix registered modules: {extras or 'none'}",
        )
    )
    for row in GATE_D_MODULE_MATRIX:
        cls = get_module_class(row["module_type"])
        results.append(
            CheckResult(
                f"v7_class_{row['id']}",
                "V7",
                "pass" if cls is not None else "fail",
                row["module_type"],
            )
        )
    return results


def _check_v2_v3_v4_v5_modules(cell: CellProfile, work_dir: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for row in GATE_D_MODULE_MATRIX:
        mid = row["id"]
        report = run_module_pipeline(
            row["module_type"],
            cell=cell,
            output_path=work_dir / f"{mid}.sch",
            params=dict(row["params"]),
            schedule_name=f"verify_{mid}",
        )
        results.append(
            CheckResult(
                f"v2_pipeline_{mid}",
                "V2/V3/V4",
                "pass" if report.passed else "fail",
                (
                    f"steps={report.step_count}"
                    if report.passed
                    else "; ".join(report.mismatches[:4]) or "pipeline failed"
                ),
            )
        )
        missing_tokens = [
            t for t in row["required_tokens"] if t not in report.topology
        ]
        results.append(
            CheckResult(
                f"v2_topology_{mid}",
                "V2",
                "pass" if not missing_tokens else "fail",
                (
                    "tokens ok"
                    if not missing_tokens
                    else f"missing {missing_tokens} in {report.topology}"
                ),
            )
        )
        warning_blob = " | ".join(report.warnings)
        for needle in row["required_warning_substrings"]:
            results.append(
                CheckResult(
                    f"v5_warn_{mid}_{needle}",
                    "V5",
                    "pass" if needle in warning_blob else "fail",
                    f"expected warning containing {needle!r}",
                )
            )
        label_sub = row.get("label_substring")
        if label_sub:
            from ..ir.project import ModuleNode
            from ..modules.base import expand_module

            intents = expand_module(
                ModuleNode(id="x", module_type=row["module_type"], params=dict(row["params"])),
                cell,
            )
            labels = " | ".join(i.label for i in intents)
            results.append(
                CheckResult(
                    f"v2_label_{mid}",
                    "V2",
                    "pass" if label_sub in labels else "fail",
                    f"label_substring={label_sub!r}",
                )
            )
    return results


def _check_v6_families() -> list[CheckResult]:
    results: list[CheckResult] = []
    for row in GATE_D_FAMILY_CHECKS:
        try:
            golden = load_golden_by_id(row["golden_id"])
        except KeyError as exc:
            results.append(
                CheckResult(row["id"], "V6", "fail", str(exc))
            )
            continue
        path = FIXTURE_ROOT / Path(golden["path"])
        if not path.is_file():
            results.append(
                CheckResult(
                    row["id"],
                    "V6",
                    "skip",
                    f"fixture missing: {path.name}",
                )
            )
            continue
        family = fixture_type_family(path)
        required: frozenset[str] = row["required_shared"]
        missing_in_golden = sorted(required - family)

        # The golden alone is a static file that never changes — checking only it
        # can never catch a module regression, which is what Gate D exists to
        # verify. Rows naming a module must also compare that module's live
        # expansion (GATE_D_VERIFICATION.md §4: "share required type families
        # with module expands").
        module_ref = row.get("module_ref")
        missing_in_module: list[str] = []
        module_detail = ""
        if module_ref is not None:
            matrix_row = _module_matrix_row(module_ref)
            intents = expand_module(
                ModuleNode(
                    id="v6",
                    module_type=matrix_row["module_type"],
                    params=dict(matrix_row["params"]),
                ),
                DEFAULT_CELL,
            )
            module_family = intent_type_family(intents)
            missing_in_module = sorted(required - module_family)
            module_detail = f"; module={sorted(module_family)}"

        missing = sorted({*missing_in_golden, *missing_in_module})
        if not missing:
            detail = f"family={sorted(family)}{module_detail}"
        else:
            parts = []
            if missing_in_golden:
                parts.append(f"golden missing {missing_in_golden}")
            if missing_in_module:
                parts.append(f"module '{module_ref}' missing {missing_in_module}")
            detail = "; ".join(parts) + f" (golden={sorted(family)}{module_detail})"
        results.append(
            CheckResult(
                row["id"],
                "V6",
                "pass" if not missing else "fail",
                detail,
            )
        )
    return results


def _module_matrix_row(module_id: str) -> dict[str, Any]:
    for row in GATE_D_MODULE_MATRIX:
        if row["id"] == module_id:
            return row
    raise KeyError(f"family check references unknown matrix row: {module_id}")
