# -*- coding: utf-8 -*-
"""
sch_writer.py -- PNE CTSeditorPro v2 포맷 .sch 파일 생성기 (v3)
=====================================================================
JSON 중간표현을 받아 PNE CTSeditorPro가 인식하는 .sch 바이너리 파일을 생성합니다.

사용법:
    python sch_writer.py schedule.json output.sch

JSON 구조 (두 가지 모드):

  [단일 루프 모드 - 수명 시험 등]
    "metadata": {
      "test_type": "cyclelife",
      "cell_capacity_mAh": 100,
    },
    "pre_loop": [...],
    "loop": {
      "count": 50, "reset_capacity": true, "steps": [...]
    }

  [다중 사이클 모드 - Rate Test 등]
    "metadata": {
      "test_type": "ratetest",
    },
    "pre_loop": [...],
    "cycles": [
      {"label":"0.1C", "count":2, "reset_capacity":true, "steps":[...]},
      ...
    ]

기본값 Rest 패턴 (metadata.test_type):
  - "ratetest":    각 충전/방전 뒤 30분 Rest
  - "cyclelife":   Rest 없음
  - "dcir":        각 충전/방전 뒤 30초 Rest
  - "formation":   각 충전/방전 뒤 30분 Rest
  - "impedance":   각 충전/방전 뒤 30초 Rest

명시적으로 rest를 지정하면 자동값이 override됨.
"""

import struct
import json
import sys
from datetime import datetime


MAGIC        = b'\x71\x4d\x0b\x00\x02\x00\x01\x00'
HEADER_SIZE  = 1632
STEP_SIZE    = 612
FILE_SIG     = b'PNE CTSPro Schedule File.'

TYPE_REST          = 3
TYPE_CCCV_CHARGE   = 0x0101
TYPE_CC_CHARGE     = 0x0201
TYPE_CC_DISCHARGE  = 0x0202
TYPE_LOOP          = 8
TYPE_END           = 6
TYPE_CYCLE         = 7

OFF_STEP_IDX   = 0
OFF_STEP_TYPE  = 8
OFF_REST_DUR   = 20
OFF_CC_I       = 16
OFF_CCCV_V     = 12
OFF_CCCV_TL    = 20
OFF_CCCV_CVCO  = 32
OFF_CCCH_VLIM  = 12
OFF_CCCH_VC    = 28
OFF_CCDIS_VLIM = 12
OFF_CCDIS_TL   = 20
OFF_CCDIS_VC   = 28
OFF_REC_VOLT   = 332
OFF_REC_TIME   = 340
OFF_FLAG_496   = 496
OFF_LOOP_COUNT = 52
OFF_LOOP_RESET = 496
OFF_LOOP_GOTO  = 564

HOFF_FILE_SIG  = 0x48
HOFF_AUTHOR    = 0x150
HOFF_TS2       = 0x250
HOFF_SCH_NAME  = 0x298
HOFF_TS3       = 0x398
HOFF_SAFETY    = 0x3D8


DEFAULT_REST_PATTERNS = {
    'ratetest': '30min',
    'cyclelife': None,
    'dcir': '30s',
    'formation': '30min',
    'impedance': '30s',
}


def insert_auto_rest(steps, test_type, rest_record_time='30s'):
    """
    test_type에 따라 충전/방전 스텝 뒤에 자동 Rest 삽입.
    마지막 스텝 뒤에도 rest를 삽입합니다 (사이클 안정화 필요).
    """
    rest_dur = DEFAULT_REST_PATTERNS.get(test_type)
    if rest_dur is None:
        return steps

    if not steps:
        return steps

    result = []
    for i, step in enumerate(steps):
        result.append(step)
        stype = step.get('type', '')
        is_charge = stype in ('cccv_charge', 'cc_charge')
        is_discharge = stype == 'cc_discharge'
        is_last = (i == len(steps) - 1)

        # 충방전 뒤에 rest 삽입 (마지막 스텝도 포함)
        should_add_rest = False
        if is_charge or is_discharge:
            if is_last:
                # 마지막 스텝이면 항상 rest 추가
                should_add_rest = True
            else:
                # 마지막이 아니면 다음 스텝이 rest가 아닐 때만
                next_step = steps[i + 1]
                if next_step.get('type') != 'rest':
                    should_add_rest = True

        if should_add_rest:
            result.append({
                'type': 'rest',
                'duration': rest_dur,
                'record_time': rest_record_time,
                'auto_inserted': True
            })

    return result


def parse_duration(s, capacity_mA=None):
    if s is None:
        return 0.0
    s = str(s).strip()
    if s.upper().endswith('C'):
        if capacity_mA is None:
            raise ValueError("C-rate '%s' needs cell_capacity_mAh" % s)
        return float(s[:-1]) * capacity_mA
    s_lower = s.lower()
    if s_lower.endswith('d'):
        return float(s[:-1]) * 86400.0
    elif s_lower.endswith('h'):
        return float(s[:-1]) * 3600.0
    elif s_lower.endswith('min'):
        return float(s[:-3]) * 60.0
    elif s_lower.endswith('s'):
        return float(s[:-1])
    else:
        return float(s)


def validate_step(step, capacity_mA):
    stype = step.get('type', '')
    required = {
        'rest':         ['duration'],
        'cccv_charge':  ['voltage_V', 'current', 'time_limit', 'cv_cutoff'],
        'cc_charge':    ['current', 'voltage_cutoff_V'],
        'cc_discharge': ['current', 'voltage_cutoff_V'],
    }
    if stype not in required:
        raise ValueError("Unknown step type: '%s'" % stype)
    missing = [f for f in required.get(stype, []) if f not in step]
    if missing:
        raise ValueError("Step '%s' missing fields: %s" % (stype, missing))


def _pack_f(block, offset, value):
    struct.pack_into('<f', block, offset, float(value))

def _pack_i(block, offset, value):
    struct.pack_into('<i', block, offset, int(value))


def make_rest_block(step_idx, duration_s, record_time_s=60.0, inside_loop=True):
    block = bytearray(STEP_SIZE)
    _pack_i(block, OFF_STEP_IDX,  step_idx)
    _pack_i(block, OFF_STEP_TYPE, TYPE_REST)
    _pack_f(block, OFF_REST_DUR,  duration_s)
    _pack_f(block, OFF_REC_TIME,  record_time_s)
    if inside_loop:
        _pack_i(block, OFF_FLAG_496, 1)
    return bytes(block)


def make_cccv_charge_block(step_idx, voltage_mV, current_mA, time_limit_s,
                            cv_cutoff_mA, record_voltage_mV=10.0, record_time_s=30.0):
    block = bytearray(STEP_SIZE)
    _pack_i(block, OFF_STEP_IDX,  step_idx)
    _pack_i(block, OFF_STEP_TYPE, TYPE_CCCV_CHARGE)
    _pack_f(block, OFF_CCCV_V,    voltage_mV)
    _pack_f(block, OFF_CC_I,      current_mA)
    _pack_f(block, OFF_CCCV_TL,   time_limit_s)
    _pack_f(block, OFF_CCCV_CVCO, cv_cutoff_mA)
    _pack_f(block, OFF_REC_VOLT,  record_voltage_mV)
    _pack_f(block, OFF_REC_TIME,  record_time_s)
    _pack_i(block, OFF_FLAG_496,  1)
    return bytes(block)


def make_cc_charge_block(step_idx, current_mA, voltage_cutoff_mV,
                          voltage_limit_mV=5000.0, time_limit_s=172800.0,
                          record_voltage_mV=10.0, record_time_s=30.0):
    block = bytearray(STEP_SIZE)
    _pack_i(block, OFF_STEP_IDX,  step_idx)
    _pack_i(block, OFF_STEP_TYPE, TYPE_CC_CHARGE)
    _pack_f(block, OFF_CCCH_VLIM, voltage_limit_mV)
    _pack_f(block, OFF_CC_I,      current_mA)
    _pack_f(block, OFF_CCCV_TL,   time_limit_s)
    _pack_f(block, OFF_CCCH_VC,   voltage_cutoff_mV)
    _pack_f(block, OFF_REC_VOLT,  record_voltage_mV)
    _pack_f(block, OFF_REC_TIME,  record_time_s)
    _pack_i(block, OFF_FLAG_496,  1)
    return bytes(block)


def make_cc_discharge_block(step_idx, current_mA, voltage_cutoff_mV,
                             voltage_limit_mV=2000.0, time_limit_s=0.0,
                             record_voltage_mV=10.0, record_time_s=30.0):
    block = bytearray(STEP_SIZE)
    _pack_i(block, OFF_STEP_IDX,   step_idx)
    _pack_i(block, OFF_STEP_TYPE,  TYPE_CC_DISCHARGE)
    _pack_f(block, OFF_CCDIS_VLIM, voltage_limit_mV)
    _pack_f(block, OFF_CC_I,       current_mA)
    if time_limit_s > 0:
        _pack_f(block, OFF_CCDIS_TL, time_limit_s)
    _pack_f(block, OFF_CCDIS_VC,   voltage_cutoff_mV)
    _pack_f(block, OFF_REC_VOLT,   record_voltage_mV)
    _pack_f(block, OFF_REC_TIME,   record_time_s)
    _pack_i(block, OFF_FLAG_496,   1)
    return bytes(block)


def make_cycle_block(step_idx, flag_offset=64):
    block = bytearray(STEP_SIZE)
    _pack_i(block, OFF_STEP_IDX,  step_idx)
    _pack_i(block, OFF_STEP_TYPE, TYPE_CYCLE)
    _pack_i(block, flag_offset,   1)
    return bytes(block)


def make_loop_block(step_idx, count, reset_capacity=False):
    block = bytearray(STEP_SIZE)
    _pack_i(block, OFF_STEP_IDX,   step_idx)
    _pack_i(block, OFF_STEP_TYPE,  TYPE_LOOP)
    _pack_i(block, OFF_LOOP_COUNT, count)
    if reset_capacity:
        _pack_i(block, OFF_LOOP_RESET, 1)
    _pack_i(block, OFF_LOOP_GOTO,  1)
    return bytes(block)


def make_end_block(step_idx):
    block = bytearray(STEP_SIZE)
    _pack_i(block, OFF_STEP_IDX,  step_idx)
    _pack_i(block, OFF_STEP_TYPE, TYPE_END)
    return bytes(block)


def make_header(schedule_name, safety, author="user"):
    header = bytearray(HEADER_SIZE)
    header[0:8] = MAGIC
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S.000')
    ts = now_str.encode('ascii')
    header[0x08 : 0x08 + len(ts)] = ts
    header[HOFF_FILE_SIG : HOFF_FILE_SIG + len(FILE_SIG)] = FILE_SIG
    try:
        author_b = author.encode('cp949')[:60]
    except Exception:
        author_b = author.encode('ascii', errors='replace')[:60]
    header[HOFF_AUTHOR : HOFF_AUTHOR + len(author_b)] = author_b
    header[HOFF_TS2 : HOFF_TS2 + len(ts)] = ts
    sch_filename = schedule_name + '.sch'
    try:
        fn_b = sch_filename.encode('cp949')[:100]
    except Exception:
        fn_b = sch_filename.encode('ascii', errors='replace')[:100]
    header[0x290] = 1
    header[0x294] = 2
    header[HOFF_SCH_NAME : HOFF_SCH_NAME + len(fn_b)] = fn_b
    header[HOFF_TS3 : HOFF_TS3 + len(ts)] = ts
    so = HOFF_SAFETY
    struct.pack_into('<f', header, so + 0,  safety.get('max_voltage_V',    4.3)  * 1000)
    struct.pack_into('<f', header, so + 4,  safety.get('min_voltage_V',    1.5)  * 1000)
    struct.pack_into('<f', header, so + 8,  safety.get('max_current_mA',   0.0))
    struct.pack_into('<f', header, so + 12, safety.get('max_capacity_mAh', 100.0))
    struct.pack_into('<f', header, so + 16, safety.get('min_current_mA',   0.0))
    struct.pack_into('<f', header, so + 20, safety.get('max_temp_C',       70.0))
    struct.pack_into('<i', header, 0x404, 7)
    return bytes(header)


def build_step_blocks(schedule_json):
    """
    JSON to step blocks.
    If test_type is specified, auto-insert default Rest.
    """
    meta      = schedule_json.get('metadata', {})
    capacity  = meta.get('cell_capacity_mAh', 1000.0)
    test_type = meta.get('test_type', None)
    pre_steps = schedule_json.get('pre_loop', [])
    loop_def  = schedule_json.get('loop',   None)
    cycles    = schedule_json.get('cycles', None)

    if test_type:
        pre_steps = insert_auto_rest(pre_steps, test_type)
        if loop_def and 'steps' in loop_def:
            loop_def = dict(loop_def)
            loop_def['steps'] = insert_auto_rest(loop_def['steps'], test_type)
        if cycles:
            cycles = [
                {
                    **cyc,
                    'steps': insert_auto_rest(cyc.get('steps', []), test_type)
                }
                for cyc in cycles
            ]

    if cycles is not None:
        return _build_multi_cycle(capacity, pre_steps, cycles)
    else:
        return _build_single_loop(capacity, pre_steps, loop_def)


def _build_single_loop(capacity, pre_steps, loop_def):
    blocks  = []
    idx     = 1
    has_loop = loop_def is not None

    if pre_steps:
        for step in pre_steps:
            validate_step(step, capacity)
            blocks.append(_step_to_block(step, idx, capacity, inside_loop=False))
            idx += 1
        blocks.append(make_loop_block(idx, 1, False))
        idx += 1
        if has_loop:
            blocks.append(make_cycle_block(idx, flag_offset=64))
            idx += 1

    if has_loop:
        loop_steps = loop_def.get('steps', [])
        count      = loop_def.get('count', 1)
        reset_cap  = loop_def.get('reset_capacity', False)
        for step in loop_steps:
            validate_step(step, capacity)
            blocks.append(_step_to_block(step, idx, capacity, inside_loop=True))
            idx += 1
        blocks.append(make_loop_block(idx, count, reset_cap))
        idx += 1

    blocks.append(make_end_block(idx))
    return blocks


def _build_multi_cycle(capacity, pre_steps, cycles):
    blocks = []
    idx    = 1

    has_pre = len(pre_steps) > 0
    if has_pre:
        for step in pre_steps:
            validate_step(step, capacity)
            blocks.append(_step_to_block(step, idx, capacity, inside_loop=False))
            idx += 1
        blocks.append(make_loop_block(idx, 1, False))
        idx += 1
        blocks.append(make_cycle_block(idx, flag_offset=496))
        idx += 1

    for ci, cyc in enumerate(cycles):
        cyc_steps = cyc.get('steps', [])
        count     = cyc.get('count', 1)
        reset_cap = cyc.get('reset_capacity', True)

        for step in cyc_steps:
            validate_step(step, capacity)
            blocks.append(_step_to_block(step, idx, capacity, inside_loop=True))
            idx += 1
        blocks.append(make_loop_block(idx, count, reset_cap))
        idx += 1

        is_last = (ci == len(cycles) - 1)
        if not is_last:
            if not has_pre and ci == 0:
                blocks.append(make_cycle_block(idx, flag_offset=496))
            else:
                blocks.append(make_cycle_block(idx, flag_offset=64))
            idx += 1

    blocks.append(make_end_block(idx))
    return blocks


def _step_to_block(step, idx, capacity_mA, inside_loop):
    stype    = step['type']
    rec_v_mv = step.get('record_voltage_V', 0.01) * 1000
    rec_t_s  = parse_duration(step.get('record_time', '60s'))

    if stype == 'rest':
        dur_s   = parse_duration(step['duration'])
        rec_t_s = parse_duration(step.get('record_time', '1min'))
        return make_rest_block(idx, dur_s, rec_t_s, inside_loop)
    elif stype == 'cccv_charge':
        v_mv    = step['voltage_V'] * 1000
        i_ma    = parse_duration(step['current'], capacity_mA)
        tl_s    = parse_duration(step['time_limit'])
        cv_ma   = parse_duration(step['cv_cutoff'], capacity_mA)
        rec_t_s = parse_duration(step.get('record_time', '30s'))
        return make_cccv_charge_block(idx, v_mv, i_ma, tl_s, cv_ma, rec_v_mv, rec_t_s)
    elif stype == 'cc_charge':
        i_ma    = parse_duration(step['current'], capacity_mA)
        vc_mv   = step['voltage_cutoff_V'] * 1000
        vl_mv   = step.get('voltage_limit_V', 5.0) * 1000
        tl_s    = parse_duration(step.get('time_limit', '2d'))
        rec_t_s = parse_duration(step.get('record_time', '30s'))
        return make_cc_charge_block(idx, i_ma, vc_mv, vl_mv, tl_s, rec_v_mv, rec_t_s)
    elif stype == 'cc_discharge':
        i_ma    = parse_duration(step['current'], capacity_mA)
        vc_mv   = step['voltage_cutoff_V'] * 1000
        vl_mv   = step.get('voltage_limit_V', 2.0) * 1000
        tl_s    = parse_duration(step.get('time_limit', '0s'))
        rec_t_s = parse_duration(step.get('record_time', '30s'))
        return make_cc_discharge_block(idx, i_ma, vc_mv, vl_mv, tl_s, rec_v_mv, rec_t_s)
    else:
        raise ValueError("Unsupported step type: '%s'" % stype)


def json_to_sch(json_input, output_path):
    if isinstance(json_input, str):
        with open(json_input, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = json_input

    meta   = data.get('metadata', {})
    safety = meta.get('safety', {})
    sname  = meta.get('schedule_name', 'schedule')
    author = meta.get('author', 'user')

    mode = 'multi-cycle' if data.get('cycles') else 'single-loop'
    print("[Generate] %s (%s)" % (sname, mode))
    header = make_header(sname, safety, author)
    blocks = build_step_blocks(data)

    total_size = len(header) + len(blocks) * STEP_SIZE
    print("  Header: %d bytes" % len(header))
    print("  Steps: %d" % len(blocks))
    print("  Total: %d bytes" % total_size)

    with open(output_path, 'wb') as f:
        f.write(header)
        for b in blocks:
            f.write(b)

    print("  [Done] -> %s" % output_path)
    return output_path


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python sch_writer.py <input.json> <output.sch>")
        sys.exit(1)
    json_to_sch(sys.argv[1], sys.argv[2])
