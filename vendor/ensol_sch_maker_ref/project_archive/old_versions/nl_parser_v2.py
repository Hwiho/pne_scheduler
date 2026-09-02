#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nl_parser_v2.py -- 자연어 파싱 (간단하고 견고한 버전)
"""

import re
import json
from typing import Dict, List, Optional


class SimpleParser:
    def __init__(self):
        self.capacity_mAh = 100.0
        self.test_type = 'cyclelife'
        self.schedule_name = 'schedule'
        self.pre_loop = []
        self.steps = []
        self.loop_count = 1

    def parse(self, text):
        print(f"[파싱] {text[:80]}...")
        self._parse_capacity(text)
        self._parse_test_type(text)
        self._parse_pre_rest(text)
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

    def _parse_loop_count(self, text):
        m = re.search(r'(\d+)\s*(?:사이클|회|cycle)', text)
        if m:
            self.loop_count = int(m.group(1))

    def _parse_steps(self, text):
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

        if self.steps:
            result['loop'] = {
                'count': self.loop_count,
                'reset_capacity': True,
                'steps': self.steps
            }

        return result


def demo():
    nl_text = "100 mAh 셀 0.5C로 50사이클 수명 시험. 시작 전에 3시간 휴지. 충전은 CCCV 4.2V, 0.05C current cut-off, 2 day limit, 방전은 CC 2.5V까지. 기록 조건은 모든 스텝에서 30초"

    print("\n" + "=" * 80)
    print("자연어 파싱 데모")
    print("=" * 80)
    print(f"\n입력: {nl_text}\n")

    parser = SimpleParser()
    result = parser.parse(nl_text)

    print("\n생성된 JSON:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    demo()
