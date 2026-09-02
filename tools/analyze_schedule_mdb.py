"""Analyze CTSEditorPro Schedule.mdb (Jet DB) structure."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from access_parser import AccessParser  # noqa: E402

REPORT_JSON = ROOT / "planning" / "SCHEDULE_MDB_ANALYSIS.json"

STEP_COLUMNS = [
    "StepID",
    "TestID",
    "StepNo",
    "StepType",
    "StepMode",
    "Vref",
    "Iref",
    "EndTime",
    "EndV",
    "EndI",
    "EndCapacity",
    "End_dV",
    "End_dI",
    "OverV",
    "LimitV",
    "OverI",
    "LimitI",
    "OverCapacity",
    "LimitCapacity",
    "OverImpedance",
    "LimitImpedance",
    "DeltaTime",
    "DeltaV",
    "DeltaI",
    "Grade",
    "VoltageReport",
    "CurrentReport",
    "CapacityReport",
    "TimeReport",
    "ImpedanceReport",
    "WattReport",
    "WattHourReport",
    "CompTime1",
    "CompValue1",
    "CompTime2",
    "CompValue2",
    "CompTime3",
    "CompValue3",
    "DeltaTime1",
]


def _table_summary(db: AccessParser, name: str) -> dict:
    try:
        table = db.parse_table(name)
        if not isinstance(table, dict) or not table:
            return {"row_count": 0, "columns": [], "sample_rows": []}
        columns = list(table.keys())
        row_count = len(next(iter(table.values())))
        sample_rows = [
            {column: table[column][index] for column in columns}
            for index in range(min(3, row_count))
        ]
        return {
            "row_count": row_count,
            "columns": columns,
            "sample_rows": sample_rows,
        }
    except Exception as exc:  # pragma: no cover - depends on Jet overflow pages
        return {"error": str(exc), "columns_inferred": STEP_COLUMNS if name == "Step" else []}


def build_schedule_mdb_report(path: Path) -> dict:
    db = AccessParser(str(path))
    user_tables = sorted(name for name in db.catalog if not name.startswith("MSys"))
    tables = {name: _table_summary(db, name) for name in user_tables}

    test_name = db.parse_table("TestName")
    battery_model = db.parse_table("BatteryModel")
    model_names = {
        battery_model["ModelID"][index]: battery_model["ModelName"][index]
        for index in range(len(battery_model["ModelID"]))
    }
    schedules_per_model = Counter(
        model_names.get(test_name["ModelID"][index], str(test_name["ModelID"][index]))
        for index in range(len(test_name["TestID"]))
    )

    check = db.parse_table("Check")
    safety_matches = [
        {
            "TestID": check["TestID"][index],
            "MaxV_mV": check["MaxV"][index],
            "MinV_mV": check["MinV"][index],
            "CurrentRange": check["CurrentRange"][index],
            "DeltaVoltage": check["DeltaVoltage"][index],
        }
        for index in range(len(check["TestID"]))
        if check["MaxV"][index] == 4300.0 and check["MinV"][index] == 1500.0
    ]

    return {
        "schema": "pne_scheduler.schedule_mdb_analysis/v1",
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "format": "Microsoft Jet DB (Standard Jet DB)",
        "contains_raw_sch_blobs": False,
        "notes": [
            "Schedule.mdb is the CTSEditorPro relational schedule catalog, not a raw .sch archive.",
            "Schedules are stored as TestName + Step rows; .sch export compiles these rows to binary.",
            "Step table parsing may fail on overflow/memo pages; use CTSPro export for full step dumps.",
        ],
        "table_count": len(user_tables),
        "tables": tables,
        "entity_model": {
            "BatteryModel": "Schedule list / folder (UI 목록명, e.g. Sample)",
            "TestName": "One schedule profile (UI 스케줄명, e.g. baseline); primary key TestID",
            "Step": "Ordered step rows for each TestID (charge/discharge/loop/rest/end)",
            "Check": "Per-schedule safety limits (maps to SCH header safety block)",
            "StepType": "Lookup: Charge, Discharge, Rest, OCV, Loop, End, ...",
            "StepMode": "Lookup: CC-CV, CC, CV, OCV",
            "SystemConfig": "Installed cycler module limits and network metadata",
            "Property": "Logged channel property units (Time, Voltage mV, Current mA, ...)",
        },
        "counts": {
            "schedules": len(test_name["TestID"]),
            "battery_models": len(battery_model["ModelID"]),
            "safety_records": len(check["TestID"]),
            "schedules_per_model_top10": schedules_per_model.most_common(10),
        },
        "step_columns_inferred": STEP_COLUMNS,
        "baseline_like_safety_hits": safety_matches[:20],
        "sch_field_mapping_hypothesis": {
            "Check.MaxV": "SCH header max voltage (mV)",
            "Check.MinV": "SCH header min voltage (mV)",
            "Check.DeltaVoltage": "often max temperature (°C) in sample data",
            "Step.Vref": "step current setpoint (mA) on charge/discharge rows",
            "Step.EndV": "voltage termination (mV)",
            "Step.EndI": "CV cutoff current (mA)",
            "Step.EndCapacity": "capacity termination",
            "Step.DeltaTime": "record/sampling interval (s)",
            "loop_count": "LOOP row only; stored in .sch step record, not a separate Step column",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mdb_path",
        type=Path,
        nargs="?",
        default=Path("c:/Schedule.mdb"),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=REPORT_JSON,
    )
    args = parser.parse_args()
    report = build_schedule_mdb_report(args.mdb_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    print("tables:", report["table_count"], "schedules:", report["counts"]["schedules"])
    step = report["tables"].get("Step", {})
    print("Step:", step.get("row_count", step.get("error", "unknown")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
