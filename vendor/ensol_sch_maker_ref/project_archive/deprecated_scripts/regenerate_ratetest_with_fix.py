#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regenerate demo_ratetest.sch using fixed insert_auto_rest logic
"""

import json
import sys
import struct

sys.path.insert(0, '.')

print("=" * 80)
print("Regenerating Rate Test .sch with corrected REST insertion")
print("=" * 80)

# Step 1: Parse natural language to JSON
from nl_parser_v2_extended import ExtendedParser

nl_text = "100 mAh 셀 Rate test. 0.1C 2사이클, 0.2C 1사이클, 0.5C 1사이클, 1C 1사이클. 충전은 CCCV 4.2V, 방전은 CC 2.5V까지."

parser = ExtendedParser()
json_data = parser.parse(nl_text)

# Save JSON
with open("demo_ratetest.json", "w", encoding="utf-8") as f:
    json.dump(json_data, f, indent=2, ensure_ascii=False)

print("\n[Step 1] JSON generation completed")
print(f"  cycles: {len(json_data['cycles'])}개")
for cyc in json_data['cycles']:
    print(f"    - {cyc['label']}: count={cyc['count']}, {len(cyc['steps'])} steps")

# Step 2: Generate .sch using sch_writer_fixed
from sch_writer_fixed import json_to_sch

print("\n[Step 2] Generating .sch file...")
json_to_sch("demo_ratetest.json", "demo_ratetest.sch")
print("  .sch file generated successfully")

# Step 3: Verify the generated .sch file
print("\n[Step 3] Verification of generated .sch")
with open('demo_ratetest.sch', 'rb') as f:
    data = f.read()

header_size = 1632
num_steps = (len(data) - header_size) // 612

type_names = {
    3: 'REST', 6: 'END', 7: 'CYCL', 8: 'LOOP',
    0x0101: 'CCCV', 0x0202: 'CCDi',
}

print(f"\nTotal {num_steps} steps:")
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
print("Regeneration complete!")
print("  - demo_ratetest.sch updated with corrected REST insertion")
print("  - Expected: CCCV → REST(30min) → CCDi → REST(30min) → LOOP per cycle")
print("=" * 80)
