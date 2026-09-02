#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nl_parser_v2_extended.py -- Rate Test 사이클 파싱 지원
"""

import re
import json
from typing import Dict, List, Optional


class ExtendedParser:
    """자연어 → JSON 파서 (Rate Test 사이클 지원)"""

    def __init__(self):
        self.capacity_mAh = 100.0
        self.test_type = 'cyclelife'
        self.schedule_name = 'schedule'
        self.pre_loop = []
        self.steps = []
        self.cycles = []
        self.loop_count = 1
        self.is_ratetest = False

    def parse(self, text):
        print(f"[파싱] {text[:80]}...")
        self._parse_capacity(text)
        self._parse_test_type(text)
        self._parse_pre_rest(text)

        if self.is_ratetest:
            self._parse_cycles(text)
        else:
            self._parse_loop_count(text)
            self._parse_steps(text)

        self._gen_name()
        return self._build_json()

    def _parse_capacity(self, text):
        m = re.search(r'(\d+(?:\.\d+)?)\s*mAh', text)
        if m:
            self.capacity_mAh = float(m.group(1))

    def _parse_test_type(self, text):
        if re.search(r'레이트|rate.*test|rate.*검사', text, re.I):
            self.test_type = 'ratetest'
            self.is_ratetest = True
        elif re.search(r'수명|cyclelife|cycle.*life', text, re.I):
            self.test_type = 'cyclelife'
        elif re.search(r'DCIR|dcir|임피던스', text, re.I):
            self.test_type = 'dcir'
        elif re.search(r'포메이션|formation', text, re.I):
            self.test_type = 'formation'

    def _parse_pre_rest(self, text):
        self.pre_loop = []
        m = re.search(r'(?:시작.*?)?전에\s*(\d+(?:\.\d+)?)\s*(?:시간|h)', text)
        if m:
            dur = float(m.group(1))
            self.pre_loop.append({
                'type': 'rest',
                'duration': f'{int(dur)}h' if dur == int(dur) else f'{dur}h',
                'record_time': '30s'
            })
            return

        m = re.search(r'(?:시작.*?)?전에\s*(\d+(?:\.\d+)?)\s*(?:분|min)', text)
        if m:
            dur = float(m.group(1))
            self.pre_loop.append({
                'type': 'rest',
                'duration': f'{int(dur)}min' if dur == int(dur) else f'{dur}min',
                'record_time': '30s'
            })

    def _parse_cycles(self, text):
        """Rate Test 사이클 파싱: '0.1C 2사이클, 0.5C 1사이클' → cycles 구조"""
        self.cycles = []

        # 패턴: "0.1C 2사이클" 또는 "0.1C 2회" 또는 "0.1C x2"
        cycle_pattern = r'(\d+(?:\.\d+)?)\s*C(?:\s*(?:x|X))?\s*(\d+)(?:\s*(?:사이클|회|cycle))?'
        matches = re.findall(cycle_pattern, text)

        if not matches:
            # 대체 패턴: 쉼표로 구분된 다중 Rate
            cycle_pattern = r'(\d+(?:\.\d+)?)\s*C\s*(\d+)?'
            matches = re.findall(cycle_pattern, text)

        for c_rate, count_str in matches:
            count = int(count_str) if count_str else 1
            c_rate_float = float(c_rate)

            # 각 사이클의 스텝 생성
            steps = self._create_cycle_steps(c_rate_float, text)

            cycle = {
                'label': f'{c_rate}C',
                'count': count,
                'reset_capacity': True,
                'steps': steps
            }
            self.cycles.append(cycle)

        print(f"  Rate Test 사이클 {len(self.cycles)}개 파싱 완료")

    def _create_cycle_steps(self, c_rate, text):
        """각 사이클의 충방전 스텝 생성"""
        steps = []

        # CCCV 충전 (C-rate 사용)
        m_volt = re.search(r'(\d+(?:\.\d+)?)\s*V', text)
        voltage = float(m_volt.group(1)) if m_volt else 4.2

        steps.append({
            'type': 'cccv_charge',
            'voltage_V': voltage,
            'current': f'{c_rate}C',
            'time_limit': '2d',
            'cv_cutoff': '0.05C',
            'record_time': '30s'
        })

        # CC 방전
        m_dis_v = re.search(r'(\d+(?:\.\d+)?)\s*V\s*까지', text)
        voltage_cutoff = float(m_dis_v.group(1)) if m_dis_v else 2.5

        steps.append({
            'type': 'cc_discharge',
            'current': f'{c_rate}C',
            'voltage_cutoff_V': voltage_cutoff,
            'record_time': '30s'
        })

        return steps

    def _parse_loop_count(self, text):
        m = re.search(r'(\d+)\s*(?:사이클|회|cycle)', text)
        if m:
            self.loop_count = int(m.group(1))

    def _parse_steps(self, text):
        """단일 루프 모드 스텝 파싱"""
        self.steps = []

        # CCCV 충전
        m_volt = re.search(r'(\d+(?:\.\d+)?)\s*V', text)
        m_i_charge = re.search(r'(?:충전|charge).*?(\d+(?:\.\d+)?)\s*C\b', text, re.IGNORECASE | re.DOTALL)
        if not m_i_charge:
            m_i_charge = re.search(r'(\d+(?:\.\d+)?)\s*C.*?(?:충전|charge)', text, re.IGNORECASE | re.DOTALL)

        if m_volt:
            voltage = float(m_volt.group(1))
            current = m_i_charge.group(1) if m_i_charge else '0.05'
            self.steps.append({
                'type': 'cccv_charge',
                'voltage_V': voltage,
                'current': f'{current}C',
                'time_limit': '2d',
                'cv_cutoff': f'{current}C',
                'record_time': '30s'
            })

        # CC 방전
        m_dis_i = re.search(r'(?:방전|discharge).*?(\d+(?:\.\d+)?)\s*C\b', text, re.IGNORECASE | re.DOTALL)
        if not m_dis_i:
            m_dis_i = re.search(r'(\d+(?:\.\d+)?)\s*C.*?(?:방전|discharge)', text, re.IGNORECASE | re.DOTALL)
        m_dis_v = re.search(r'(\d+(?:\.\d+)?)\s*V\s*까지', text)

        if m_dis_i or m_dis_v:
            current_d = m_dis_i.group(1) if m_dis_i else '0.5'
            voltage_d = float(m_dis_v.group(1)) if m_dis_v else 2.5
            self.steps.append({
                'type': 'cc_discharge',
                'current': f'{current_d}C',
                'voltage_cutoff_V': voltage_d,
                'record_time': '30s'
            })

    def _gen_name(self):
        if self.test_type == 'cyclelife':
            self.schedule_name = f'CycleLife_{self.loop_count}cyc'
        elif self.test_type == 'ratetest':
            if self.cycles:
                rates = '_'.join([c['label'] for c in self.cycles])
                self.schedule_name = f'RateTest_{rates}'
            else:
                self.schedule_name = 'RateTest'
        else:
            self.schedule_name = f'{self.test_type}'

    def _build_json(self):
        result = {
            'metadata': {
                'schedule_name': self.schedule_name,
                'test_type': self.test_type,
                'cell_capacity_mAh': self.capacity_mAh,
                'author': 'nl_parser',
                'safety': {
                    'max_voltage_V': 4.3,
                    'min_voltage_V': 2.5,
                    'max_current_mA': self.capacity_mAh * 2,
                    'max_capacity_mAh': self.capacity_mAh,
                    'max_temp_C': 70,
                }
            }
        }

        if self.pre_loop:
            result['pre_loop'] = self.pre_loop

        if self.is_ratetest and self.cycles:
            result['cycles'] = self.cycles
        elif self.steps:
            result['loop'] = {
                'count': self.loop_count,
                'reset_capacity': True,
                'steps': self.steps
            }

        return result


def demo():
    print("\n" + "=" * 80)
    print("Rate Test 사이클 파싱 데모")
    print("=" * 80)

    # 테스트 1: CycleLife
    print("\n[테스트 1] CycleLife")
    nl1 = "100 mAh 셀 0.5C로 50사이클 수명 시험. 시작 전에 3시간 휴지. 충전은 CCCV 4.2V, 0.05C, 방전은 CC 2.5V까지."
    parser1 = ExtendedParser()
    result1 = parser1.parse(nl1)
    print(f"  schedule_name: {result1['metadata']['schedule_name']}")
    print(f"  test_type: {result1['metadata']['test_type']}")
    print(f"  loop.count: {result1['loop']['count']}")

    # 테스트 2: Rate Test
    print("\n[테스트 2] Rate Test")
    nl2 = "100 mAh 셀 Rate test. 0.1C 2사이클, 0.2C 1사이클, 0.5C 1사이클, 1C 1사이클. 충전은 CCCV 4.2V, 방전은 CC 2.5V까지."
    parser2 = ExtendedParser()
    result2 = parser2.parse(nl2)
    print(f"  schedule_name: {result2['metadata']['schedule_name']}")
    print(f"  test_type: {result2['metadata']['test_type']}")
    print(f"  cycles: {len(result2.get('cycles', []))}개")
    if 'cycles' in result2:
        for cyc in result2['cycles']:
            print(f"    - {cyc['label']}: count={cyc['count']}, steps={len(cyc['steps'])}")

    print("\n" + "=" * 80)
    print("생성된 JSON (Rate Test):")
    print("=" * 80)
    print(json.dumps(result2, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    demo()
