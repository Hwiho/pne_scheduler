# sch_current_rescaler 유효숫자 개선 계획

작성일: 2026-04-28

## 목표

`sch_current_rescaler`에서 0.1C, 0.33C, 0.5C 같은 C-rate 기반 전류를 다룰 때 `32.999999`, `0.330000013`, `49.999996`처럼 거슬리는 숫자가 CLI/GUI 로그에 노출되는 문제를 줄인다.

핵심 원칙은 세 가지다.

1. C-rate는 사용자가 의도한 실험 조건에 맞게 소수점 둘째 자리까지 정규화한다.
2. 전류 mA는 소수점 셋째 자리까지 정규화한다.
3. 사용자에게 보여주는 값과 `.sch`에 쓰는 논리적 저장값이 일치해야 한다.

## 현재 문제 지점

변경 대상의 중심 파일은 다음 두 개다.

- `battery_scheduler/sch_current_rescaler.py`
- `battery_scheduler/sch_current_rescaler_gui.py`

현재 `sch_current_rescaler.py`는 전류를 다음 방식으로 계산한다.

```python
factor = float(new_capacity_mAh) / float(old_capacity_mAh)
new_current = old_current * factor
write_f32(block, OFF_CURR, new_current)
```

그리고 출력은 `%g` 계열 포맷을 직접 사용한다.

```python
c_rate = "-" if item["c_rate"] is None else "%.6g" % item["c_rate"]
print("%5s  %-12s  %-12s  %10.6g  %10s" % (...))
```

GUI도 같은 형태로 직접 문자열을 만든다.

```python
"%5s  %-12s  %-12s  %10.6g  %10s"
% (item["step"], item["kind"], item["field"], item["value"], c_rate)
```

문제는 두 종류다.

- binary32 float 자체가 0.1, 0.33 같은 값을 정확히 표현하지 못한다.
- 출력 포맷이 domain-friendly rounding을 하지 않아 내부 표현 오차가 사용자에게 드러난다.

## 접근 방식

### 1. 표시값만 숨기지 않고 canonical 값을 만든다

기존 계획처럼 로그에서만 숫자를 예쁘게 보이게 하면 `.sch` 내부 전류값과 사용자가 본 값이 어긋날 수 있다. 이번 개선의 기준은 “표시값과 저장값의 논리적 일치”이다.

따라서 변환 과정에서 다음 순서로 canonical 값을 만든다.

1. 원본 전류와 기존 셀 용량으로 원본 C-rate를 계산한다.
2. C-rate를 소수점 둘째 자리까지 정규화한다.
3. 정규화된 C-rate에 새 셀 용량을 곱한다.
4. 새 전류를 소수점 셋째 자리까지 정규화한다.
5. 이 정규화된 전류를 `.sch`에 쓴다.
6. CLI/GUI 로그도 같은 canonical 값을 표시한다.

예:

```text
old current 32.999996 mA, old capacity 100 mAh
raw C-rate  0.32999996C
canonical   0.33C

new capacity 120 mAh
new current  39.600 mA
```

이 접근은 내부 전류값이 “입력한 새 cell 용량의 0.5배, 0.33배, 0.1배”가 되도록 맞추는 방식이다.

### 2. 공통 포맷터를 도입한다

새 헬퍼는 `sch_current_rescaler.py`에 둔다.

```python
CURRENT_DIGITS = 3
C_RATE_DIGITS = 2


def format_number(value, digits):
    """Return a compact, stable decimal string for user-facing logs."""
    if value is None:
        return "-"
    rounded = round(float(value), digits)
    text = ("%.*f" % (digits, rounded)).rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text


def format_mA(value):
    return format_number(value, digits=CURRENT_DIGITS)


def format_c_rate(value):
    return format_number(value, digits=C_RATE_DIGITS)
```

예상 출력:

```text
33.0000000004  -> 33
32.9999961853  -> 33
0.330000013    -> 0.33
0.100000001    -> 0.1
```

전류는 최대 소수점 셋째 자리, C-rate는 최대 소수점 둘째 자리로 표시한다. trailing zero는 기본적으로 제거하되, 필요하면 후속 단계에서 `33.000`처럼 고정 소수 표시 옵션을 둘 수 있다.

### 3. 변환 로직은 C-rate 기준으로 재계산한다

`old_current * factor` 방식은 원본 float32 오차를 그대로 끌고 간다. 대신 원본 C-rate를 먼저 정규화한 다음 새 용량 기준 전류를 다시 계산한다.

```python
CURRENT_DIGITS = 3
C_RATE_DIGITS = 2


def canonical_c_rate(current_mA, capacity_mAh, digits=C_RATE_DIGITS):
    return round(float(current_mA) / float(capacity_mAh), digits)


def current_from_c_rate(c_rate, capacity_mAh, digits=CURRENT_DIGITS):
    return round(float(c_rate) * float(capacity_mAh), digits)


def scale_current_fields(
    data,
    old_capacity_mAh,
    new_capacity_mAh,
    current_digits=CURRENT_DIGITS,
    c_rate_digits=C_RATE_DIGITS,
):
    ...
    old_c = canonical_c_rate(old_current, old_capacity_mAh, c_rate_digits)
    new_current = current_from_c_rate(old_c, new_capacity_mAh, current_digits)
    write_f32(block, OFF_CURR, new_current)
```

summary에는 raw C-rate와 canonical C-rate를 둘 다 남기면 검토가 쉬워진다.

```python
changes.append({
    "step": step_num,
    "field": "current_mA",
    "kind": step_kind(type_code),
    "old": old_current,
    "new": new_current,
    "old_c_raw": old_current / old_capacity_mAh,
    "old_c": old_c,
    "new_c": new_current / new_capacity_mAh,
})
```

표시에는 `old_c`와 `new_c`를 사용한다. 이렇게 하면 로그에 보이는 C-rate와 저장 전류를 만든 C-rate가 같은 기준을 따른다.

### 4. 자릿수는 옵션화하되 기본값을 명확히 둔다

기본 정책은 다음과 같다.

```text
C-rate: 소수점 2자리
전류:   소수점 3자리 mA
```

CLI에는 고급 사용자를 위해 옵션을 추가한다.

```python
parser.add_argument(
    "--current-digits",
    type=int,
    default=3,
    help="Decimal places for written and displayed current values",
)
parser.add_argument(
    "--c-rate-digits",
    type=int,
    default=2,
    help="Decimal places used to canonicalize C-rate values",
)
```

호출부:

```python
out, summary = scale_current_fields(
    src,
    args.old_capacity_mAh,
    args.new_capacity_mAh,
    current_digits=args.current_digits,
    c_rate_digits=args.c_rate_digits,
)
```

GUI는 1차에서는 옵션 입력을 노출하지 않고 기본값인 전류 3자리, C-rate 2자리를 사용한다. 사용자 혼란을 줄이기 위해 GUI 로그 상단에 적용 정책을 명시한다.

```text
정규화 정책: C-rate 소수점 2자리, 전류 소수점 3자리 mA
```

### 5. summary에는 raw 값과 canonical 값을 구분한다

기존 summary dict에는 `old`, `new`, `old_c`, `new_c`가 float로 들어간다. 여기에 문자열을 섞으면 후속 코드가 불편해지므로, 내부 summary는 숫자 그대로 유지하고 출력 함수에서만 포맷한다.

다만 새 구조에서는 raw 계산값과 canonical 값을 구분한다.

- `old_c_raw`: 원본 float32 전류 / old capacity
- `old_c`: 정규화된 C-rate. 새 전류 계산에 사용한 값
- `new`: `.sch`에 쓴 canonical 전류값
- `new_c`: `new / new_capacity_mAh`

```python
def print_summary(summary, limit=None):
    ...
    for ch in shown:
        print(
            "%5s  %-12s  %-12s  %10s  %10s  %s -> %s"
            % (
                ch["step"],
                ch["kind"],
                ch["field"],
                format_mA(ch["old"]),
                format_mA(ch["new"]),
                format_c_rate(ch["old_c"]),
                format_c_rate(ch["new_c"]),
            )
        )
```

이렇게 하면 테스트와 GUI는 float summary를 계속 사용할 수 있고, 사용자 출력만 안정화된다.

### 6. GUI는 CLI 포맷터를 재사용한다

`sch_current_rescaler_gui.py`에서 포맷 문자열을 직접 만들지 않고 `format_mA`, `format_c_rate`를 import한다.

```python
from sch_current_rescaler import (
    collect_current_fields,
    format_c_rate,
    format_mA,
    scale_current_fields,
)
```

원본 전류 표시:

```python
c_rate = format_c_rate(item["c_rate"])
self.write_log(
    "%5s  %-12s  %-12s  %10s  %10s"
    % (
        item["step"],
        item["kind"],
        item["field"],
        format_mA(item["value"]),
        c_rate,
    )
)
```

변환 로그:

```python
self.write_log(
    "%5s  %-12s  %-12s  %10s  %10s  %s -> %s"
    % (
        ch["step"],
        ch["kind"],
        ch["field"],
        format_mA(ch["old"]),
        format_mA(ch["new"]),
        format_c_rate(ch["old_c"]),
        format_c_rate(ch["new_c"]),
    )
)
```

### 7. GUI 옵션은 2단계로 미룬다

CLI에는 `--current-digits`, `--c-rate-digits`를 추가하되, GUI에는 처음부터 자릿수 옵션을 넣지 않는 편이 낫다. GUI에 입력칸을 추가하면 사용자가 실험 조건 정규화 정책을 매번 고민해야 한다.

1차 GUI 개선은 기본 정책을 고정 적용한다. 자릿수 조정이 실제로 필요하다는 피드백이 있으면 GUI에 다음 옵션을 추가한다.

```text
C-rate 자릿수: [2]
전류 자릿수:   [3]
```

## 변경될 파일 경로

### 1차 변경

- `battery_scheduler/sch_current_rescaler.py`
  - `format_number()`, `format_mA()`, `format_c_rate()` 추가
  - `canonical_c_rate()`, `current_from_c_rate()` 추가
  - `print_current_fields()` 출력 포맷 변경
  - `print_summary()` 출력 포맷 변경
  - `scale_current_fields(..., current_digits=3, c_rate_digits=2)` 정책 반영
  - CLI `--current-digits`, `--c-rate-digits` 옵션 추가

- `battery_scheduler/sch_current_rescaler_gui.py`
  - CLI 모듈의 포맷터 import
  - 원본 전류 목록 로그 포맷 변경
  - 변환 결과 로그 포맷 변경
  - 로그에 정규화 정책 표시

### 선택적 후속 변경

- `battery_scheduler/sch_current_rescaler_gui.py`
  - C-rate/전류 자릿수 입력 UI 추가
  - `scale_current_fields(..., current_digits=..., c_rate_digits=...)` 연동

- `battery_scheduler/tests/test_sch_current_rescaler.py`
  - 새 테스트 파일 추가
  - 현재 프로젝트에는 테스트 디렉터리가 없으므로 도입 시 새로 생성

## 테스트 계획

테스트가 아직 없으므로 최소한 스크립트 수준 검증을 먼저 추가한다.

### 포맷터 단위 테스트 후보

```python
def test_format_c_rate_hides_float_noise():
    assert format_c_rate(0.10000000149011612) == "0.1"
    assert format_c_rate(0.33000001311302185) == "0.33"
    assert format_c_rate(0.5) == "0.5"


def test_format_mA_uses_three_decimals():
    assert format_mA(32.9999961853) == "33"
    assert format_mA(39.5999999) == "39.6"
    assert format_mA(12.34567) == "12.346"
```

### 변환 동작 테스트 후보

```python
def test_scale_current_fields_uses_canonical_c_rate():
    out, summary = scale_current_fields(src, 100, 330)
    change = summary["changes"][0]
    assert change["old_c"] == 0.33
    assert change["new"] == 108.9
```

### 자릿수 옵션 테스트 후보

```python
def test_digit_options_affect_canonical_values():
    out, summary = scale_current_fields(src, 100, 330, current_digits=2, c_rate_digits=1)
    change = summary["changes"][0]
    assert change["old_c"] == 0.3
    assert change["new"] == 99.0
```

주의: 위 스니펫의 `src`는 최소 `.sch` fixture가 필요하다. fixture를 만들 때는 1632-byte header + 612-byte CCCV step + END step 형태로 충분하다.

## 트레이드오프 분석

### 표시만 반올림하는 방식

장점:

- 장비에 전달되는 `.sch` 값이 바뀌지 않는다.
- 기존 변환 결과와 binary compatibility가 가장 높다.
- CLI와 GUI 로그의 불편한 숫자를 빠르게 개선한다.
- 테스트 범위가 작다.

단점:

- 바이너리 내부에는 여전히 float32 표현 오차가 남는다.
- 다른 도구로 `.sch`를 읽으면 비슷한 숫자가 다시 보일 수 있다.
- 저장값과 표시값이 서로 다를 수 있어 사용자가 실제 입력 전류를 오해할 수 있다.

결론: 이번 요구에는 맞지 않으므로 채택하지 않는다.

### C-rate 정규화 후 저장 전류 재계산 방식

장점:

- 저장 전류가 새 cell 용량의 0.1배, 0.33배, 0.5배 같은 실험 조건과 직접 대응한다.
- CLI/GUI 표시값과 `.sch`에 쓰는 논리적 값이 일치한다.
- 원본 float32 noise를 다음 파일로 전파하지 않는다.
- 다른 reader/importer에서도 깔끔한 값이 나올 가능성이 높다.

단점:

- 원본이 0.333C, 0.025C처럼 두 자리보다 세밀한 C-rate를 의도한 경우 정보가 손실된다.
- 기본 동작이 기존 `old_current * factor`와 달라진다.
- CV cutoff처럼 0.05C는 괜찮지만, 0.025C 같은 컷오프를 쓰는 파일은 기본 2자리 정책이 과할 수 있다.

대응:

- 기본 정책은 C-rate 2자리, 전류 3자리로 둔다.
- CLI에는 `--c-rate-digits`, `--current-digits`를 제공해 세밀한 파일을 처리할 수 있게 한다.
- summary에 `old_c_raw`를 남겨 정규화 전 값도 검토 가능하게 한다.

결론: 이번 요구의 기본 구현안으로 채택한다.

### Decimal 사용

`Decimal`을 사용해 factor와 intermediate 값을 계산하는 방법도 있다.

```python
from decimal import Decimal

factor = Decimal(str(new_capacity_mAh)) / Decimal(str(old_capacity_mAh))
new_current = float(Decimal(str(old_current)) * factor)
```

장점:

- decimal 입력값 기준의 계산 의도가 더 명확하다.

단점:

- 원본 `.sch`의 `old_current`는 이미 float32에서 온 값이라 Decimal로 바꿔도 원천 오차가 사라지지 않는다.
- 결국 `.sch`에 다시 float32로 저장해야 한다.
- 현재 요구는 “의도 C-rate로 정규화한 뒤 저장 전류와 표시 전류를 맞추는 것”이므로 Decimal만으로는 충분하지 않다.

결론적으로 Decimal 전면 도입은 우선순위가 낮다. 필요하다면 `canonical_c_rate()` 내부 계산을 보조하는 수준으로만 검토한다.

## 권장 구현 순서

1. [x] `sch_current_rescaler.py`에 `CURRENT_DIGITS = 3`, `C_RATE_DIGITS = 2` 상수를 추가한다.
2. [x] `format_number()`, `format_mA()`, `format_c_rate()`를 추가한다.
3. [x] `canonical_c_rate()`, `current_from_c_rate()`를 추가한다.
4. [x] `scale_current_fields()`가 `old_current * factor` 대신 canonical C-rate 기반으로 새 전류를 계산하도록 구현한다.
5. [x] summary에 `old_c_raw`, `old_c`, `new_c`를 구분해 남긴다.
6. [x] CLI 출력 함수가 공통 포맷터를 사용하도록 바꾼다.
7. [x] CLI에 `--current-digits`, `--c-rate-digits`를 추가한다.
8. [x] GUI 로그가 같은 포맷터를 import해 사용하도록 바꾼다.
9. [x] GUI 로그에 기본 정규화 정책을 표시한다.
10. [x] `python3 -m py_compile`로 구문 검사를 수행한다.
11. [x] 최소 fixture 기반 테스트를 추가한다.

## 최종 권장안

1차 업그레이드는 “C-rate 2자리 정규화 + 전류 3자리 저장/표시 통일”을 기본 정책으로 삼는 것이 좋다. 이렇게 하면 내부 전류값이 새 cell 용량의 0.1배, 0.33배, 0.5배 같은 실험 조건과 직접 대응하고, 사용자가 GUI/CLI에서 본 값과 `.sch`에 쓰는 논리적 값이 일치한다.

단, 세밀한 C-rate 파일을 위해 CLI에는 자릿수 조정 옵션을 둔다. GUI는 1차에서는 기본 정책만 적용하고, 필요성이 확인되면 자릿수 입력 UI를 추가한다.
