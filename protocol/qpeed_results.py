"""Bounded local CSV/TSV previews; never infer SOC from voltage alone."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 50000
MAX_CANDIDATES = 500


def _normal(header: str) -> str:
    return re.sub(r"[\s_\-()\[\]％%/]", "", header).lower()


def _number(text: str) -> float:
    value = float(text.strip().replace(",", ""))
    if not math.isfinite(value):
        raise ValueError("유한한 숫자가 아닙니다.")
    return value


def preview_soc_voltages(text: str, *, mapping: dict | None = None,
                         reference_capacity_mAh: float | None = None) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("결과 파일의 내용이 비어 있습니다.")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("결과 파일은 2 MB 이하로 내보내 주세요.")
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    delimiter = "\t" if "\t" in lines[0] else ( ";" if ";" in lines[0] and "," not in lines[0] else ",")
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = reader.fieldnames or []
    if not headers or any(not header.strip() for header in headers):
        raise ValueError("열 이름이 있는 CSV/TSV 파일이 필요합니다.")
    normalized = [_normal(header) for header in headers]
    if len(set(normalized)) != len(headers):
        raise ValueError("중복된 열 이름을 먼저 구분해 주세요.")
    aliases = {
        "voltageColumn": {"voltage", "voltagev", "voltagemv", "전압", "전압v", "전압mv", "voltagevolt"},
        "socColumn": {"soc", "socfraction", "잔량", "soc비율"},
        "stepColumn": {"stepno", "step", "stepnumber", "단계", "스텝", "스텝번호"},
        "cellColumn": {"cellid", "셀id", "셀번호", "channel", "channelno", "채널"},
        "cycleColumn": {"totalcycle", "cycleno", "cyclenum", "사이클", "사이클번호"},
        "capacityColumn": {"chargecapacitymah", "충전용량mah"},
    }
    chosen = dict(mapping or {})
    for key, names in aliases.items():
        if key not in chosen:
            matches = [header for header in headers if _normal(header) in names]
            if len(matches) == 1:
                chosen[key] = matches[0]
        if chosen.get(key) and chosen[key] not in headers:
            raise ValueError(f"파일에 없는 열입니다: {chosen[key]}")
    voltage_column = chosen.get("voltageColumn")
    if not voltage_column:
        return {"ok": True, "headers": headers, "mapping": chosen, "candidates": [],
                "warnings": ["전압 열과 단위를 선택하고 다시 미리보기 하세요."], "rowCount": 0,
                "invalidRows": 0, "digest": hashlib.sha256(text.encode()).hexdigest()}
    if not chosen.get("voltageUnit"):
        norm = _normal(voltage_column)
        chosen["voltageUnit"] = "mV" if norm.endswith("mv") else ("V" if norm.endswith(("v", "volt")) else "")
    if chosen["voltageUnit"] not in {"V", "mV"}:
        return {"ok": True, "headers": headers, "mapping": chosen, "candidates": [],
                "warnings": ["전압 단위(V 또는 mV)를 명시적으로 선택하세요."], "rowCount": 0,
                "invalidRows": 0, "digest": hashlib.sha256(text.encode()).hexdigest()}
    if chosen.get("socColumn") and not chosen.get("socUnit"):
        name = chosen["socColumn"]
        chosen["socUnit"] = "%" if "%" in name or "％" in name else ("fraction" if "fraction" in _normal(name) or "비율" in name else "")
    if chosen.get("socColumn") and chosen.get("socUnit") not in {"%", "fraction"}:
        return {"ok": True, "headers": headers, "mapping": chosen, "candidates": [],
                "warnings": ["SOC 열의 단위(% 또는 0–1 비율)를 선택하세요."], "rowCount": 0,
                "invalidRows": 0, "digest": hashlib.sha256(text.encode()).hexdigest()}
    if reference_capacity_mAh is not None:
        if isinstance(reference_capacity_mAh, bool) or not math.isfinite(reference_capacity_mAh) or reference_capacity_mAh <= 0:
            raise ValueError("SOC 계산용 기준용량은 양의 유한한 mAh 값이어야 합니다.")
    groups: dict[tuple, dict] = {}
    invalid = count = 0
    for count, row in enumerate(reader, start=1):
        if count > MAX_ROWS:
            raise ValueError("50000행 이하로 결과를 나눠 내보내 주세요.")
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{count + 1}행의 열 개수가 머리글과 다릅니다.")
        try:
            voltage = _number(row[voltage_column]) / (1000 if chosen["voltageUnit"] == "mV" else 1)
            if not 0 < voltage <= 10:
                raise ValueError("셀 전압 범위가 아닙니다.")
            soc = None
            soc_basis = ""
            if chosen.get("socColumn"):
                soc = _number(row[chosen["socColumn"]]) * (100 if chosen["socUnit"] == "fraction" else 1)
                soc_basis = "파일의 SOC 열"
            elif chosen.get("capacityColumn") and reference_capacity_mAh is not None:
                # Only a qualified charge-capacity mAh column is accepted.
                if _normal(chosen["capacityColumn"]) not in aliases["capacityColumn"]:
                    raise ValueError("충전용량(mAh) 열을 명시해 주세요.")
                soc = _number(row[chosen["capacityColumn"]]) / reference_capacity_mAh * 100
                soc_basis = "충전용량 / 입력 기준용량의 명목 비율"
            if soc is not None and not 0 <= soc <= 100:
                raise ValueError("SOC 범위를 벗어났습니다.")
        except (ValueError, TypeError):
            invalid += 1
            continue
        cell = row.get(chosen.get("cellColumn"), "").strip()
        step = row.get(chosen.get("stepColumn"), "").strip()
        cycle = row.get(chosen.get("cycleColumn"), "").strip()
        key = (cell, cycle, step) if step else ("row", count)
        groups[key] = {"id": f"row-{count + 1}", "row": count + 1, "voltageV": voltage,
                       "socPercent": soc, "socBasis": soc_basis, "cellId": cell,
                       "step": step, "cycle": cycle}
    candidates = sorted(groups.values(), key=lambda item: item["row"])
    warnings = ["자동 적용하지 않습니다. SOC setting에 해당하는 셀·스텝·행을 직접 선택하세요.",
                "전압은 선택한 스텝의 마지막 유효 샘플이며 OCV 또는 실제 SOC로 자동 판정하지 않습니다."]
    if chosen.get("stepColumn") and not chosen.get("cycleColumn"):
        warnings.append("사이클 열이 없어 반복된 같은 스텝의 마지막 샘플로 묶입니다.")
    if not chosen.get("socColumn"):
        warnings.append("SOC가 없는 전압값으로 잔량을 추정하지 않습니다. 기준용량을 명시한 충전용량 열만 명목 비율 계산에 사용합니다.")
    if invalid:
        warnings.append(f"빈 값·잘못된 숫자·범위 오류 {invalid}행을 제외했습니다.")
    if len(candidates) > MAX_CANDIDATES:
        warnings.append(f"후보 {len(candidates)}개 중 앞의 {MAX_CANDIDATES}개만 표시합니다. 파일을 셀/시험별로 나눠 주세요.")
    if not candidates:
        warnings.append("사용할 수 있는 전압 행이 없습니다.")
    return {"ok": True, "headers": headers, "mapping": chosen,
            "candidates": candidates[:MAX_CANDIDATES], "rowCount": count,
            "invalidRows": invalid, "warnings": warnings,
            "digest": hashlib.sha256(text.encode()).hexdigest()}


__all__ = ["preview_soc_voltages"]
