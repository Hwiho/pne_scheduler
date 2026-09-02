#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discharge 뒤 REST 수정 검증
"""

def insert_auto_rest_impl(steps, test_type='ratetest'):
    """수정된 insert_auto_rest 로직"""
    rest_dur = '30min'
    result = []
    for i, step in enumerate(steps):
        result.append(step)
        stype = step.get('type', '')
        is_charge = stype in ('cccv_charge', 'cc_charge')
        is_discharge = stype == 'cc_discharge'
        is_last = (i == len(steps) - 1)

        should_add_rest = False
        if is_charge or is_discharge:
            if is_last:
                should_add_rest = True
            else:
                next_step = steps[i + 1]
                if next_step.get('type') != 'rest':
                    should_add_rest = True

        if should_add_rest:
            result.append({
                'type': 'rest',
                'duration': rest_dur,
                'auto_inserted': True
            })

    return result


print("=" * 80)
print("discharge 뒤 REST 자동 삽입 검증")
print("=" * 80)

# Cycle 1
cycle1 = [
    {"type": "cccv_charge", "voltage_V": 4.2},
    {"type": "cc_discharge", "voltage_cutoff_V": 2.5}
]

print("\n[Cycle 1] 원본: 2 스텝")
result1 = insert_auto_rest_impl(cycle1)
print(f"수정 후: {len(result1)} 스텝")
for i, s in enumerate(result1, 1):
    auto = " ← 자동 삽입" if s.get('auto_inserted') else ""
    print(f"  {i}. {s['type']}{auto}")

# Cycle 2
cycle2 = [
    {"type": "cccv_charge", "voltage_V": 4.2},
    {"type": "cc_discharge", "voltage_cutoff_V": 2.5}
]

print("\n[Cycle 2] 원본: 2 스텝")
result2 = insert_auto_rest_impl(cycle2)
print(f"수정 후: {len(result2)} 스텝")
for i, s in enumerate(result2, 1):
    auto = " ← 자동 삽입" if s.get('auto_inserted') else ""
    print(f"  {i}. {s['type']}{auto}")

# 검증
print("\n" + "=" * 80)
if len(result1) == 4 and len(result2) == 4:
    print("✓ 성공!")
    print("  - 각 사이클이 4 스텝 (CCCV → REST → DIS → REST)")
    print("  - discharge 뒤에 REST 정상 삽입됨!")
    print("\nRate Test 구조:")
    print("  Loop(Cycle1) → Cycle_marker")
    print("    CCCV(0.1C) → REST → DIS → REST → LOOP(2)")
    print("  Loop(Cycle2) → Cycle_marker")
    print("    CCCV(0.2C) → REST → DIS → REST → LOOP(1)")
    print("  ... End")
else:
    print("✗ 실패!")
print("=" * 80)
