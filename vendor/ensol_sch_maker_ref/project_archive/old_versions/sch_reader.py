# -*- coding: utf-8 -*-
"""
sch_reader.py -- PNE CTSeditorPro v2/v3 .sch 파일 디코더 (v2)
.sch 바이너리 파일을 읽어 JSON 중간표현으로 변환합니다.

사용법:
    python sch_reader.py input.sch [output.json]

Loop 구조 해석:
  Loop 0개: pre_loop만
  Loop 1개: loop (단일 루프)
  Loop 2개: pre_loop + loop (2-Loop 구조)
  Loop 3개 이상: cycles (다중 사이클, Rate Test 등)
"""

import struct
import json
import sys

HEADER_V2    = 1632
HEADER_V3    = 1760
STEP_SIZE    = 612

TYPE_REST          = 3
TYPE_CCCV_CHARGE   = 0x0101
TYPE_CC_CHARGE     = 0x0201
TYPE_CC_DISCHARGE  = 0x0202
TYPE_LOOP          = 8
TYPE_END           = 6
TYPE_CYCLE         = 7

OFF_STEP_IDX    = 0
OFF_STEP_TYPE   = 8
OFF_CC_I        = 16
OFF_REST_DUR    = 20
OFF_CCCV_V      = 12
OFF_CCCV_TL     = 20
OFF_CCCV_CVCO   = 32
OFF_CCCH_VLIM   = 12
OFF_CCCH_VC     = 28
OFF_CCDIS_VLIM  = 12
OFF_CCDIS_TL    = 20
OFF_CCDIS_VC    = 28
OFF_REC_VOLT    = 332
OFF_REC_TIME    = 340
OFF_FLAG_496    = 496
OFF_LOOP_COUNT  = 52
OFF_LOOP_RESET  = 496
OFF_LOOP_GOTO   = 564

HOFF_AUTHOR    = 0x150
HOFF_SCH_NAME  = 0x298
HOFF_SAFETY    = 0x3D8

SKIP_TYPES = ('end', 'loop', 'cycle_marker', 'unknown')


def _f(block, off):
    return struct.unpack_from('<f', block, off)[0]

def _i(block, off):
    return struct.unpack_from('<i', block, off)[0]

def _round(v):
    return round(v, 6)

def _read_str(data, offset, maxlen=128):
    raw = data[offset:offset+maxlen]
    end = raw.find(b'\x00')
    if end >= 0:
        raw = raw[:end]
    try:
        return raw.decode('cp949')
    except Exception:
        try:
            return raw.decode('utf-8')
        except Exception:
            return raw.decode('ascii', errors='replace')

def _detect_version(data):
    if len(data) < HEADER_V3:
        return HEADER_V2
    rem_v2 = (len(data) - HEADER_V2) % STEP_SIZE
    rem_v3 = (len(data) - HEADER_V3) % STEP_SIZE
    if rem_v3 == 0 and rem_v2 != 0:
        return HEADER_V3
    return HEADER_V2


def decode_header(data):
    author    = _read_str(data, HOFF_AUTHOR, 128)
    sch_name  = _read_str(data, HOFF_SCH_NAME, 128)
    if sch_name.lower().endswith('.sch'):
        sch_name = sch_name[:-4]
    so = HOFF_SAFETY
    safety = {
        'max_voltage_V':    _round(_f(data, so + 0)  / 1000),
        'min_voltage_V':    _round(_f(data, so + 4)  / 1000),
        'max_current_mA':   _round(_f(data, so + 8)),
        'max_capacity_mAh': _round(_f(data, so + 12)),
        'min_current_mA':   _round(_f(data, so + 16)),
        'max_temp_C':       _round(_f(data, so + 20)),
    }
    return {'schedule_name': sch_name, 'author': author, 'safety': safety}


def decode_rest(block):
    return {
        'type':          'rest',
        'duration_s':    _round(_f(block, OFF_REST_DUR)),
        'record_time_s': _round(_f(block, OFF_REC_TIME)),
    }

def decode_cccv_charge(block):
    return {
        'type':              'cccv_charge',
        'voltage_mV':        _round(_f(block, OFF_CCCV_V)),
        'current_mA':        _round(_f(block, OFF_CC_I)),
        'time_limit_s':      _round(_f(block, OFF_CCCV_TL)),
        'cv_cutoff_mA':      _round(_f(block, OFF_CCCV_CVCO)),
        'record_voltage_mV': _round(_f(block, OFF_REC_VOLT)),
        'record_time_s':     _round(_f(block, OFF_REC_TIME)),
    }

def decode_cc_charge(block):
    return {
        'type':              'cc_charge',
        'voltage_limit_mV':  _round(_f(block, OFF_CCCH_VLIM)),
        'current_mA':        _round(_f(block, OFF_CC_I)),
        'time_limit_s':      _round(_f(block, OFF_CCCV_TL)),
        'voltage_cutoff_mV': _round(_f(block, OFF_CCCH_VC)),
        'record_voltage_mV': _round(_f(block, OFF_REC_VOLT)),
        'record_time_s':     _round(_f(block, OFF_REC_TIME)),
    }

def decode_cc_discharge(block):
    return {
        'type':              'cc_discharge',
        'voltage_limit_mV':  _round(_f(block, OFF_CCDIS_VLIM)),
        'current_mA':        _round(_f(block, OFF_CC_I)),
        'time_limit_s':      _round(_f(block, OFF_CCDIS_TL)),
        'voltage_cutoff_mV': _round(_f(block, OFF_CCDIS_VC)),
        'record_voltage_mV': _round(_f(block, OFF_REC_VOLT)),
        'record_time_s':     _round(_f(block, OFF_REC_TIME)),
    }

def decode_loop(block):
    return {
        'type':           'loop',
        'count':          _i(block, OFF_LOOP_COUNT),
        'reset_capacity': bool(_i(block, OFF_LOOP_RESET)),
    }

def decode_step_block(block):
    idx = _i(block, OFF_STEP_IDX)
    typ = _i(block, OFF_STEP_TYPE)
    if typ == TYPE_REST:
        d = decode_rest(block)
    elif typ == TYPE_CCCV_CHARGE:
        d = decode_cccv_charge(block)
    elif typ == TYPE_CC_CHARGE:
        d = decode_cc_charge(block)
    elif typ == TYPE_CC_DISCHARGE:
        d = decode_cc_discharge(block)
    elif typ == TYPE_LOOP:
        d = decode_loop(block)
    elif typ == TYPE_END:
        d = {'type': 'end'}
    elif typ == TYPE_CYCLE:
        d = {'type': 'cycle_marker'}
    else:
        d = {'type': 'unknown', 'raw_type': typ}
    d['_step_idx'] = idx
    d['_flag_496'] = _i(block, OFF_FLAG_496)
    return d


def decode_sch(data):
    """
    .sch 바이너리 -> JSON 딕셔너리 변환.

    Loop 개수로 구조 판단:
      0개: pre_loop만
      1개: loop 단일 루프
      2개: pre_loop + loop (2-Loop 구조)
      3개 이상: cycles 다중 사이클 (Rate Test 등)
    """
    header_size = _detect_version(data)
    n_steps     = (len(data) - header_size) // STEP_SIZE
    meta        = decode_header(data)

    raw_steps = []
    for s in range(n_steps):
        base  = header_size + s * STEP_SIZE
        block = data[base:base + STEP_SIZE]
        raw_steps.append(decode_step_block(block))

    loop_positions = [i for i, st in enumerate(raw_steps) if st['type'] == 'loop']
    n_loops = len(loop_positions)

    pre_loop_steps = []
    loop_out  = None
    cycles_out = None

    if n_loops == 0:
        # pre_loop만
        pre_loop_steps = [_clean(s) for s in raw_steps if s['type'] not in SKIP_TYPES]

    elif n_loops == 1:
        # 단일 루프
        lp = loop_positions[0]
        loop_blk = raw_steps[lp]
        inner = [s for s in raw_steps[:lp] if s['type'] not in SKIP_TYPES]
        loop_out = {
            'count':          loop_blk.get('count', 1),
            'reset_capacity': loop_blk.get('reset_capacity', False),
            'steps':          [_clean(s) for s in inner],
        }

    elif n_loops == 2:
        # 2-Loop 구조 (pre_loop + 메인 루프)
        lp1, lp2     = loop_positions[0], loop_positions[1]
        second_blk   = raw_steps[lp2]
        pre_loop_steps = [_clean(s) for s in raw_steps[:lp1]
                          if s['type'] not in SKIP_TYPES]
        loop_inner   = [s for s in raw_steps[lp1 + 1 : lp2]
                        if s['type'] not in SKIP_TYPES]
        loop_out = {
            'count':          second_blk.get('count', 1),
            'reset_capacity': second_blk.get('reset_capacity', False),
            'steps':          [_clean(s) for s in loop_inner],
        }

    else:
        # 다중 사이클 (Rate Test 등)
        # 첫 Loop 앞 = pre_loop, 이후 Loop 사이 구간 = 각 cycle 그룹
        lp0 = loop_positions[0]
        pre_loop_steps = [_clean(s) for s in raw_steps[:lp0]
                          if s['type'] not in SKIP_TYPES]

        # pre_loop이 있는지 판단: 첫 Loop의 reset_capacity=False이면 pre_loop용
        first_loop = raw_steps[lp0]
        has_pre    = (not first_loop.get('reset_capacity', False)
                      and len(pre_loop_steps) > 0)

        if has_pre:
            cycle_loop_positions = loop_positions[1:]  # 첫 Loop는 pre_loop용
            start_idx = lp0 + 1  # 첫 Cycle 마커부터
        else:
            cycle_loop_positions = loop_positions
            pre_loop_steps = []
            start_idx = 0

        # 각 cycle 그룹 추출
        cycles_out = []
        prev_end   = start_idx
        for ci, lp in enumerate(cycle_loop_positions):
            loop_blk  = raw_steps[lp]
            # prev_end ~ lp 사이의 내용 스텝 (Cycle 마커 제외)
            group_steps = [s for s in raw_steps[prev_end:lp]
                           if s['type'] not in SKIP_TYPES]
            cycles_out.append({
                'label':          'Cycle%d' % (ci + 1),
                'count':          loop_blk.get('count', 1),
                'reset_capacity': loop_blk.get('reset_capacity', True),
                'steps':          [_clean(s) for s in group_steps],
            })
            prev_end = lp + 1  # 다음 Cycle 마커부터

    result = {
        'metadata': meta,
        'pre_loop': pre_loop_steps,
    }
    if cycles_out is not None:
        result['cycles'] = cycles_out
    else:
        result['loop'] = loop_out

    return result


def _clean(step):
    return {k: v for k, v in step.items() if not k.startswith('_')}


def sch_to_json(input_path, output_path=None):
    with open(input_path, 'rb') as f:
        data = f.read()
    result = decode_sch(data)
    text   = json.dumps(result, ensure_ascii=False, indent=2)
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print('[Reader] %s -> %s' % (input_path, output_path))
    else:
        print(text)
    return result


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('사용법: python sch_reader.py <input.sch> [output.json]')
        sys.exit(1)
    out = sys.argv[2] if len(sys.argv) >= 3 else None
    sch_to_json(sys.argv[1], out)
