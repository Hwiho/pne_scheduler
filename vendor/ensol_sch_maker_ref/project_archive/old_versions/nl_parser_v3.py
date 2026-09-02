#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nl_parser_v3.py -- Rate Test + CycleLife 복합 구조 파싱 지원
- 기록 조건 파싱 ('모든 스텝에서 10초')
- CCCV cv_cutoff / time_limit 파싱 ('0.05C current cut-off, 2 day limit')
- Rate Test + 이어서 CycleLife 복합 구조
"""

import re
import json
from typing import Dict, List, Optional


class ScheduleParser:
    """자연어 -> JSON 파서 v3"""

    def __init__(self):
        self.capacity_mAh = 100.0
        self.test_type = 'cyclelife'
        self.schedule_name = 'schedule'
        self.record_time = '30s'

        # Charge/discharge common params
        self.charge_voltage_V = 4.2
        self.cv_cutoff = '0.05C'
        self.time_limit = '2d'
        self.discharge_voltage_V = 2.5

        # Rate Test
        self.is_ratetest = False
        self.cycles = []

        # Single-loop CycleLife
        self.pre_loop = []
        self.steps = []
        self.loop_count = 1

        # Followup CycleLife (after Rate Test)
        self.has_followup = False
        self.followup_pre_loop = []
        self.followup_steps = []
        self.followup_count = 1
        self.followup_c_rate = 0.5

    def parse(self, text):
        print(f"[파싱] {text[:80]}...")
        self._parse_capacity(text)
        self._parse_record_time(text)
        self._parse_charge_params(text)
        self._parse_discharge_params(text)
        self._parse_test_type(text)

        if self.test_type == 'ratetest_cyclelife':
            self._parse_ratetest_cycles(text)
            self._parse_followup_cyclelife(text)
        elif self.is_ratetest:
            self._parse_ratetest_cycles(text)
        else:
            self._parse_pre_rest(text)
            self._parse_loop_count(text)
            self._parse_cyclelife_steps(text)

        self._gen_name()
        return self._build_json()

    # --------------------------------------------------
    # 공통 파라미터 파싱
    # --------------------------------------------------

    def _parse_capacity(self, text):
        m = re.search(r'(\d+(?:\.\d+)?)\s*mAh', text, re.I)
        if m:
            self.capacity_mAh = float(m.group(1))

    def _parse_record_time(self, text):
        """기록 조건: '모든 스텝에서 10초' or '기록 조건 30초'"""
        m = re.search(r'(?:기록|record).*?(\d+)\s*(?:초|s\b)', text, re.I | re.DOTALL)
        if m:
            self.record_time = f'{m.group(1)}s'
            return
        m = re.search(r'(?:기록|record).*?(\d+)\s*(?:분|min)', text, re.I | re.DOTALL)
        if m:
            self.record_time = f'{m.group(1)}min'

    def _parse_charge_params(self, text):
        """CCCV 파라미터: 'CCCV 4.2V, 0.05C current cut-off, 2 day limit'"""
        # 충전 전압
        m = re.search(r'CCCV\s+(\d+(?:\.\d+)?)\s*V', text, re.I)
        if m:
            self.charge_voltage_V = float(m.group(1))

        # CV 컷오프 전류
        m = re.search(r'(\d+(?:\.\d+)?)\s*C\s*(?:current\s*)?cut[-\s]?off', text, re.I)
        if m:
            self.cv_cutoff = f'{m.group(1)}C'

        # 시간 제한
        m = re.search(r'(\d+)\s*day\s*limit', text, re.I)
        if m:
            self.time_limit = f'{m.group(1)}d'

    def _parse_discharge_params(self, text):
        """방전 파라미터: 'CC 2.5V까지'"""
        m = re.search(r'(\d+(?:\.\d+)?)\s*V\s*까지', text)
        if m:
            self.discharge_voltage_V = float(m.group(1))

    def _parse_test_type(self, text):
        has_ratetest = bool(re.search(r'rate\s*test|레이트', text, re.I))
        has_cyclelife = bool(re.search(r'수명\s*시험|cyclelife|cycle\s*life', text, re.I))
        has_followup = bool(re.search(r'이어서', text))

        if has_ratetest and (has_cyclelife or has_followup):
            self.test_type = 'ratetest_cyclelife'
            self.is_ratetest = True
        elif has_ratetest:
            self.test_type = 'ratetest'
            self.is_ratetest = True
        elif has_cyclelife:
            self.test_type = 'cyclelife'
        elif re.search(r'DCIR|dcir', text, re.I):
            self.test_type = 'dcir'
        elif re.search(r'포메이션|formation', text, re.I):
            self.test_type = 'formation'

    # --------------------------------------------------
    # Rate Test 파싱
    # --------------------------------------------------

    def _parse_ratetest_cycles(self, text):
        """Rate Test 사이클: '0.1C 2사이클, 0.2C 1사이클, ...'"""
        self.cycles = []

        # Rate Test 섹션만 추출 ('이어서' 이전 부분)
        rate_section = text
        m_followup = re.search(r'이어서', text)
        if m_followup:
            rate_section = text[:m_followup.start()]

        pattern = r'(\d+(?:\.\d+)?)\s*C\s*(\d+)\s*(?:사이클|회|cycle)?'
        matches = re.findall(pattern, rate_section)

        for c_rate_str, count_str in matches:
            c_rate = float(c_rate_str)
            count = int(count_str)
            steps = self._make_cycle_steps(c_rate)
            self.cycles.append({
                'label': f'{c_rate_str}C',
                'count': count,
                'reset_capacity': True,
                'steps': steps
            })

        print(f"  Rate Test: {len(self.cycles)}개 C-rate 파싱 완료")

    def _make_cycle_steps(self, c_rate):
        """충방전 스텝 페어 생성"""
        return [
            {
                'type': 'cccv_charge',
                'voltage_V': self.charge_voltage_V,
                'current': f'{c_rate}C',
                'time_limit': self.time_limit,
                'cv_cutoff': self.cv_cutoff,
                'record_time': self.record_time
            },
            {
                'type': 'cc_discharge',
                'current': f'{c_rate}C',
                'voltage_cutoff_V': self.discharge_voltage_V,
                'record_time': self.record_time
            }
        ]

    # --------------------------------------------------
    # 복합 구조 (Rate Test + 이어서 CycleLife) 파싱
    # --------------------------------------------------

    def _parse_followup_cyclelife(self, text):
        """'이어서 N사이클 수명 시험' 파싱"""
        m_followup = re.search(r'이어서(.+)', text, re.DOTALL)
        if not m_followup:
            return
        followup_text = m_followup.group(1)

        # C-rate 파싱
        m = re.search(r'(\d+(?:\.\d+)?)\s*C', followup_text)
        self.followup_c_rate = float(m.group(1)) if m else 0.5

        # 사이클 수
        m = re.search(r'(\d+)\s*(?:사이클|회|cycle)', followup_text)
        if m:
            self.followup_count = int(m.group(1))

        # pre_loop (시작 전 휴지) - followup 섹션 또는 전체 텍스트에서 탐색
        m_rest = re.search(r'(\d+(?:\.\d+)?)\s*(?:시간|h)\s*휴지', text)
        if not m_rest:
            m_rest = re.search(r'시작\s*전에\s*(\d+(?:\.\d+)?)\s*(?:시간|h)', followup_text)
        if m_rest:
            dur = float(m_rest.group(1))
            dur_str = f'{int(dur)}h' if dur == int(dur) else f'{dur}h'
            self.followup_pre_loop = [{
                'type': 'rest',
                'duration': dur_str,
                'record_time': self.record_time
            }]

        # followup 스텝 (CCCV + CC_Dis)
        self.followup_steps = self._make_cycle_steps(self.followup_c_rate)
        self.has_followup = True

        print(f"  Followup CycleLife: {self.followup_c_rate}C, {self.followup_count}사이클 파싱 완료")

    # --------------------------------------------------
    # 단일 CycleLife 파싱
    # --------------------------------------------------

    def _parse_pre_rest(self, text):
        self.pre_loop = []
        m = re.search(r'(?:시작.*?)?전에\s*(\d+(?:\.\d+)?)\s*(?:시간|h)', text)
        if m:
            dur = float(m.group(1))
            self.pre_loop.append({
                'type': 'rest',
                'duration': f'{int(dur)}h' if dur == int(dur) else f'{dur}h',
                'record_time': self.record_time
            })

    def _parse_loop_count(self, text):
        m = re.search(r'(\d+)\s*(?:사이클|회|cycle)', text)
        if m:
            self.loop_count = int(m.group(1))

    def _parse_cyclelife_steps(self, text):
        m = re.search(r'(\d+(?:\.\d+)?)\s*C', text)
        c_rate = float(m.group(1)) if m else 0.5
        self.steps = self._make_cycle_steps(c_rate)

    # --------------------------------------------------
    # JSON 빌드
    # --------------------------------------------------

    def _gen_name(self):
        if self.test_type == 'ratetest_cyclelife':
            rates = '_'.join([c['label'] for c in self.cycles])
            self.schedule_name = f'RateTest_{rates}_CycleLife_{self.followup_count}cyc'
        elif self.test_type == 'ratetest':
            rates = '_'.join([c['label'] for c in self.cycles])
            self.schedule_name = f'RateTest_{rates}'
        elif self.test_type == 'cyclelife':
            self.schedule_name = f'CycleLife_{self.loop_count}cyc'
        else:
            self.schedule_name = self.test_type

    def _build_json(self):
        result = {
            'metadata': {
                'schedule_name': self.schedule_name,
                'test_type': self.test_type,
                'cell_capacity_mAh': self.capacity_mAh,
                'author': 'nl_parser_v3',
                'safety': {
                    'max_voltage_V': round(self.charge_voltage_V + 0.1, 1),
                    'min_voltage_V': round(self.discharge_voltage_V, 1),
                    'max_current_mA': self.capacity_mAh * 2,
                    'max_capacity_mAh': self.capacity_mAh,
                    'max_temp_C': 70,
                }
            }
        }

        if self.test_type == 'ratetest_cyclelife':
            result['cycles'] = self.cycles
            if self.has_followup:
                result['followup'] = {
                    'pre_loop': self.followup_pre_loop,
                    'loop': {
                        'count': self.followup_count,
                        'reset_capacity': True,
                        'steps': self.followup_steps
                    }
                }
        elif self.is_ratetest:
            if self.pre_loop:
                result['pre_loop'] = self.pre_loop
            result['cycles'] = self.cycles
        else:
            if self.pre_loop:
                result['pre_loop'] = self.pre_loop
            result['loop'] = {
                'count': self.loop_count,
                'reset_capacity': True,
                'steps': self.steps
            }

        return result


if __name__ == '__main__':
    import sys
    text = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "100 mAh 셀 Rate test. 0.1C 2사이클, 0.2C 1사이클, 0.5C 1사이클, 1C 1사이클. "
        "이어서 0.5C로 50사이클 수명 시험. 시작 전에 3시간 휴지. "
        "충전은 CCCV 4.2V, 0.05C current cut-off, 2 day limit, 방전은 CC 2.5V까지. "
        "기록 조건은 모든 스텝에서 10초"
    )
    parser = ScheduleParser()
    result = parser.parse(text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
