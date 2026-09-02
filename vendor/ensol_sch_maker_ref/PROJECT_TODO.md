# PROJECT TODO

## ✅ 완료된 기능

- 충전만 수행하는 Charging block 구현
- 방전만 수행하는 Discharging block 구현
- Rest block이 cycle-loop로 닫히도록 구성

---

## 🚧 진행 필요

### 1. Pulse Test 구조 개선

- 충전만 / 방전만 기능이 분리되었으므로  
  기존 Pulse test의 "초기 충전 기능"은 제거 검토
- Pulse test는 아래 구조로 단순화 가능:
  - SOC를 100% 또는 0%로 설정 (충전/방전 block 활용)
  - 이후 Pulse 인가
- 필요한 기능:
  - 충전 방향 기준 SOC 설정
  - 방전 방향 기준 SOC 설정
  - Pulse 인가 기능
- 각 기능은 cycle 및 loop 구조로 닫히도록 구성

---

### 2. Capacity Check 개선

- 단일 실행이 아닌 **여러 cycle 반복 가능하도록 수정**

---

### 3. SOC 관련 기능 개선

- SOC 설정 기준:
  - 기존 `(blk_6)` 대신
  - Capacity Check 하단 표시값 사용
    - 예: `0.1C 충`, `0.1C 방`
- SOC 이동 기능 및 초기 충전 기능 정의 필요
- 충방전 후 Rest 30분 포함 여부 검토 필요

---

### 4. Pulse Step UI/조건 분리

- Pulse 관련 조건 분리 필요:
  - Rest 시간
  - 기록 조건
- SOC 설정 조건과 Pulse 조건을 분리하여 표시

---

### 5. Charging / Discharging 전용 기능

- SOC 설정과 별개로:
  - "충전만 수행"
  - "방전만 수행"
  기능 제공 필요

---

### 6. 입력 및 적용 방식 개선

- 숫자 입력 시 자동 반영 기능 검토
- 또는 아래 방식 고려:
  - 전체 적용 버튼
  - 마지막에 한 번만 저장

---

## 🔮 추후 기능 (우선순위 포함)

### ⭐ 1순위

- SCH 파일 불러오기 기능
- 저장 기능 개선
- Formation 기능 구현

---# PROJECT TODO

## ✅ 완료된 기능

- 충전만 수행하는 Charging block 구현
- 방전만 수행하는 Discharging block 구현
- Rest block이 cycle-loop로 닫히도록 구성

---

## 🚧 진행 필요

### 1. Pulse Test 구조 개선

- 충전만 / 방전만 기능이 분리되었으므로  
  기존 Pulse test의 "초기 충전 기능"은 제거 검토
- Pulse test는 아래 구조로 단순화 가능:
  - SOC를 100% 또는 0%로 설정 (충전/방전 block 활용)
  - 이후 Pulse 인가
- 필요한 기능:
  - 충전 방향 기준 SOC 설정
  - 방전 방향 기준 SOC 설정
  - Pulse 인가 기능
- 각 기능은 cycle 및 loop 구조로 닫히도록 구성

---

### 2. Capacity Check 개선

- 단일 실행이 아닌 **여러 cycle 반복 가능하도록 수정**

---

### 3. SOC 관련 기능 개선

- SOC 설정 기준:
  - 기존 `(blk_6)` 대신
  - Capacity Check 하단 표시값 사용
    - 예: `0.1C 충`, `0.1C 방`
- SOC 이동 기능 및 초기 충전 기능 정의 필요
- 충방전 후 Rest 30분 포함 여부 검토 필요

---

### 4. Pulse Step UI/조건 분리

- Pulse 관련 조건 분리 필요:
  - Rest 시간
  - 기록 조건
- SOC 설정 조건과 Pulse 조건을 분리하여 표시

---

### 5. Charging / Discharging 전용 기능

- SOC 설정과 별개로:
  - "충전만 수행"
  - "방전만 수행"
  기능 제공 필요

---

### 6. 입력 및 적용 방식 개선

- 숫자 입력 시 자동 반영 기능 검토
- 또는 아래 방식 고려:
  - 전체 적용 버튼
  - 마지막에 한 번만 저장

---

## 🔮 추후 기능 (우선순위 포함)

### ⭐ 1순위

- SCH 파일 불러오기 기능
- 저장 기능 개선
- Formation 기능 구현

---
