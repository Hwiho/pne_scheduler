#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_rest 기능 테스트 스크립트
"""
import sys
import os

# sch_writer와 sch_reader import
sys.path.insert(0, os.path.dirname(__file__))
from sch_writer import json_to_sch, insert_auto_rest
from sch_reader import sch_to_json

def test_auto_rest():
    print("=" * 70)
    print("자동 Rest 기능 테스트")
    print("=" * 70)

    # Test 1: CycleLife (rest 없음)
    print("\n[테스트 1] CycleLife (test_type='cyclelife')")
    print("  기대: 충방전 뒤 Rest 없음")

    json_path_1 = "test_cyclelife_auto_rest.json"
    sch_path_1 = "test_cyclelife_auto_rest.sch"

    try:
        json_to_sch(json_path_1, sch_path_1)

        # 역변환해서 스텝 확인
        result = sch_to_json(sch_path_1)
        loop_steps = result.get('loop', {}).get('steps', [])

        print(f"  생성된 루프 스텝 수: {len(loop_steps)}")
        for i, step in enumerate(loop_steps, 1):
            stype = step.get('type')
            if stype == 'rest':
                dur = step.get('duration')
                print(f"    Step {i}: REST (duration={dur}s)")
            else:
                print(f"    Step {i}: {stype.upper()}")

        # 기대: CCCV, CC_DIS (rest 없음)
        expected_count = 2
        actual_count = len(loop_steps)
        if actual_count == expected_count:
            print(f"  ✓ 통과: 예상대로 {expected_count}개 스텝")
        else:
            print(f"  ✗ 실패: 기대 {expected_count}개, 실제 {actual_count}개")
    except Exception as e:
        print(f"  ✗ 오류: {e}")

    # Test 2: RateTest (30분 rest 자동 삽입)
    print("\n[테스트 2] RateTest (test_type='ratetest')")
    print("  기대: 각 충방전 뒤 1800초(30분) Rest 자동 삽입")

    json_path_2 = "test_ratetest_auto_rest.json"
    sch_path_2 = "test_ratetest_auto_rest.sch"

    try:
        json_to_sch(json_path_2, sch_path_2)

        # 역변환해서 사이클 구조 확인
        result = sch_to_json(sch_path_2)
        cycles = result.get('cycles', [])

        print(f"  생성된 사이클 수: {len(cycles)}")
        for ci, cyc in enumerate(cycles, 1):
            print(f"\n  Cycle {ci}: {cyc.get('label')} (count={cyc.get('count')})")
            steps = cyc.get('steps', [])
            print(f"    스텝 수: {len(steps)}")
            for si, step in enumerate(steps, 1):
                stype = step.get('type')
                if stype == 'rest':
                    dur = step.get('duration')
                    print(f"      {si}. REST (duration={dur}s)")
                else:
                    print(f"      {si}. {stype.upper()}")

        # Cycle 1 확인: CCCV, REST(1800), CC_DIS, REST(1800) = 4개
        if len(cycles) >= 1 and len(cycles[0].get('steps', [])) == 4:
            print("\n  ✓ 통과: Cycle 1에서 CCCV→REST→DIS→REST 구조 확인")
        else:
            print(f"\n  ✗ 실패: Cycle 1 스텝 수가 {len(cycles[0].get('steps', []))}개 (기대: 4개)")
    except Exception as e:
        print(f"  ✗ 오류: {e}")

    print("\n" + "=" * 70)

if __name__ == '__main__':
    test_auto_rest()
