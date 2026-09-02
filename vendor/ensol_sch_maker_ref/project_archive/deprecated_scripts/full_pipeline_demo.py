#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
full_pipeline_demo.py -- 자연어 → JSON → .sch 완전 파이프라인
CycleLife + Rate Test 모두 지원
"""

import json
import struct
from nl_parser_v2_extended import ExtendedParser
from sch_writer import json_to_sch


def demo_cyclelife():
    print("\n" + "=" * 80)
    print("[데모 1] CycleLife: 자연어 → JSON → .sch")
    print("=" * 80)

    nl_text = "100 mAh 셀 0.5C로 50사이클 수명 시험. 시작 전에 3시간 휴지. 충전은 CCCV 4.2V, 0.05C current cut-off, 2 day limit, 방전은 CC 2.5V까지. 기록 조건은 모든 스텝에서 30초"

    print(f"\n자연어 입력:")
    print(f"  {nl_text[:70]}...\n")

    parser = ExtendedParser()
    json_data = parser.parse(nl_text)

    print(f"\n생성된 JSON:")
    print(f"  schedule_name: {json_data['metadata']['schedule_name']}")
    print(f"  test_type: {json_data['metadata']['test_type']}")
    print(f"  loop.count: {json_data['loop']['count']}")
    print(f"  loop.steps: {len(json_data['loop']['steps'])}")

    # JSON 저장
    json_file = 'demo_cyclelife.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    # .sch 생성
    sch_file = 'demo_cyclelife.sch'
    json_to_sch(json_file, sch_file)

    # 검증
    print(f"\n생성된 .sch 파일 검증:")
    with open(sch_file, 'rb') as f:
        data = f.read()
    filesize = len(data)
    header_size = 1760 if (filesize - 1760) % 612 == 0 else 1632
    num_steps = (filesize - header_size) // 612
    print(f"  파일: {sch_file} ({filesize} bytes, {num_steps} 스텝)")
    print(f"  ✓ CycleLife 생성 완료!")


def demo_ratetest():
    print("\n" + "=" * 80)
    print("[데모 2] Rate Test: 자연어 → JSON → .sch")
    print("=" * 80)

    nl_text = "100 mAh 셀 Rate test. 0.1C 2사이클, 0.2C 1사이클, 0.5C 1사이클, 1C 1사이클. 충전은 CCCV 4.2V, 방전은 CC 2.5V까지."

    print(f"\n자연어 입력:")
    print(f"  {nl_text[:70]}...\n")

    parser = ExtendedParser()
    json_data = parser.parse(nl_text)

    print(f"\n생성된 JSON:")
    print(f"  schedule_name: {json_data['metadata']['schedule_name']}")
    print(f"  test_type: {json_data['metadata']['test_type']}")
    print(f"  cycles: {len(json_data.get('cycles', []))}개")
    if 'cycles' in json_data:
        for cyc in json_data['cycles']:
            print(f"    - {cyc['label']}: count={cyc['count']}, {len(cyc['steps'])} 스텝")

    # JSON 저장
    json_file = 'demo_ratetest.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    # .sch 생성
    sch_file = 'demo_ratetest.sch'
    json_to_sch(json_file, sch_file)

    # 검증
    print(f"\n생성된 .sch 파일 검증:")
    with open(sch_file, 'rb') as f:
        data = f.read()
    filesize = len(data)
    header_size = 1760 if (filesize - 1760) % 612 == 0 else 1632
    num_steps = (filesize - header_size) // 612

    type_names = {
        3: 'REST', 6: 'END', 7: 'CYCL', 8: 'LOOP',
        0x0101: 'CCCV', 0x0202: 'CCDi',
    }

    print(f"  파일: {sch_file} ({filesize} bytes, {num_steps} 스텝)")
    print(f"  스텝 구조 (처음 20개):")
    for i in range(min(num_steps, 20)):
        offset = header_size + i * 612
        step_type = struct.unpack_from('<i', data, offset + 8)[0]
        type_name = type_names.get(step_type, f'0x{step_type:04x}')

        info = ''
        if step_type == 8:
            count = struct.unpack_from('<i', data, offset + 52)[0]
            info = f'(count={count})'
        elif step_type == 7:
            flag_496 = struct.unpack_from('<i', data, offset + 496)[0]
            info = f'(flag_496={flag_496})'

        print(f"    {i+1:2d}. {type_name:4s} {info}")

    if num_steps > 20:
        print(f"    ... ({num_steps - 20}개 더)")

    print(f"  ✓ Rate Test 생성 완료!")


def main():
    print("\n" + "=" * 80)
    print("자연어 → JSON → .sch 완전 파이프라인 데모")
    print("=" * 80)

    demo_cyclelife()
    demo_ratetest()

    print("\n" + "=" * 80)
    print("✓ 모든 데모 완료!")
    print("=" * 80)
    print("\n생성된 파일:")
    print("  - demo_cyclelife.json / demo_cyclelife.sch")
    print("  - demo_ratetest.json / demo_ratetest.sch")
    print("\n다음 단계: CTSeditorPro에서 .sch 파일을 열어 저장 테스트하세요.")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
