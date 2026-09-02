#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_demo.py -- 자연어 → JSON → .sch 전체 파이프라인 데모
"""

import json
import sys
from pathlib import Path

# 같은 디렉토리의 모듈 import
from natural_language_parser import ScheduleParser
from sch_writer import json_to_sch


def demo():
    """자연어 → .sch 전체 파이프라인 데모"""

    print("\n" + "=" * 80)
    print("자연어 → JSON → .sch 전체 파이프라인 데모")
    print("=" * 80)

    # 자연어 입력
    nl_input = "100 mAh 셀 0.5C로 50사이클 수명 시험. 시작 전에 3시간 휴지. 충전은 CCCV 4.2V, 0.05C current cut-off, 2 day limit, 방전은 CC 2.5V까지. 기록 조건은 모든 스텝에서 30초"

    print("\n[단계 1] 자연어 입력:")
    print(f"  {nl_input}\n")

    # Step 1: 자연어 → JSON
    print("[단계 2] 자연어 파싱 → JSON")
    parser = ScheduleParser()
    json_data = parser.parse(nl_input)
    print(f"\n생성된 JSON (일부):")
    print(f"  schedule_name: {json_data['metadata']['schedule_name']}")
    print(f"  test_type: {json_data['metadata']['test_type']}")
    print(f"  cell_capacity: {json_data['metadata']['cell_capacity_mAh']} mAh")
    print(f"  loop.count: {json_data['loop']['count']}")
    print(f"  loop.steps: {len(json_data['loop']['steps'])} 개")

    # JSON 저장
    json_output_path = 'demo_cyclelife.json'
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"\n  ✓ JSON 저장: {json_output_path}")

    # Step 2: JSON → .sch
    print("\n[단계 3] JSON → .sch 바이너리 생성")
    sch_output_path = 'demo_cyclelife.sch'
    json_to_sch(json_output_path, sch_output_path)
    print(f"  ✓ .sch 저장: {sch_output_path}")

    # Step 3: 결과 확인
    print("\n[단계 4] 생성된 .sch 파일 검증")
    import struct
    with open(sch_output_path, 'rb') as f:
        data = f.read()

    filesize = len(data)
    if (filesize - 1760) % 612 == 0:
        header_size = 1760
    else:
        header_size = 1632

    num_steps = (filesize - header_size) // 612
    print(f"  파일 크기: {filesize} bytes")
    print(f"  헤더: {header_size} bytes")
    print(f"  스텝 수: {num_steps}")

    # 스텝 상세 출력
    print("\n  스텝 구성:")
    type_names = {
        3: 'REST',
        6: 'END ',
        7: 'CYCL',
        8: 'LOOP',
        0x0101: 'CCCV',
        0x0202: 'CCDi',
    }

    for i in range(num_steps):
        offset = header_size + i * 612
        step_type = struct.unpack_from('<i', data, offset + 8)[0]
        type_name = type_names.get(step_type, f'0x{step_type:04x}')

        info = ''
        if step_type == 8:
            count = struct.unpack_from('<i', data, offset + 52)[0]
            info = f'count={count}'
        elif step_type == 3:
            dur = struct.unpack_from('<f', data, offset + 20)[0]
            info = f'dur={dur:.0f}s'

        print(f"    {i+1}. {type_name:4s} {info}")

    print("\n" + "=" * 80)
    print("완료! CTSeditorPro에서 demo_cyclelife.sch를 열어 테스트해보세요.")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    demo()
