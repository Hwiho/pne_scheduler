"""
sch_core.py  -- binary .sch writer for block-based schedules
All comments in English to avoid encoding issues in cp949 environments.
"""
import struct
from datetime import datetime

MAGIC        = b"\x71\x4d\x0b\x00\x02\x00\x01\x00"
HEADER_SIZE  = 1632
STEP_SIZE    = 612
FILE_SIG     = b"PNE CTSPro Schedule File."
TYPE_REST    = 3
TYPE_CCCV    = 0x0101
TYPE_CCCh    = 0x0201
TYPE_CCDi    = 0x0202
TYPE_LOOP    = 8
TYPE_END     = 6
TYPE_CYCLE   = 7

OFF_IDX   = 0
OFF_TYPE  = 8
OFF_CCVV  = 12
OFF_VLIM  = 12
OFF_CCI   = 16
OFF_CCTL  = 20
OFF_VC    = 28
OFF_CVCO  = 32
OFF_CNT   = 52
OFF_RDVLT = 332
OFF_RTIME = 340
OFF_DOD   = 384
OFF_F496  = 496
OFF_GOTO  = 564

HOFF_SIG  = 0x48
HOFF_AUTH = 0x150
HOFF_TS2  = 0x250
HOFF_NAME = 0x298
HOFF_TS3  = 0x398
HOFF_SAFE = 0x3D8

CCDI_VLIM_DEFAULT = 2000.0


def pf(b, o, v):
    struct.pack_into("<f", b, o, float(v))

def pi(b, o, v):
    struct.pack_into("<i", b, o, int(v))

def _set_cap_flag(b, mode_byte, ref_step_num):
    b[OFF_F496]   = mode_byte
    b[OFF_F496+1] = int(ref_step_num)

def crate_to_mA(c_rate, cap_mAh):
    return float(c_rate) * float(cap_mAh)


def blk_rest(idx, dur_s, rec_s=30.0, dv_mV=10.0):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_REST)
    pf(b, OFF_CCTL, dur_s)
    pf(b, OFF_RDVLT, dv_mV); pf(b, OFF_RTIME, rec_s)
    b[OFF_F496] = 0x01
    return bytes(b)

def blk_cccv(idx, volt_mV, curr_mA, tl_s, cv_mA, rec_s=30.0, dv_mV=10.0):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_CCCV)
    pf(b, OFF_CCVV, volt_mV); pf(b, OFF_CCI, curr_mA)
    pf(b, OFF_CCTL, tl_s); pf(b, OFF_CVCO, cv_mA)
    pf(b, OFF_RDVLT, dv_mV); pf(b, OFF_RTIME, rec_s)
    b[OFF_F496] = 0x01
    return bytes(b)

def blk_ccc(idx, volt_mV, curr_mA, tl_s, rec_s=30.0, dv_mV=10.0):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_CCCh)
    pf(b, OFF_CCVV, volt_mV); pf(b, OFF_CCI, curr_mA)
    pf(b, OFF_CCTL, tl_s)
    pf(b, OFF_RDVLT, dv_mV); pf(b, OFF_RTIME, rec_s)
    b[OFF_F496] = 0x01
    return bytes(b)

def blk_ccc_return(idx, volt_mV, curr_mA, ref_step_num, rec_s=30.0, dv_mV=10.0):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_CCCh)
    pf(b, OFF_CCVV, volt_mV); pf(b, OFF_CCI, curr_mA)
    pf(b, OFF_CCTL, 172800.0)
    pf(b, OFF_RDVLT, dv_mV); pf(b, OFF_RTIME, rec_s)
    pf(b, OFF_DOD, 100.0)
    _set_cap_flag(b, 0x00, ref_step_num)
    return bytes(b)

def blk_ccdi(idx, curr_mA, vc_mV, tl_s=0.0, rec_s=30.0, dv_mV=10.0):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_CCDi)
    pf(b, OFF_VLIM, CCDI_VLIM_DEFAULT); pf(b, OFF_CCI, curr_mA)
    pf(b, OFF_CCTL, tl_s if tl_s > 0 else 172800.0)
    pf(b, OFF_VC, vc_mV)
    pf(b, OFF_RDVLT, dv_mV); pf(b, OFF_RTIME, rec_s)
    b[OFF_F496] = 0x01
    return bytes(b)

def blk_ccdi_dod(idx, curr_mA, vc_mV, dod_pct, ref_step_num, rec_s=30.0, dv_mV=10.0):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_CCDi)
    pf(b, OFF_VLIM, CCDI_VLIM_DEFAULT); pf(b, OFF_CCI, curr_mA)
    pf(b, OFF_CCTL, 172800.0)
    pf(b, OFF_VC, vc_mV)
    pf(b, OFF_RDVLT, dv_mV); pf(b, OFF_RTIME, rec_s)
    pf(b, OFF_DOD, dod_pct)
    _set_cap_flag(b, 0x01, ref_step_num)
    return bytes(b)

def blk_marker(idx):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_CYCLE)
    return bytes(b)

def blk_loop(idx, count, reset_cap=False):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_LOOP)
    pi(b, OFF_CNT, count)
    if reset_cap:
        b[88] = 1
    pi(b, OFF_GOTO, 1)
    return bytes(b)

def blk_end(idx):
    b = bytearray(STEP_SIZE)
    pi(b, OFF_IDX, idx); pi(b, OFF_TYPE, TYPE_END)
    return bytes(b)


def make_header(name, safety, author="user"):
    h = bytearray(HEADER_SIZE)
    h[0:8] = MAGIC
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.000").encode("ascii")
    h[0x08:0x08+len(ts)] = ts
    h[HOFF_SIG:HOFF_SIG+len(FILE_SIG)] = FILE_SIG
    try:
        ab = author.encode("cp949")[:60]
    except Exception:
        ab = author.encode("ascii", errors="replace")[:60]
    h[HOFF_AUTH:HOFF_AUTH+len(ab)] = ab
    h[HOFF_TS2:HOFF_TS2+len(ts)]   = ts
    fn = (name + ".sch").encode("cp949", errors="replace")[:100]
    h[0x290] = 1; h[0x294] = 2
    h[HOFF_NAME:HOFF_NAME+len(fn)] = fn
    h[HOFF_TS3:HOFF_TS3+len(ts)] = ts
    so = HOFF_SAFE
    struct.pack_into("<f", h, so+0,  safety.get("max_voltage_V",   4.3) * 1000)
    struct.pack_into("<f", h, so+4,  safety.get("min_voltage_V",   0.0) * 1000)
    struct.pack_into("<f", h, so+8,  safety.get("max_current_mA",  0.0))
    struct.pack_into("<f", h, so+12, safety.get("min_current_mA",  0.0))
    struct.pack_into("<f", h, so+16, safety.get("max_capacity_mAh", 200.0))
    struct.pack_into("<f", h, so+20, safety.get("max_temp_C",      70.0))
    struct.pack_into("<i", h, 0x404, 7)
    return bytes(h)


def expand_rest(p, cap, start_idx, _ctx=None):
    """CYCMRK -> REST -> LOOP(1)."""
    dur_s  = p.get("duration_min", 30) * 60
    rec_s  = p.get("record_time_s", 30)
    dv_mV  = p.get("voltage_change_mV", 10.0)
    idx    = start_idx
    blocks = []
    blocks.append(blk_marker(idx)); idx += 1
    blocks.append(blk_rest(idx, dur_s, rec_s, dv_mV)); idx += 1
    blocks.append(blk_loop(idx, 1)); idx += 1
    return blocks, idx


def expand_capacity_check(p, cap, start_idx, _ctx=None):
    """CYCMRK -> CCCV charge -> REST -> CC discharge -> REST -> LOOP(1,reset)."""
    blocks = []
    idx    = start_idx
    rec_s  = p.get("record_time_s", 30)
    dv_mV  = p.get("voltage_change_mV", 10.0)
    tl_s   = p.get("time_limit_h", 48) * 3600
    ch_v   = p.get("charge_voltage_V",   4.2) * 1000
    ch_mA  = crate_to_mA(p.get("charge_c_rate", 0.1), cap)
    cv_mA  = crate_to_mA(p.get("cv_cutoff_c",   0.05), cap)
    di_mA  = crate_to_mA(p.get("discharge_c_rate", 0.1), cap)
    di_vc  = p.get("discharge_voltage_V", 2.5) * 1000
    rc_s   = p.get("rest_after_charge_min",    30) * 60
    rd_s   = p.get("rest_after_discharge_min", 30) * 60

    blocks.append(blk_marker(idx)); idx += 1
    blocks.append(blk_cccv(idx, ch_v, ch_mA, tl_s, cv_mA, rec_s, dv_mV)); idx += 1
    blocks.append(blk_rest(idx, rc_s, rec_s, dv_mV)); idx += 1
    blocks.append(blk_ccdi(idx, di_mA, di_vc, rec_s=rec_s, dv_mV=dv_mV)); idx += 1
    capa_ref_rest_step = idx
    blocks.append(blk_rest(idx, rd_s, rec_s, dv_mV)); idx += 1
    blocks.append(blk_loop(idx, 1, reset_cap=True)); idx += 1
    return blocks, idx, capa_ref_rest_step


def _resolve_capa_ref(p, ctx):
    """Return capa_ref_step from explicit block id or latest."""
    if ctx is None:
        return 0
    ref_id  = p.get("capacity_ref_block_id", "")
    ref_map = ctx.get("capa_ref_map", {})
    if ref_id and ref_id in ref_map:
        return ref_map[ref_id]
    return ctx.get("capa_ref_step", 0)


def expand_soc_setting(p, cap, start_idx, _ctx=None):
    """CCCV full charge -> REST -> DOD discharge -> REST -> REST(stabilize)."""
    blocks = []
    idx    = start_idx
    rec_s  = p.get("record_time_s", 30)
    dv_mV  = p.get("voltage_change_mV", 10.0)
    tl_s   = p.get("time_limit_h", 48) * 3600
    soc    = p.get("target_soc_percent", 50)
    c_rate = p.get("c_rate", 0.2)
    curr   = crate_to_mA(c_rate, cap)
    ch_v   = p.get("charge_voltage_V",   4.2) * 1000
    di_vc  = p.get("discharge_voltage_V", 2.5) * 1000
    cv_mA  = crate_to_mA(p.get("cv_cutoff_c", 0.05), cap)
    rest_s = p.get("rest_min", 30) * 60
    capa_ref = _resolve_capa_ref(p, _ctx)

    blocks.append(blk_cccv(idx, ch_v, curr, tl_s, cv_mA, rec_s, dv_mV)); idx += 1
    blocks.append(blk_rest(idx, rest_s, rec_s, dv_mV)); idx += 1

    if capa_ref > 0:
        dod = 100.0 - soc
        blocks.append(blk_marker(idx)); idx += 1
        blocks.append(blk_ccdi_dod(idx, curr, di_vc, dod, capa_ref, rec_s, dv_mV)); idx += 1
        blocks.append(blk_rest(idx, rest_s, rec_s, dv_mV)); idx += 1
        blocks.append(blk_loop(idx, 1)); idx += 1
    else:
        step_pct = (100 - soc) / 100.0
        di_tl_s  = (step_pct / c_rate) * 3600
        blocks.append(blk_ccdi(idx, curr, di_vc, tl_s=di_tl_s, rec_s=rec_s, dv_mV=dv_mV)); idx += 1
        blocks.append(blk_rest(idx, rest_s, rec_s, dv_mV)); idx += 1

    blocks.append(blk_rest(idx, rest_s, rec_s, dv_mV)); idx += 1
    return blocks, idx


def expand_charge(p, cap, start_idx, _ctx=None):
    """CYCMRK -> charge (CCCV or CC) -> REST -> LOOP(count)."""
    blocks  = []
    idx     = start_idx
    count   = p.get("count", 1)
    rec_s   = p.get("record_time_s", 30)
    dv_mV   = p.get("voltage_change_mV", 10.0)
    tl_s    = p.get("time_limit_h", 48) * 3600
    ch_v    = p.get("charge_voltage_V",  4.2) * 1000
    ch_mA   = crate_to_mA(p.get("charge_c_rate", 0.5), cap)
    cv_mA   = crate_to_mA(p.get("cv_cutoff_c",   0.05), cap)
    rest_s  = p.get("rest_min", 30) * 60
    ch_mode = p.get("charge_mode", "cccv")

    blocks.append(blk_marker(idx)); idx += 1
    if ch_mode == "cc":
        blocks.append(blk_ccc(idx, ch_v, ch_mA, tl_s, rec_s, dv_mV)); idx += 1
    else:
        blocks.append(blk_cccv(idx, ch_v, ch_mA, tl_s, cv_mA, rec_s, dv_mV)); idx += 1
    blocks.append(blk_rest(idx, rest_s, rec_s, dv_mV)); idx += 1
    blocks.append(blk_loop(idx, count)); idx += 1
    return blocks, idx


def expand_discharge(p, cap, start_idx, _ctx=None):
    """CYCMRK -> CC discharge -> REST -> LOOP(count)."""
    blocks = []
    idx    = start_idx
    count  = p.get("count", 1)
    rec_s  = p.get("record_time_s", 30)
    dv_mV  = p.get("voltage_change_mV", 10.0)
    di_mA  = crate_to_mA(p.get("discharge_c_rate", 0.5), cap)
    di_vc  = p.get("discharge_voltage_V", 2.5) * 1000
    rest_s = p.get("rest_min", 30) * 60

    blocks.append(blk_marker(idx)); idx += 1
    blocks.append(blk_ccdi(idx, di_mA, di_vc, rec_s=rec_s, dv_mV=dv_mV)); idx += 1
    blocks.append(blk_rest(idx, rest_s, rec_s, dv_mV)); idx += 1
    blocks.append(blk_loop(idx, count)); idx += 1
    return blocks, idx


def expand_cycle(p, cap, start_idx, _ctx=None):
    """CYCMRK -> charge -> REST -> discharge -> REST -> LOOP(N)."""
    blocks  = []
    idx     = start_idx
    count   = p.get("count", 1)
    rec_s   = p.get("record_time_s", 30)
    dv_mV   = p.get("voltage_change_mV", 10.0)
    tl_s    = p.get("time_limit_h", 48) * 3600
    ch_v    = p.get("charge_voltage_V",   4.2) * 1000
    ch_mA   = crate_to_mA(p.get("charge_c_rate", 0.5), cap)
    di_mA   = crate_to_mA(p.get("discharge_c_rate", 0.5), cap)
    di_vc   = p.get("discharge_voltage_V", 2.5) * 1000
    rc_s    = p.get("rest_after_charge_min",    30) * 60
    rd_s    = p.get("rest_after_discharge_min", 30) * 60
    ch_mode = p.get("charge_mode", "cccv")
    cv_mA   = crate_to_mA(p.get("cv_cutoff_c", 0.05), cap)

    blocks.append(blk_marker(idx)); idx += 1
    if ch_mode == "cc":
        blocks.append(blk_ccc(idx, ch_v, ch_mA, tl_s, rec_s, dv_mV)); idx += 1
    else:
        blocks.append(blk_cccv(idx, ch_v, ch_mA, tl_s, cv_mA, rec_s, dv_mV)); idx += 1
    blocks.append(blk_rest(idx, rc_s, rec_s, dv_mV)); idx += 1
    blocks.append(blk_ccdi(idx, di_mA, di_vc, rec_s=rec_s, dv_mV=dv_mV)); idx += 1
    blocks.append(blk_rest(idx, rd_s, rec_s, dv_mV)); idx += 1
    blocks.append(blk_loop(idx, count)); idx += 1
    return blocks, idx


def expand_rate_test(p, cap, start_idx, _ctx=None):
    """Rate Test: CC charge only. Multiple C-rate groups."""
    blocks  = []
    idx     = start_idx
    rec_s   = p.get("record_time_s", 30)
    dv_mV   = p.get("voltage_change_mV", 10.0)
    tl_s    = p.get("time_limit_h", 48) * 3600
    ch_v    = p.get("charge_voltage_V",   4.2) * 1000
    di_vc   = p.get("discharge_voltage_V", 2.5) * 1000
    rc_s    = p.get("rest_after_charge_min",    30) * 60
    rd_s    = p.get("rest_after_discharge_min", 30) * 60
    c_rates = p.get("c_rates", [])

    for group in c_rates:
        cr    = group["c_rate"]
        cnt   = group.get("count", 1)
        di_cr = group.get("discharge_c_rate", cr)
        ch_mA = crate_to_mA(cr, cap)
        di_mA = crate_to_mA(di_cr, cap)
        blocks.append(blk_marker(idx)); idx += 1
        blocks.append(blk_ccc(idx, ch_v, ch_mA, tl_s, rec_s, dv_mV)); idx += 1
        blocks.append(blk_rest(idx, rc_s, rec_s, dv_mV)); idx += 1
        blocks.append(blk_ccdi(idx, di_mA, di_vc, rec_s=rec_s, dv_mV=dv_mV)); idx += 1
        blocks.append(blk_rest(idx, rd_s, rec_s, dv_mV)); idx += 1
        blocks.append(blk_loop(idx, cnt)); idx += 1

    return blocks, idx


def expand_pulse_test(p, cap, start_idx, _ctx=None):
    """
    Pulse Test (HPPC-style).
    Per SOC point:
      [SOC Adjust]  CYCMRK + CCDi_DOD + REST + LOOP(1)
      [Measure]     CYCMRK + REST_stab + CCDi_pulse + REST + [CCCh_return + REST] + LOOP(1)
    """
    blocks = []
    idx    = start_idx
    rec_s  = p.get("record_time_s", 30)
    dv_mV  = p.get("voltage_change_mV", 10.0)
    tl_s   = p.get("time_limit_h", 48) * 3600

    ch_v      = p.get("charge_voltage_V",   4.2) * 1000
    di_vc     = p.get("discharge_voltage_V", 2.5) * 1000
    cv_mA     = crate_to_mA(p.get("cv_cutoff_c", 0.05), cap)
    step_mA   = crate_to_mA(p.get("soc_step_c_rate", 0.1), cap)
    pulse_mA  = crate_to_mA(p.get("pulse_c_rate", 1.5), cap)
    ret_mA    = crate_to_mA(p.get("return_c_rate", 0.1), cap)
    pulse_s   = float(p.get("pulse_duration_s", 30))
    stab_s    = p.get("stabilization_min", 60) * 60
    recov_s   = p.get("recovery_min", 30) * 60
    rec_pulse = p.get("record_time_pulse_s", 1)
    dv_pulse  = p.get("voltage_change_pulse_mV", 0.0)
    return_pulse = p.get("return_pulse", True)
    capa_ref  = _resolve_capa_ref(p, _ctx)

    soc_mode = p.get("soc_mode", "interval")
    if soc_mode == "interval":
        interval   = p.get("soc_interval_percent", 10)
        soc_points = list(range(100 - interval, 0, -interval))
    else:
        soc_points = sorted(p.get("soc_points", [80, 60, 40, 20]), reverse=True)

    blocks.append(blk_cccv(idx, ch_v, step_mA, tl_s, cv_mA, rec_s, dv_mV)); idx += 1
    blocks.append(blk_rest(idx, recov_s, rec_s, dv_mV)); idx += 1

    prev_soc = 100.0
    for soc in soc_points:
        dod_pct = prev_soc - soc
        blocks.append(blk_marker(idx)); idx += 1
        blocks.append(blk_ccdi_dod(idx, step_mA, di_vc, dod_pct, capa_ref, rec_s, dv_mV)); idx += 1
        blocks.append(blk_rest(idx, recov_s, rec_s, dv_mV)); idx += 1
        blocks.append(blk_loop(idx, 1)); idx += 1

        blocks.append(blk_marker(idx)); idx += 1
        blocks.append(blk_rest(idx, stab_s, rec_s, dv_mV)); idx += 1
        blocks.append(blk_ccdi(idx, pulse_mA, di_vc, tl_s=pulse_s, rec_s=rec_pulse, dv_mV=dv_pulse)); idx += 1
        pulse_rest_ref = idx
        blocks.append(blk_rest(idx, recov_s, rec_s, dv_mV)); idx += 1
        if return_pulse:
            blocks.append(blk_ccc_return(idx, ch_v, ret_mA, ref_step_num=pulse_rest_ref, rec_s=rec_s, dv_mV=dv_mV)); idx += 1
            blocks.append(blk_rest(idx, recov_s, rec_s, dv_mV)); idx += 1
        blocks.append(blk_loop(idx, 1)); idx += 1
        prev_soc = soc

    return blocks, idx


EXPANDERS = {
    "rest":           expand_rest,
    "capacity_check": expand_capacity_check,
    "soc_setting":    expand_soc_setting,
    "charge":         expand_charge,
    "discharge":      expand_discharge,
    "cycle":          expand_cycle,
    "rate_test":      expand_rate_test,
    "pulse_test":     expand_pulse_test,
}


def schedule_to_binary_blocks(schedule):
    cap         = float(schedule.get("cell_capacity_mAh", 100.0))
    blocks_json = schedule.get("blocks", [])
    binary      = []
    idx         = 1
    ctx         = {"capa_ref_step": 0, "capa_ref_map": {}}

    for block in blocks_json:
        btype    = block["type"]
        params   = block.get("params", {})
        bid      = block.get("id", "")
        expander = EXPANDERS.get(btype)
        if expander is None:
            continue

        if btype == "capacity_check":
            new_blocks, idx, capa_ref = expander(params, cap, idx, ctx)
            ctx["capa_ref_step"] = capa_ref
            if bid:
                ctx["capa_ref_map"][bid] = capa_ref
        else:
            new_blocks, idx = expander(params, cap, idx, ctx)

        binary.extend(new_blocks)

    binary.append(blk_end(idx))
    return binary


def schedule_to_sch(schedule):
    safety = schedule.get("safety", {})
    name   = schedule.get("schedule_name", schedule.get("name", "Schedule"))
    header = make_header(name=name, safety=safety, author=schedule.get("author", "user"))
    body   = b"".join(schedule_to_binary_blocks(schedule))
    return header + body
