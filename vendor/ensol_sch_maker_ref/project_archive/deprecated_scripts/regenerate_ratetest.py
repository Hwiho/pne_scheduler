#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_ratetest.sch 파일 재생성
캐시를 무시하고 수정된 insert_auto_rest를 적용
"""

import json
import subprocess
import sys

# Step 1: nl_parser로 JSON 생성
print("=" * 80)
print("Rate Test .sch 파일 재생성")
print("=" * 80)

nl_text = "100 mAh 셀 Rate test. 0.1C 2사이클, 0.2C 1사이클, 0.5C 1사이클, 1C 1사이클. 충전은 CCCV 4.2V, 방전은 CC 2.5V까지."

# nl_parser 실행
result = subprocess.run([
    sys.executable, '-c',
    '''
import json
import sys
sys.path.insert(0, '.')
from nl_parser_v2_extended import ExtendedParser

parser = ExtendedParser()
json_data = parser.parse("''' + nl_text + '''")

with open("demo_ratetest.json", "w", encoding="utf-8") as f:
    json.dump(json_data, f, indent=2, ensure_ascii=False)

print(json.dumps(json_data))
'''
], capture_output=True, text=True)

if result.returncode != 0:
    print("파싱 실패:")
    print(result.stderr)
    sys.exit(1)

# JSON이 생성됨
json_data = json.loads(result.stdout)
print("\n[Step 1] JSON 생성 완료")
print(f"  cycles: {len(json_data['cycles'])}개")

# Step 2: sch_writer로 .sch 생성
result = subprocess.run([
    sys.executable, '-c',
    '''
import sys
sys.path.insert(0, '.')
from sch_writer import json_to_sch

json_to_sch("demo_ratetest.json", "demo_ratetest.sch")
'''
], capture_output=True, text=True)

if result.returncode != 0:
    print("\n.sch 생성 실패:")
    print(result.stderr)
    sys.exit(1)

print("\n[Step 2] .sch 생성 완료")
print(result.stdout)

# Step 3: 검증
import struct

print("\n[Step 3] 생성된 .sch 검증")
with open('demo_ratetest.sch', 'rb') as f:
    data = f.read()

header_size = 1632
num_steps = (len(data) - header_size) // 612

type_names = {
    3: 'REST', 6: 'END', 7: 'CYCL', 8: 'LOOP',
    0x0101: 'CCCV', 0x0202: 'CCDi',
}

print(f"\n총 {num_steps} 스텝:")
cycle_num = 0
for i in range(num_steps):
    offset = header_size + i * 612
    step_type = struct.unpack_from('<i', data, offset + 8)[0]
    type_name = type_names.get(step_type, '?')

    if type_name == 'CYCL':
        cycle_num += 1
        print(f"\n  [Cycle {cycle_num}]")
    elif type_name == 'END':
        print(f"  {i+1:2d}. {type_name}")
        break
    else:
        info = ''
        if type_name == 'LOOP':
            count = struct.unpack_from('<i', data, offset + 52)[0]
            info = f' (count={count})'
        print(f"  {i+1:2d}. {type_name}{info}")

print("\n" + "=" * 80)
print("✓ 완료!")
print("  - demo_ratetest.sch 업데이트됨")
print("  - 각 사이클: CCCV → REST → CCDi → REST → LOOP")
print("=" * 80)
