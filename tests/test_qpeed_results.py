"""QPEED result import stays explicit, bounded, and preview-bound."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from pne_scheduler.protocol.qpeed_results import MAX_BYTES, preview_soc_voltages
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel


def _project(tmp_path):
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    model.set_cell_value("nominal_capacity_mAh", "80")
    module_id = model.add_module("qpeed", {"variant": "full", "soc_control": "capacity"})
    return model.project.to_dict(), module_id


def _client(tmp_path):
    pytest.importorskip("flask")
    from pne_scheduler.api.app import create_app

    return create_app(
        tmp_path / "library", storage_db_path=tmp_path / "storage.sqlite3"
    ).test_client()


def _http_payload(tmp_path):
    project, module_id = _project(tmp_path)
    args = {
        "moduleId": module_id,
        "fileName": "cycler/result.csv",
        "text": "Cell ID,Cycle No,Step No,Voltage (V),SOC (%)\nA01,2,7,3.71,42\n",
        "mapping": {},
    }
    return {"project": project, "args": args}, module_id


@pytest.mark.parametrize(
    ("text", "mapping", "expected"),
    [
        ("Voltage (V),SOC (%)\n3.712,55\n", {}, 3.712),
        (
            "Voltage (mV)\tSOC (fraction)\n3712\t0.55\n",
            {},
            3.712,
        ),
    ],
)
def test_csv_and_tsv_convert_explicit_voltage_units(text, mapping, expected):
    preview = preview_soc_voltages(text, mapping=mapping)

    assert preview["invalidRows"] == 0
    assert preview["candidates"][0]["voltageV"] == pytest.approx(expected)
    assert preview["candidates"][0]["socPercent"] == pytest.approx(55.0)


@pytest.mark.parametrize(
    ("header", "value", "unit"),
    [("SOC (%)", "37.5", "%"), ("SOC fraction", "0.375", "fraction")],
)
def test_soc_percent_and_fraction_require_and_preserve_explicit_basis(
    header, value, unit
):
    preview = preview_soc_voltages(f"Voltage (V),{header}\n3.65,{value}\n")
    candidate = preview["candidates"][0]

    assert preview["mapping"]["socUnit"] == unit
    assert candidate["socPercent"] == pytest.approx(37.5)
    assert candidate["socBasis"] == "파일의 SOC 열"


def test_voltage_without_soc_is_not_treated_as_a_soc_estimate():
    preview = preview_soc_voltages("Voltage (V)\n3.65\n")

    assert preview["candidates"][0]["socPercent"] is None
    assert preview["candidates"][0]["socBasis"] == ""
    assert "잔량을 추정하지 않습니다" in " ".join(preview["warnings"])


def test_qualified_charge_capacity_needs_reference_capacity_opt_in():
    text = "Voltage (V),Charge Capacity (mAh)\n3.68,20\n"

    without_reference = preview_soc_voltages(text)
    with_reference = preview_soc_voltages(text, reference_capacity_mAh=80.0)

    assert without_reference["candidates"][0]["socPercent"] is None
    assert with_reference["candidates"][0]["socPercent"] == pytest.approx(25.0)
    assert "입력 기준용량" in with_reference["candidates"][0]["socBasis"]


def test_unqualified_capacity_column_cannot_be_mapped_into_soc_calculation():
    preview = preview_soc_voltages(
        "Voltage (V),Capacity\n3.68,20\n",
        mapping={"capacityColumn": "Capacity"},
        reference_capacity_mAh=80.0,
    )

    assert preview["candidates"] == []
    assert preview["invalidRows"] == 1


def test_normalized_duplicate_headers_are_rejected():
    with pytest.raises(ValueError, match="중복된 열 이름"):
        preview_soc_voltages("Voltage (V),Voltage_V\n3.7,3.8\n")


def test_ambiguous_voltage_headers_wait_for_manual_column_mapping():
    text = "Voltage (V),전압(mV),SOC (%)\n3.7,3700,50\n"

    ambiguous = preview_soc_voltages(text)
    selected = preview_soc_voltages(
        text,
        mapping={
            "voltageColumn": "전압(mV)",
            "voltageUnit": "mV",
            "socColumn": "SOC (%)",
            "socUnit": "%",
        },
    )

    assert ambiguous["candidates"] == []
    assert "전압 열과 단위" in " ".join(ambiguous["warnings"])
    assert selected["candidates"][0]["voltageV"] == pytest.approx(3.7)


def test_unitless_headers_require_manual_units_before_rows_are_candidates():
    text = "Voltage,SOC\n3.7,0.5\n"

    voltage_unit_missing = preview_soc_voltages(text)
    soc_unit_missing = preview_soc_voltages(
        text, mapping={"voltageColumn": "Voltage", "voltageUnit": "V"}
    )
    selected = preview_soc_voltages(
        text,
        mapping={
            "voltageColumn": "Voltage",
            "voltageUnit": "V",
            "socColumn": "SOC",
            "socUnit": "fraction",
        },
    )

    assert voltage_unit_missing["candidates"] == []
    assert "전압 단위" in " ".join(voltage_unit_missing["warnings"])
    assert soc_unit_missing["candidates"] == []
    assert "SOC 열의 단위" in " ".join(soc_unit_missing["warnings"])
    assert selected["candidates"][0]["socPercent"] == pytest.approx(50.0)


def test_nan_and_out_of_range_rows_are_counted_and_reported():
    text = (
        "Voltage (V),SOC (%)\n"
        "3.7,50\n"
        "nan,50\n"
        "11,50\n"
        "3.8,101\n"
        "3.9,nan\n"
    )

    preview = preview_soc_voltages(text)

    assert preview["rowCount"] == 5
    assert preview["invalidRows"] == 4
    assert [row["row"] for row in preview["candidates"]] == [2]
    assert "4행을 제외했습니다" in " ".join(preview["warnings"])


def test_cell_cycle_step_group_keeps_the_last_valid_candidate():
    text = (
        "Cell ID,Cycle No,Step No,Voltage (V),SOC (%)\n"
        "A01,1,7,3.60,40\n"
        "A01,1,7,nan,41\n"
        "A01,1,7,3.70,42\n"
        "A01,2,7,3.80,43\n"
        "A02,1,7,3.90,44\n"
    )

    preview = preview_soc_voltages(text)

    assert preview["invalidRows"] == 1
    assert [row["row"] for row in preview["candidates"]] == [4, 5, 6]
    assert [row["voltageV"] for row in preview["candidates"]] == pytest.approx(
        [3.7, 3.8, 3.9]
    )


def test_file_size_limit_is_enforced_before_parsing():
    text = "Voltage (V)\n" + "3" * MAX_BYTES

    with pytest.raises(ValueError, match="2 MB"):
        preview_soc_voltages(text)


def test_row_limit_is_enforced():
    text = "Voltage (V)\n" + "3.7\n" * 50001

    with pytest.raises(ValueError, match="50000행"):
        preview_soc_voltages(text)


def test_candidate_limit_truncates_with_an_explicit_warning():
    text = "Voltage (V)\n" + "3.7\n" * 501

    preview = preview_soc_voltages(text)

    assert preview["rowCount"] == 501
    assert len(preview["candidates"]) == 500
    assert "앞의 500개만" in " ".join(preview["warnings"])


def test_http_preview_is_non_mutating_and_capacity_use_is_opt_in(tmp_path):
    client = _client(tmp_path)
    payload, _ = _http_payload(tmp_path)
    payload["args"]["text"] = "Voltage (V),Charge Capacity (mAh)\n3.71,20\n"
    before = deepcopy(payload["project"])

    without_reference = client.post("/api/plan/qpeedVoltage", json=payload)
    with_reference = client.post(
        "/api/plan/qpeedVoltage",
        json={
            **payload,
            "args": {**payload["args"], "useReferenceCapacity": True},
        },
    )

    assert without_reference.status_code == 200
    assert without_reference.get_json()["candidates"][0]["socPercent"] is None
    assert with_reference.status_code == 200
    assert with_reference.get_json()["candidates"][0]["socPercent"] == pytest.approx(25.0)
    assert payload["project"] == before


def test_http_apply_sets_selected_value_source_voltage_control_and_one_label(tmp_path):
    client = _client(tmp_path)
    payload, module_id = _http_payload(tmp_path)
    planned = client.post("/api/plan/qpeedVoltage", json=payload)
    assert planned.status_code == 200, planned.get_json()
    preview = planned.get_json()

    applied = client.post(
        "/api/edit/applyQpeedVoltage",
        json={
            **payload,
            "args": {
                **payload["args"],
                "token": preview["token"],
                "candidateId": preview["candidates"][0]["id"],
            },
        },
    )

    assert applied.status_code == 200, applied.get_json()
    body = applied.get_json()
    params = next(
        node["params"] for node in body["project"]["modules"] if node["id"] == module_id
    )
    source = json.loads(params["soc_voltage_source"])
    assert params["soc_control"] == "voltage"
    assert params["soc_voltage_v"] == pytest.approx(3.71)
    assert params["start_soc_percent"] == pytest.approx(42.0)
    assert source["fileName"] == "result.csv"
    assert source["voltageV"] == pytest.approx(3.71)
    assert source["socPercent"] == pytest.approx(42.0)
    assert source["textSha256"] == preview["digest"]
    assert body["label"] == f"{module_id} SOC 전압 불러오기"


def test_model_apply_is_exactly_one_undo_step(tmp_path):
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    module_id = model.add_module("qpeed", {"variant": "full", "soc_control": "capacity"})

    model.apply_qpeed_voltage(module_id, 3.71, '{"fileName":"result.csv"}', 42.0)

    assert model.document.can_undo
    assert model.document.undo_label == f"{module_id} SOC 전압 불러오기"
    assert model.document.undo() == f"{module_id} SOC 전압 불러오기"
    assert model.project.modules[0].params["soc_control"] == "capacity"
    assert model.document.undo_label == "QPEED 추가"
    assert model.document.undo() == "QPEED 추가"
    assert model.project.modules == []
    assert not model.document.can_undo
    assert model.document.undo() is None


@pytest.mark.parametrize(
    "change",
    ["text", "file_name", "params", "cell", "mapping"],
)
def test_http_apply_rejects_any_preview_bound_input_change_with_409(tmp_path, change):
    client = _client(tmp_path)
    payload, module_id = _http_payload(tmp_path)
    preview_response = client.post("/api/plan/qpeedVoltage", json=payload)
    assert preview_response.status_code == 200, preview_response.get_json()
    preview = preview_response.get_json()
    changed = deepcopy(payload)

    if change == "text":
        changed["args"]["text"] = changed["args"]["text"].replace("3.71", "3.72")
    elif change == "file_name":
        changed["args"]["fileName"] = "cycler/renamed.csv"
    elif change == "params":
        next(
            node for node in changed["project"]["modules"] if node["id"] == module_id
        )["params"]["high_rate_levels"] = 2
    elif change == "cell":
        changed["project"]["cell_profile"]["nominal_capacity_mAh"] = 81.0
    else:
        changed["args"]["mapping"] = {
            "voltageColumn": "Voltage (V)",
            "voltageUnit": "mV",
            "socColumn": "SOC (%)",
            "socUnit": "%",
        }
    changed["args"].update(
        token=preview["token"], candidateId=preview["candidates"][0]["id"]
    )

    rejected = client.post("/api/edit/applyQpeedVoltage", json=changed)

    assert rejected.status_code == 409
    assert "다시 미리보기" in rejected.get_json()["error"]


def test_http_apply_rejects_forged_candidate_id(tmp_path):
    client = _client(tmp_path)
    payload, _ = _http_payload(tmp_path)
    planned = client.post("/api/plan/qpeedVoltage", json=payload)
    assert planned.status_code == 200, planned.get_json()
    preview = planned.get_json()

    rejected = client.post(
        "/api/edit/applyQpeedVoltage",
        json={
            **payload,
            "args": {
                **payload["args"],
                "token": preview["token"],
                "candidateId": "row-forged",
            },
        },
    )

    assert rejected.status_code == 400
    assert "직접 선택" in rejected.get_json()["error"]
