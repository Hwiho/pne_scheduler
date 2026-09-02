# -*- coding: utf-8 -*-
"""
natural_language_parser.py -- 배터리 시험 자연어를 JSON 스케줄로 변환
=====================================================================
사용자의 자연어 설명을 JSON 중간표현으로 변환합니다.

사용법:
    python natural_language_parser.py
    >>> parser = ScheduleParser()
    >>> json_data = parser.parse("100 mAh 셀 0.5C로 50사이클 수명 시험...")
"""

import re
import json
from typing import Dict, List, Optional, Tuple


class ScheduleParser:
    """배터리 시험 일정을 자연어에서 JSON으로 파싱"""

    def __init__(self):
        self.capacity_mAh = None
        self.test_type = None
        self.schedule_name = None
        self.pre_loop = []
        self.main_steps = []
        self.cycle_groups = []
        self.loop_count = 1
        self.reset_capacity = True
        self.record_time_default = '30s'

    def parse(self, text: str) -> Dict:
        """자연어 텍스트를 JSON 스케줄로 변환"""
        print(f"[파싱 시작] 입력 텍스트:")
        print(f"  {text[:100]}...")

        self._extract_cell_capacity(text)
        self._extract_test_type(text)
        self._extract_pre_loop(text)
        self._extract_steps(text)
        self._generate_schedule_name()

        result = self._build_json()
        print(f"[파싱 완료] test_type={self.test_type}, steps={len(self.main_steps)}")
        return result

    def _extract_cell_capacity(self, text: str):
        """셀 용량 추출: '100 mAh', '200mAh' 등"""
        patterns = [
            r'(\d+)\s*mAh',
            r'(\d+)\s*m[Aa][Hh]',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                self.capacity_mAh = float(match.group(1))
                print(f"  셀 용량: {self.capacity_mAh} mAh")
                return

        self.capacity_mAh = 100.0  # 기본값
        print(f"  셀 용량: {self.capacity_mAh} mAh (기본값)")

    def _extract_test_type(self, text: str):
        """시험 유형 추출: 수명, Rate Test, DCIR, Formation 등"""
        # 우선순위 순서대로 확인
        type_patterns = [
            (r'레이트\s*테스트|rate\s*test|rate\s*?검사', 'ratetest'),
            (r'수명\s*시험|cycle\s*life|cyclelife', 'cyclelife'),
            (r'(?:DCIR|dcir|임피던스|impedance)', 'dcir'),
            (r'포메이션|formation|초기화', 'formation'),
            (r'임피던스|impedance', 'impedance'),
        ]

        for pattern, test_type in type_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                self.test_type = test_type
                print(f"  시험 유형: {self.test_type}")
                return

        self.test_type = 'cyclelife'  # 기본값
        print(f"  시험 유형: {self.test_type} (기본값)")

    def _extract_pre_loop(self, text: str):
        """사전 처리 단계 추출: '시작 전에 3시간 휴지' 등"""
        self.pre_loop = []

        # Rest 패턴: "N시간 휴지", "30분 rest" 등
        rest_patterns = [
            r'(?:시작\s*)?전에\s*(\d+(?:\.\d+)?)\s*(?:시간|hour)',  # 시간
            r'(?:시작\s*)?전에\s*(\d+(?:\.\d+)?)\s*(?:분|minute|min)',  # 분
            r'(?:초기\s*)?휴지\s*(\d+(?:\.\d+)?)\s*(?:시간|hour)',
            r'pre\s*(?:rest|休止)\s*(\d+(?:\.\d+)?)\s*(?:[hH]|hour)',
        ]

        for pattern in rest_patterns:
            match = re.search(pattern, text)
            if match:
                duration_val = float(match.group(1))
                # 시간인지 분인지 판단
                if 'hour' in pattern.lower() or '시간' in pattern:
                    duration_str = f"{duration_val}h"
                else:
                    duration_str = f"{duration_val}min"

                self.pre_loop.append({
                    'type': 'rest',
                    'duration': duration_str,
                    'record_time': self.record_time_default
                })
                print(f"  사전 Rest: {duration_str}")
                return

    def _extract_steps(self, text: str):
        """충전/방전 스텝 추출"""
        self.main_steps = []

        # 사이클 또는 반복 수 추출
        cycle_patterns = [
            r'(\d+)\s*(?:사이클|cycle|cycl)',
            r'(\d+)\s*(?:회|번)',
        ]
        for pattern in cycle_patterns:
            match = re.search(pattern, text)
            if match:
                self.loop_count = int(match.group(1))
                print(f"  반복 수: {self.loop_count}회")
                break

        # 충전 스텝 추출
        charge_step = self._extract_charge_step(text)
        if charge_step:
            self.main_steps.append(charge_step)
            print(f"  충전 스텝: {charge_step.get('type')}")

        # 방전 스텝 추출
        discharge_step = self._extract_discharge_step(text)
        if discharge_step:
            self.main_steps.append(discharge_step)
            print(f"  방전 스텝: {discharge_step.get('type')}")

    def _extract_charge_step(self, text: str) -> Optional[Dict]:
        """충전 스텝 추출: CCCV 또는 CC"""
        # CCCV 패턴 찾기
        cccv_pattern = r'충전.*?CCCV|CCCV.*?충전'
        if re.search(cccv_pattern, text, re.IGNORECASE):
            # 전압 추출
            voltage_pattern = r'(\d+(?:\.\d+)?)\s*V'
            voltage_match = re.search(voltage_pattern, text)
            voltage = voltage_match.group(1) if voltage_match else '4.2'

            # 전류 추출 (C-rate 또는 mA)
            current = self._extract_current(text, for_charge=True)

            # CV cutoff 추출
            cv_cutoff_pattern = r'(?:current\s*)?cut[_-]?off|CV\s*(?:cutoff|cut-off)'
            cv_match = re.search(cv_cutoff_pattern, text, re.IGNORECASE)
            cv_cutoff = self._extract_current(text, is_cutoff=True) if cv_match else '0.05C'

            # 시간 제한 추출
            time_limit = self._extract_time_limit(text)

            return {
                'type': 'cccv_charge',
                'voltage_V': float(voltage),
                'current': current,
                'time_limit': time_limit,
                'cv_cutoff': cv_cutoff,
                'record_time': self.record_time_default
            }

        return None

    def _extract_discharge_step(self, text: str) -> Optional[Dict]:
        """방전 스텝 추출"""
        discharge_pattern = r'방전|discharge|di[scharging]+'
        if not re.search(discharge_pattern, text, re.IGNORECASE):
            return None

        # 방전 전류
        current = self._extract_current(text, for_discharge=True)

        # 방전 종료 전압
        voltage_cutoff_pattern = r'(\d+(?:\.\d+)?)\s*V\s*까지'
        voltage_match = re.search(voltage_cutoff_pattern, text)
        voltage_cutoff = float(voltage_match.group(1)) if voltage_match else 2.5

        return {
            'type': 'cc_discharge',
            'current': current,
            'voltage_cutoff_V': voltage_cutoff,
            'record_time': self.record_time_default
        }

    def _extract_current(self, text: str, for_charge=False, for_discharge=False, is_cutoff=False) -> str:
        """전류 추출: C-rate 또는 mA"""
        patterns = [
            r'(\d+(?:\.\d+)?)\s*C\b',  # 0.5C, 1C 등
            r'(\d+(?:\.\d+)?)\s*mA',  # mA 단위
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                if is_cutoff and len(matches) >= 2:
                    return f"{matches[1]}C"
                elif for_discharge and len(matches) >= 2:
                    return f"{matches[1]}C"
                else:
                    return f"{matches[0]}C" if 'C' in pattern else f"{matches[0]}mA"

        # 기본값
        if for_discharge:
            return '0.5C'
        return '0.1C'

    def _extract_time_limit(self, text: str) -> str:
        """충전 시간 제한 추출: '2 day limit' 등"""
        time_patterns = [
            (r'(\d+)\s*day', 'd'),
            (r'(\d+)\s*(?:시간|hour)', 'h'),
            (r'(\d+)\s*(?:분|minute|min)', 'min'),
        ]

        for pattern, unit in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1)
                return f"{val}{unit}"

        return '2d'  # 기본값

    def _generate_schedule_name(self):
        """스케줄 이름 생성"""
        if self.test_type == 'ratetest':
            self.schedule_name = 'RateTest'
        elif self.test_type == 'cyclelife':
            self.schedule_name = f'CycleLife_{self.loop_count}cyc'
        else:
            self.schedule_name = f'{self.test_type.capitalize()}'

        print(f"  스케줄 이름: {self.schedule_name}")

    def _build_json(self) -> Dict:
        """최종 JSON 구조 생성"""
        result = {
            'metadata': {
                'schedule_name': self.schedule_name,
                'test_type': self.test_type,
                'cell_capacity_mAh': self.capacity_mAh,
                'author': 'parsed_from_natural_language',
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

        if self.main_steps:
            result['loop'] = {
                'count': self.loop_count,
                'reset_capacity': self.reset_capacity,
                'steps': self.main_steps
            }

        return result


def main():
    """테스트"""
    parser = ScheduleParser()

    # 테스트 케이스 1: CycleLife
    text1 = "100 mAh 셀 0.5C로 50사이클 수명 시험. 시작 전에 3시간 휴지. 충전은 CCCV 4.2V, 0.05C current cut-off, 2 day limit, 방전은 CC 2.5V까지. 기록 조건은 모든 스텝에서 30초"
    print("\n" + "=" * 80)
    print("[테스트 1] CycleLife 파싱")
    print("=" * 80)
    result1 = parser.parse(text1)
    print("\n생성된 JSON:")
    print(json.dumps(result1, indent=2, ensure_ascii=False))

    # 테스트 케이스 2: Rate Test (간단한 버전)
    parser2 = ScheduleParser()
    text2 = "100 mAh 셀 Rate test. 0.1C 2사이클, 0.5C 1사이클. 충전 4.2V CCCV, 방전 2.5V CC."
    print("\n" + "=" * 80)
    print("[테스트 2] Rate Test 파싱 (미리보기)")
    print("=" * 80)
    result2 = parser2.parse(text2)
    print("\n생성된 JSON (구조만):")
    print(f"  test_type: {result2['metadata']['test_type']}")
    print(f"  schedule_name: {result2['metadata']['schedule_name']}")
    print(f"  loop: {result2.get('loop', {})}")


if __name__ == '__main__':
    main()
