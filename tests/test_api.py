"""G1 — the HTTP surface, and the safety properties it must not weaken."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

pytest.importorskip("flask")

from pne_scheduler.api.app import SessionRegistry, create_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "example" / "example.schproj"
SCH = (
    ROOT / "example" / "fixtures" / "capacheck_zip"
    / "07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch"
)


@pytest.fixture()
def client(tmp_path):
    logging.disable(logging.CRITICAL)
    yield create_app(tmp_path / "library").test_client()
    logging.disable(logging.NOTSET)


@pytest.fixture()
def project() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


# --- the safety properties --------------------------------------------------


def test_an_out_of_range_edit_saves_but_closes_every_export_gate(client, project):
    """Saving is never blocked; only export is. The API must not change that."""
    response = client.post(
        "/api/edit/setParam",
        json={
            "project": project,
            "args": {"moduleId": "formation_1", "key": "charge_c_rate", "text": "999C"},
        },
    )
    assert response.status_code == 200, "a bad value must still be storable"

    views = response.get_json()["views"]
    assert [row["code"] for row in views["validation"] if row["severity"] == "error"]

    allowed = {o["kind"] for o in views["release"]["options"] if o["allowed"]}
    assert allowed == {"draft_save"}
    assert views["release"]["label"]["label"] == "analysis-only"
    assert views["release"]["label"]["equipmentExecutable"] is False


def test_the_client_is_never_asked_to_decide_a_gate(client, project):
    """Every gate arrives as a computed decision with its reasons attached."""
    views = client.post("/api/views", json={"project": project}).get_json()["views"]
    for option in views["release"]["options"]:
        assert isinstance(option["allowed"], bool)
        if not option["allowed"]:
            assert option["blockers"] or option["nextAction"]
    assert views["release"]["label"]["reasons"] or views["release"]["label"]["label"]


def test_the_recommended_export_is_the_patch_path(client, project):
    views = client.post("/api/views", json={"project": project}).get_json()["views"]
    recommended = [o["kind"] for o in views["release"]["options"] if o["recommended"]]
    assert recommended == ["template_patch"]


# --- statelessness ----------------------------------------------------------

def test_the_server_keeps_nothing_between_edits(client, project):
    """Two edits from the same starting project must not compound."""
    first = client.post(
        "/api/edit/addModule", json={"project": project, "args": {"moduleType": "rest"}}
    ).get_json()
    second = client.post(
        "/api/edit/addModule", json={"project": project, "args": {"moduleType": "rest"}}
    ).get_json()
    assert len(first["project"]["modules"]) == len(second["project"]["modules"])


def test_an_edit_reports_the_label_for_the_client_history(client, project):
    body = client.post(
        "/api/edit/addModule", json={"project": project, "args": {"moduleType": "rest"}}
    ).get_json()
    assert body["label"] == "Rest 추가"


# --- plan is not transform --------------------------------------------------


def test_planning_a_campaign_changes_nothing(client, project):
    body = client.post(
        "/api/plan/campaign",
        json={"project": project, "args": {"totalCycles": 150, "rptEvery": 50,
                                           "chargeCRate": 0.5, "dischargeCRate": 0.5}},
    ).get_json()
    assert body["ok"] and len(body["blocks"]) == 7
    assert "project" not in body


def test_a_plan_carries_the_warnings_that_must_be_read_first(client, project):
    body = client.post(
        "/api/plan/campaign",
        json={"project": project, "args": {"totalCycles": 50, "chargeCRate": 0.5,
                                           "dischargeCRate": 0.5}},
    ).get_json()
    joined = " ".join(body["warnings"])
    assert "기록되지 않습니다" in joined and "prototype" in joined


def test_applying_produces_exactly_what_the_preview_described(client, project):
    args = {"totalCycles": 150, "rptEvery": 50, "chargeCRate": 0.5, "dischargeCRate": 0.5}
    preview = client.post("/api/plan/campaign", json={"project": project, "args": args})
    applied = client.post("/api/edit/addCampaign", json={"project": project, "args": args})

    blocks = preview.get_json()["blocks"]
    modules = applied.get_json()["project"]["modules"]
    assert len(modules) == len(project["modules"]) + len(blocks)
    assert [m["module_type"] for m in modules[len(project["modules"]):]] == [
        b["moduleType"] for b in blocks
    ]


# --- refusals ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url, body, status",
    [
        ("/api/views", {}, 400),
        ("/api/edit/nope", {"project": {}, "args": {}}, 404),
        ("/api/plan/nope", {"project": {}, "args": {}}, 404),
        ("/api/import/deadbeef/plan", {}, 404),
        ("/api/import/open", {"path": "/no/such.sch"}, 400),
    ],
)
def test_every_refusal_is_json_with_a_reason(client, url, body, status):
    response = client.post(url, json=body)
    assert response.status_code == status
    payload = response.get_json()
    assert payload["ok"] is False and payload["error"]


def test_a_missing_argument_names_itself(client, project):
    body = client.post(
        "/api/edit/addModule", json={"project": project, "args": {}}
    ).get_json()
    assert body["ok"] is False and "moduleType" in body["error"]


# --- local resources --------------------------------------------------------


def test_a_method_round_trips_through_the_library(client, project):
    saved = client.post(
        "/api/library", json={"project": project, "name": "왕복"}
    ).get_json()
    assert saved["method"]["moduleCount"] == len(project["modules"])

    listing = client.get("/api/library").get_json()
    assert [m["name"] for m in listing["methods"]] == ["왕복"]

    empty = dict(project, modules=[])
    loaded = client.post(
        "/api/library/load",
        json={"project": empty, "methodId": saved["method"]["methodId"]},
    ).get_json()
    assert len(loaded["project"]["modules"]) == len(project["modules"])
    assert loaded["warnings"], "loading must still say that saved is not verified"


def test_an_import_session_offers_only_proven_fields(client):
    opened = client.post("/api/import/open", json={"path": str(SCH)}).get_json()
    session_id = opened["sessionId"]
    assert opened["stepCount"] > 0
    assert all(field["evidence"] for field in opened["editableFields"])

    good = client.post(
        f"/api/import/{session_id}/stage",
        json={"stepNo": 3, "field": "fVref", "value": 25.0},
    ).get_json()
    assert len(good["accepted"]) == 1 and good["plan"]["template_sha256"] == opened["sha256"]

    bad = client.post(
        f"/api/import/{session_id}/stage",
        json={"stepNo": 3, "field": "unproven_offset", "value": 1.0},
    ).get_json()
    assert [r["field"] for r in bad["rejected"]] == ["unproven_offset"]


def test_import_sessions_expire_rather_than_pinning_lab_bytes():
    from pne_scheduler.import_session import ImportSession

    registry = SessionRegistry(ttl=-1)
    key = registry.add(ImportSession.open(SCH))
    from pne_scheduler.api.errors import ApiError

    with pytest.raises(ApiError):
        registry.get(key)


def test_the_registry_is_bounded():
    from pne_scheduler.import_session import ImportSession

    registry = SessionRegistry(limit=2)
    keys = [registry.add(ImportSession.open(SCH)) for _ in range(4)]
    alive = 0
    for key in keys:
        try:
            registry.get(key)
            alive += 1
        except Exception:
            pass
    assert alive <= 2


# --- G3: export goes through the gate, never around it ----------------------


def test_a_preview_export_writes_its_files(client, project, tmp_path):
    body = client.post(
        "/api/export",
        json={"project": project, "kind": "preview", "outDir": str(tmp_path)},
    ).get_json()
    assert body["ok"]
    names = {Path(p).name for p in body["paths"]}
    assert {"steps.csv", "summary.txt"} <= names
    assert all(Path(p).exists() for p in body["paths"])


def test_a_blocked_export_is_refused_with_the_blockers(client, project, tmp_path):
    """`exporting` re-checks the ladder itself; the route only names the failure."""
    broken = client.post(
        "/api/edit/setParam",
        json={
            "project": project,
            "args": {"moduleId": "formation_1", "key": "charge_c_rate", "text": "999C"},
        },
    ).get_json()["project"]

    response = client.post(
        "/api/export",
        json={"project": broken, "kind": "preview", "outDir": str(tmp_path)},
    )
    assert response.status_code == 409
    assert "잠겨" in response.get_json()["error"]
    assert not list(tmp_path.iterdir()), "a blocked export must write nothing"


@pytest.mark.parametrize("kind", ["equipment_export", "template_patch"])
def test_the_dangerous_paths_are_not_reachable_by_one_post(client, project, tmp_path, kind):
    """Template patch needs a real CTSPro file; equipment-ready needs recorded
    human approval. Neither belongs behind a single HTTP call."""
    response = client.post(
        "/api/export", json={"project": project, "kind": kind, "outDir": str(tmp_path)}
    )
    assert response.status_code == 404


def test_a_missing_output_directory_is_refused_before_anything_runs(client, project):
    response = client.post(
        "/api/export",
        json={"project": project, "kind": "preview", "outDir": "/no/such/dir"},
    )
    assert response.status_code == 400
    assert "출력 폴더가 없습니다" in response.get_json()["error"]
