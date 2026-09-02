#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nl_to_sch.py -- 자연어 → JSON → .sch 전체 파이프라인
사용법: python nl_to_sch.py
"""

import json
import struct
from nl_parser_v2 import SimpleParser
from sch_writer import json_to_sch


def main():
    print("\n" + "=" * 80)
    print("자연어 → JSON → .sch 파이프라인")
    print("=" * 80)

    # 자연어 입력
    nl_text = "100 mAh 셀 0.5C로 50사이클 수명 시험. 시작 전에 3시간 휴지. 충전은 CCCV 4.2V, 0.05C current cut-off, 2 day limit, 방전은 CC 2.5V까지. 기록 조건은 모든 스텝에서 30초"

    print(f"\n[Step 1] 자연어 입력:")
    print(f"  {nl_text[:70]}...\n")

    # Step 1: 자연어 → JSON
    print("[Step 2] 자연어 파싱")
    parser = SimpleParser()
    json_data = parser.parse(nl_text)

    print(f"\n  ✓ schedule_name: {json_data['metadata']['schedule_name']}")
    print(f"  ✓ test_type: {json_data['metadata']['test_type']}")
    print(f"  ✓ cell_capacity: {json_data['metadata']['cell_capacity_mAh']} mAh")
    print(f"  ✓ loop.count: {json_data['loop']['count']}")
    print(f"  ✓ loop.steps: {len(json_data['loop']['steps'])} 개")

    # JSON 저장
    json_file = 'demo_nl_cyclelife.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON 저장: {json_file}")

    # Step 2: JSON → .sch
    print("\n[Step 3] JSON → .sch 생성")
    sch_file = 'demo_nl_cyclelife.sch'
    json_to_sch(json_file, sch_file)

    # Step 3: 검증
    print("\n[Step 4] 생성된 .sch 파일 검증")
    with open(sch_file, 'rb') as f:
        data = f.read()

    filesize = len(data)
    if (filesize - 1760) % 612 == 0:
        header_size = 1760
    else:
        header_size = 1632

    num_steps = (filesize - header_size) // 612
    print(f"\n  파일 크기: {filesize} bytes")
    print(f"  헤더: {header_size} bytes")
    print(f"  스텝 수: {num_steps}")

    type_names = {
        3: 'REST',
        6: 'END',
        7: 'CYCL',
        8: 'LOOP',
        0x0101: 'CCCV',
        0x0202: 'CCDi',
    }

    print("\n  스텝 구조:")
    for i in range(num_steps):
        offset = header_size + i * 612
        step_type = struct.unpack_from('<i', data, offset + 8)[0]
        type_name = type_names.get(step_type, f'0x{step_type:04x}')

        info = ''
        if step_type == 8:
            count = struct.unpack_from('<i', data, offset + 52)[0]
            info = f'(count={count})'
        elif step_type == 3:
            dur = struct.unpack_from('<f', data, offset + 20)[0]
            info = f'(dur={dur/3600:.1f}h)' if dur >= 3600 else f'(dur={dur/60:.0f}min)'

        print(f"    {i+1}. {type_name:4s} {info}")

    print("\n" + "=" * 80)
    print(f"✓ 완료!")
    print(f"  생성된 파일:")
    print(f"    - JSON: {json_file}")
    print(f"    - SCH:  {sch_file}")
    print(f"\n  다음 단계: CTSeditorPro에서 {sch_file}을 열어 저장 테스트")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
