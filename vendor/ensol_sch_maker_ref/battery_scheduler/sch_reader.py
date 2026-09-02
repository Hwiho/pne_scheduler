"""
sch_reader.py -- best-effort .sch importer for Battery Scheduler.

The importer decodes PNE CTSPro .sch step blocks and converts simple step groups
back into the current block-based schedule JSON. Complex legacy HPPC/RPT files
may contain DOD/capacity-reference steps that do not map cleanly to one current
UI block yet; those groups are preserved as simpler charge/discharge/rest blocks
with import warnings.
"""
import json
import os
import struct
import sys

HEADER_1632 = 1632
HEADER_1760 = 1760
STEP_SIZE = 612

TYPE_REST = 3
TYPE_CCCV = 0x0101
TYPE_CCCH = 0x0201
TYPE_CCDI = 0x0202
TYPE_LOOP = 8
TYPE_END = 6
TYPE_CYCMRK = 7

OFF_IDX = 0
OFF_TYPE = 8
OFF_VOLT = 12
OFF_CURR = 16
OFF_DUR = 20
OFF_VC = 28
OFF_CVCO = 32
OFF_LOOP_COUNT = 52
OFF_LOOP_RESET = 88
OFF_REC_DV = 332
OFF_REC_TIME = 340
OFF_DOD = 384
OFF_CAP_MODE = 496
OFF_CAP_REF = 497

HOFF_AUTH = 0x150
HOFF_NAME = 0x298
HOFF_SAFE = 0x3D8


def _f(buf, off):
    return struct.unpack_from("<f", buf, off)[0]


def _i(buf, off):
    return struct.unpack_from("<i", buf, off)[0]


def _round(v, digits=6):
    return round(float(v), digits)


def _minutes(seconds):
    return _round(float(seconds) / 60.0)


def _hours(seconds):
    return _round(float(seconds) / 3600.0)


def _volts(mv):
    return _round(float(mv) / 1000.0)


def _crate(ma, cap_mAh):
    if not cap_mAh:
        return _round(ma)
    return _round(float(ma) / float(cap_mAh))


def _read_str(data, offset, maxlen=128):
    raw = data[offset:offset + maxlen]
    end = raw.find(b"\x00")
    if end >= 0:
        raw = raw[:end]
    for enc in ("cp949", "utf-8", "ascii"):
        try:
            return raw.decode(enc).strip()
        except Exception:
            pass
    return raw.decode("ascii", errors="replace").strip()


def detect_header_size(data):
    candidates = []
    for header_size in (HEADER_1632, HEADER_1760):
        if len(data) >= header_size and (len(data) - header_size) % STEP_SIZE == 0:
            candidates.append(header_size)
    if not candidates:
        raise ValueError("Unsupported .sch size: cannot align header and 612-byte steps")
    if HEADER_1760 in candidates and HEADER_1632 not in candidates:
        return HEADER_1760
    return HEADER_1632


def decode_header(data):
    safety = {}
    if len(data) >= HOFF_SAFE + 24:
        safety = {
            "max_voltage_V": _volts(_f(data, HOFF_SAFE + 0)),
            "min_voltage_V": _volts(_f(data, HOFF_SAFE + 4)),
            "max_current_mA": _round(_f(data, HOFF_SAFE + 8)),
            "min_current_mA": _round(_f(data, HOFF_SAFE + 12)),
            "max_capacity_mAh": _round(_f(data, HOFF_SAFE + 16)),
            "max_temp_C": _round(_f(data, HOFF_SAFE + 20)),
        }
    name = _read_str(data, HOFF_NAME, 128)
    if name.lower().endswith(".sch"):
        name = name[:-4]
    return {
        "schedule_name": name or "ImportedSchedule",
        "author": _read_str(data, HOFF_AUTH, 128) or "imported",
        "safety": safety,
    }


def decode_step(block):
    step_type = _i(block, OFF_TYPE) & 0xFFFF
    step = {
        "step_num": _i(block, OFF_IDX),
        "type_code": step_type,
        "record_time_s": _round(_f(block, OFF_REC_TIME)),
        "voltage_change_mV": _round(_f(block, OFF_REC_DV)),
        "cap_mode": int(block[OFF_CAP_MODE]),
        "cap_ref_step": int(block[OFF_CAP_REF]),
        "dod_pct": _round(_f(block, OFF_DOD)),
    }
    if step_type == TYPE_REST:
        step["kind"] = "rest"
        step["duration_s"] = _round(_f(block, OFF_DUR))
    elif step_type == TYPE_CCCV:
        step["kind"] = "cccv"
        step["voltage_V"] = _volts(_f(block, OFF_VOLT))
        step["current_mA"] = _round(_f(block, OFF_CURR))
        step["time_limit_h"] = _hours(_f(block, OFF_DUR))
        step["cv_cutoff_mA"] = _round(_f(block, OFF_CVCO))
    elif step_type == TYPE_CCCH:
        step["kind"] = "cc_charge"
        step["voltage_V"] = _volts(_f(block, OFF_VOLT))
        step["voltage_cutoff_V"] = _volts(_f(block, OFF_VC))
        step["current_mA"] = _round(_f(block, OFF_CURR))
        step["time_limit_h"] = _hours(_f(block, OFF_DUR))
    elif step_type == TYPE_CCDI:
        step["kind"] = "cc_discharge"
        step["voltage_cutoff_V"] = _volts(_f(block, OFF_VC))
        step["current_mA"] = _round(_f(block, OFF_CURR))
        step["time_limit_h"] = _hours(_f(block, OFF_DUR))
    elif step_type == TYPE_LOOP:
        step["kind"] = "loop"
        step["count"] = _i(block, OFF_LOOP_COUNT)
        step["reset_capacity"] = bool(block[OFF_LOOP_RESET])
    elif step_type == TYPE_CYCMRK:
        step["kind"] = "cycle_marker"
    elif step_type == TYPE_END:
        step["kind"] = "end"
    else:
        step["kind"] = "unknown"
    return step


def decode_sch(data):
    header_size = detect_header_size(data)
    steps = []
    for idx in range((len(data) - header_size) // STEP_SIZE):
        base = header_size + idx * STEP_SIZE
        steps.append(decode_step(data[base:base + STEP_SIZE]))
    meta = decode_header(data)
    meta["header_size"] = header_size
    return meta, steps


def split_loop_groups(steps):
    groups = []
    current = []
    for step in steps:
        kind = step["kind"]
        if kind == "end":
            break
        if kind == "cycle_marker":
            if current and current[-1]["kind"] != "loop":
                current.append(step)
            else:
                current = [step]
            continue
        current.append(step)
        if kind == "loop":
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _content_steps(group):
    return [s for s in group if s["kind"] not in ("cycle_marker", "loop")]


def _loop_step(group):
    loops = [s for s in group if s["kind"] == "loop"]
    return loops[-1] if loops else {"count": 1, "reset_capacity": False}


def _base_record_params(step):
    return {
        "record_time_s": step.get("record_time_s", 30) or 30,
        "voltage_change_mV": step.get("voltage_change_mV", 0),
    }


def _rest_params(step):
    params = _base_record_params(step)
    params["duration_min"] = _minutes(step.get("duration_s", 0))
    return params


def _charge_params(charge, rest, loop, cap_mAh):
    charge_voltage = charge.get("voltage_V", charge.get("voltage_cutoff_V", 4.2))
    if charge["kind"] == "cc_charge" and charge.get("voltage_cutoff_V", 0) > 0 and charge_voltage >= 5.0:
        charge_voltage = charge["voltage_cutoff_V"]
    params = _base_record_params(charge)
    params.update({
        "count": loop.get("count", 1),
        "charge_mode": "cccv" if charge["kind"] == "cccv" else "cc",
        "charge_c_rate": _crate(charge.get("current_mA", 0), cap_mAh),
        "charge_voltage_V": charge_voltage,
        "time_limit_h": charge.get("time_limit_h", 48),
        "rest_min": _minutes(rest.get("duration_s", 0)) if rest else 0,
    })
    if charge["kind"] == "cccv":
        params["cv_cutoff_c"] = _crate(charge.get("cv_cutoff_mA", 0), cap_mAh)
    else:
        params["cv_cutoff_c"] = 0.05
    return params


def _discharge_params(discharge, rest, loop, cap_mAh):
    params = _base_record_params(discharge)
    params.update({
        "count": loop.get("count", 1),
        "discharge_c_rate": _crate(discharge.get("current_mA", 0), cap_mAh),
        "discharge_voltage_V": discharge.get("voltage_cutoff_V", 2.5),
        "rest_min": _minutes(rest.get("duration_s", 0)) if rest else 0,
    })
    return params


def _capacity_check_params(parts, cap_mAh):
    charge, rest_ch, discharge, rest_di = parts
    params = _base_record_params(charge)
    params.update({
        "charge_c_rate": _crate(charge.get("current_mA", 0), cap_mAh),
        "charge_voltage_V": charge.get("voltage_V", 4.2),
        "cv_cutoff_c": _crate(charge.get("cv_cutoff_mA", 0), cap_mAh),
        "time_limit_h": charge.get("time_limit_h", 48),
        "discharge_c_rate": _crate(discharge.get("current_mA", 0), cap_mAh),
        "discharge_voltage_V": discharge.get("voltage_cutoff_V", 2.5),
        "rest_after_charge_min": _minutes(rest_ch.get("duration_s", 0)),
        "rest_after_discharge_min": _minutes(rest_di.get("duration_s", 0)),
    })
    return params


def group_to_blocks(group, block_num, cap_mAh):
    parts = _content_steps(group)
    loop = _loop_step(group)
    kinds = [p["kind"] for p in parts]
    warnings = []
    blocks = []

    if kinds == ["rest"]:
        blocks.append({"id": f"imp_{block_num}", "type": "rest", "params": _rest_params(parts[0])})
        return blocks, warnings

    if kinds == ["cccv", "rest", "cc_discharge", "rest"]:
        blocks.append({
            "id": f"imp_{block_num}",
            "type": "capacity_check",
            "params": _capacity_check_params(parts, cap_mAh),
        })
        return blocks, warnings

    if kinds in (["cccv", "rest"], ["cc_charge", "rest"]):
        blocks.append({
            "id": f"imp_{block_num}",
            "type": "charge",
            "params": _charge_params(parts[0], parts[1], loop, cap_mAh),
        })
        return blocks, warnings

    if kinds == ["cc_discharge", "rest"]:
        if parts[0].get("dod_pct", 0):
            warnings.append(
                f"group {block_num}: DOD discharge step was imported as a plain discharge block"
            )
        blocks.append({
            "id": f"imp_{block_num}",
            "type": "discharge",
            "params": _discharge_params(parts[0], parts[1], loop, cap_mAh),
        })
        return blocks, warnings

    if kinds == ["cc_discharge", "rest", "cc_charge", "rest"]:
        if parts[0].get("dod_pct", 0) or parts[2].get("dod_pct", 0):
            warnings.append(
                f"group {block_num}: capacity-reference pulse/return group was split into discharge and charge blocks"
            )
        blocks.append({
            "id": f"imp_{block_num}_a",
            "type": "discharge",
            "params": _discharge_params(parts[0], parts[1], {"count": 1}, cap_mAh),
        })
        blocks.append({
            "id": f"imp_{block_num}_b",
            "type": "charge",
            "params": _charge_params(parts[2], parts[3], {"count": loop.get("count", 1)}, cap_mAh),
        })
        return blocks, warnings

    warnings.append(f"group {block_num}: unsupported pattern {kinds}")
    for offset, part in enumerate(parts):
        if part["kind"] == "rest":
            blocks.append({"id": f"imp_{block_num}_{offset}", "type": "rest", "params": _rest_params(part)})
        elif part["kind"] in ("cccv", "cc_charge"):
            blocks.append({
                "id": f"imp_{block_num}_{offset}",
                "type": "charge",
                "params": _charge_params(part, None, {"count": 1}, cap_mAh),
            })
        elif part["kind"] == "cc_discharge":
            blocks.append({
                "id": f"imp_{block_num}_{offset}",
                "type": "discharge",
                "params": _discharge_params(part, None, {"count": 1}, cap_mAh),
            })
    return blocks, warnings


def sch_to_schedule(data, cell_capacity_mAh=100.0):
    meta, steps = decode_sch(data)
    groups = split_loop_groups(steps)
    blocks = []
    warnings = []
    for idx, group in enumerate(groups, start=1):
        new_blocks, new_warnings = group_to_blocks(group, idx, cell_capacity_mAh)
        blocks.extend(new_blocks)
        warnings.extend(new_warnings)
    safety = meta.get("safety") or {}
    if not safety or all(v == 0 for v in safety.values()):
        safety = {
            "max_voltage_V": 4.3,
            "min_voltage_V": 0.0,
            "max_current_mA": 0.0,
            "min_current_mA": 0.0,
            "max_capacity_mAh": cell_capacity_mAh * 2,
            "max_temp_C": 70.0,
        }
    return {
        "schedule_name": meta.get("schedule_name") or "ImportedSchedule",
        "cell_capacity_mAh": cell_capacity_mAh,
        "author": meta.get("author") or "imported",
        "safety": safety,
        "blocks": blocks,
        "_import": {
            "header_size": meta.get("header_size"),
            "step_count": len([s for s in steps if s["kind"] != "end"]),
            "group_count": len(groups),
            "warnings": warnings,
        },
    }


def sch_file_to_schedule(input_path, output_path=None, cell_capacity_mAh=100.0):
    with open(input_path, "rb") as f:
        schedule = sch_to_schedule(f.read(), cell_capacity_mAh=cell_capacity_mAh)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
    return schedule


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sch_reader.py <input.sch> [output.json] [cell_capacity_mAh]")
        sys.exit(1)
    output = None
    capacity = 100.0
    if len(sys.argv) >= 3:
        try:
            capacity = float(sys.argv[2])
        except ValueError:
            output = sys.argv[2]
    if len(sys.argv) >= 4:
        capacity = float(sys.argv[3])
    result = sch_file_to_schedule(sys.argv[1], output, capacity)
    if output:
        print("[Reader] %s -> %s" % (sys.argv[1], output))
        warnings = result.get("_import", {}).get("warnings", [])
        if warnings:
            print("[Reader] warnings: %d" % len(warnings))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
