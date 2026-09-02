# sch_current_rescaler 1/3C fraction alias 고도화 계획

작성일: 2026-05-28

상태: 구현 완료

## 목표

`sch_current_rescaler`가 `33.333 mA / 100 mAh`처럼 사실상 `1/3C`를 의도한 전류를 `0.33C`로 잘라서 처리하지 않도록 개선한다.

현재 기본 정책은 `C_RATE_DIGITS = 2`라서 raw C-rate를 소수점 둘째 자리로 정규화한다.

```text
33.333 mA / 100 mAh = 0.33333C
round(..., 2)       = 0.33C
```

이 방식은 `0.33C`가 실제로는 `1/3C`였던 schedule에서 새 용량 변환 시 전류가 작아지는 문제가 있다.

예:

```text
old capacity: 100 mAh
old current:  33.333 mA
new capacity: 120 mAh

현재 방식:
0.33C * 120 mAh = 39.6 mA

원하는 방식:
1/3C * 120 mAh = 40.0 mA
```

## 핵심 정책

`1/3C`만 특별한 fraction alias로 허용한다.

전역적으로 모든 C-rate를 분수로 변환하지 않는다. `Fraction.limit_denominator()` 같은 일반 분수화는 `0.2C -> 1/5C`, `0.25C -> 1/4C`, `0.166C -> 1/6C`처럼 의도하지 않은 표현을 만들 수 있다. 따라서 이번 변경은 `1/3C`에만 적용한다.

## tolerance 정의

`1/3C` 판정 tolerance는 `0.0005C`로 한다.

`1/3C = 0.333333333...C`이므로 판정 범위는 다음과 같다.

```text
0.332833333C <= raw C-rate <= 0.333833333C
```

즉 `abs(raw_c_rate - (1 / 3)) <= 0.0005`이면 `1/3C`로 본다.

용량 `100 mAh` 기준 전류 범위는 다음과 같다.

```text
33.283333 mA <= current <= 33.383333 mA
```

예상 판정:

```text
33.0 mA   / 100 mAh = 0.33C       -> 0.33C
33.28 mA  / 100 mAh = 0.3328C     -> 0.33C
33.30 mA  / 100 mAh = 0.333C      -> 1/3C
33.333 mA / 100 mAh = 0.33333C    -> 1/3C
33.38 mA  / 100 mAh = 0.3338C     -> 1/3C
33.40 mA  / 100 mAh = 0.334C      -> 0.33C 또는 0.33/0.334 정책 대상
```

주의: `33.40 mA`는 `1/3C` tolerance 밖이다. 현재 기본 `C_RATE_DIGITS = 2` 정책을 유지하면 decimal canonical 값은 `0.33C`가 된다.

## 변경 대상

- `battery_scheduler/sch_current_rescaler.py`
- `battery_scheduler/sch_current_rescaler_gui.py`
- `battery_scheduler/tests/test_sch_current_rescaler.py`

## 설계 방향

### 1. C-rate를 숫자와 표시 label로 분리한다

현재 summary에는 `old_c`, `new_c`가 float로 들어간다.

```python
{
    "old_c": 0.33,
    "new_c": 0.33,
}
```

`1/3C`를 표현하려면 계산값과 표시값을 분리해야 한다.

권장 구조:

```python
{
    "old_c_raw": 0.333329963684082,
    "old_c": 0.3333333333333333,
    "old_c_label": "1/3",
    "new_c": 0.3333333333333333,
    "new_c_label": "1/3",
}
```

decimal C-rate는 기존처럼 label을 생략하거나 `None`으로 둔다.

```python
{
    "old_c_raw": 0.49999996,
    "old_c": 0.5,
    "old_c_label": None,
    "new_c": 0.5,
    "new_c_label": None,
}
```

출력 함수는 label이 있으면 `1/3C`처럼 표시하고, 없으면 기존 `format_c_rate()`를 사용한다.

### 2. `canonical_c_rate()` 반환값 확장 여부

기존 `canonical_c_rate()`는 float만 반환한다.

```python
def canonical_c_rate(current_mA, capacity_mAh, digits=C_RATE_DIGITS):
    return round(float(current_mA) / float(capacity_mAh), int(digits))
```

이 함수의 반환 타입을 dict나 tuple로 바꾸면 기존 테스트와 호출부 영향이 커진다. 따라서 기존 함수는 float 반환을 유지하고, fraction alias를 포함한 새 helper를 추가한다.

권장 새 helper:

```python
ONE_THIRD_C_RATE = 1.0 / 3.0
FRACTION_C_RATE_TOLERANCE = 0.0005


def canonical_c_rate_info(
    current_mA,
    capacity_mAh,
    digits=C_RATE_DIGITS,
    fraction_tolerance=FRACTION_C_RATE_TOLERANCE,
):
    raw = float(current_mA) / float(capacity_mAh)
    if abs(raw - ONE_THIRD_C_RATE) <= float(fraction_tolerance):
        return {
            "raw": raw,
            "value": ONE_THIRD_C_RATE,
            "label": "1/3",
        }
    return {
        "raw": raw,
        "value": round(raw, int(digits)),
        "label": None,
    }
```

이렇게 하면 기존 `canonical_c_rate()` API는 보존하면서, `scale_current_fields()`와 `collect_current_fields()`만 새 helper를 사용하도록 바꿀 수 있다.

### 3. 전류 계산은 label이 아니라 canonical value를 사용한다

`1/3C`로 판정되면 새 전류는 `1.0 / 3.0 * new_capacity_mAh`로 계산한다.

```python
c_info = canonical_c_rate_info(old_current, old_capacity_mAh, c_rate_digits)
new_current = current_from_c_rate(c_info["value"], new_capacity_mAh, current_digits)
```

예:

```text
1/3C * 120 mAh = 40.0 mA
```

`.sch`에는 기존 정책대로 `CURRENT_DIGITS = 3` 기준으로 round한 float32를 쓴다.

### 4. 표시 formatter를 추가한다

현재 `format_c_rate(value)`는 숫자만 받는다. fraction label까지 처리하려면 별도 helper를 둔다.

권장:

```python
def format_c_rate_label(value, label=None, digits=C_RATE_DIGITS):
    if label:
        return "%sC" % label
    formatted = format_c_rate(value, digits)
    if formatted == "-":
        return formatted
    return "%sC" % formatted
```

다만 현재 표 header가 `C-rate`이고 값에는 `0.33`처럼 `C` suffix가 없다. 기존 출력 스타일을 덜 흔들려면 다음 방식도 가능하다.

```python
def format_c_rate_display(value, label=None, digits=C_RATE_DIGITS):
    if label:
        return label
    return format_c_rate(value, digits)
```

이번 변경에서는 사용자가 “표현도 `1/3C`로 나오게”를 요청했으므로, C-rate 출력값에는 suffix `C`를 붙이는 방향을 권장한다.

예:

```text
기존: 0.33 -> 0.33
변경: 0.5  -> 0.5C
변경: 1/3 -> 1/3C
```

이 경우 CLI와 GUI 표 header도 `C-rate` 그대로 유지해도 무방하다.

### 5. CLI 옵션

기본값은 자동 `1/3C` 인식 활성화로 한다.

새 옵션 후보:

```text
--fraction-tolerance 0.0005
```

기능:

- `1/3C` alias 판정 tolerance를 C-rate 단위로 지정한다.
- `0`을 주면 사실상 자동 fraction alias를 끌 수 있다.

예:

```bash
python sch_current_rescaler.py input.sch output.sch 100 120 \
  --fraction-tolerance 0.0005
```

`--no-fraction-c-rate` 같은 boolean 옵션도 가능하지만, 우선순위는 낮다. tolerance `0`으로 비활성화하는 편이 구현 변경이 작다.

### 6. GUI 정책

GUI는 1차 구현에서 옵션 입력을 노출하지 않는다.

대신 시작 로그에 정책을 명확히 표시한다.

```text
정규화 정책: 1/3C 자동 인식 tolerance 0.0005C, 그 외 C-rate 소수점 2자리, 전류 소수점 3자리 mA
```

추후 사용자가 tolerance 조정을 요구하면 GUI에 고급 옵션으로 추가한다.

## 함수별 변경 계획

### `sch_current_rescaler.py`

#### 상수 추가

```python
ONE_THIRD_C_RATE = 1.0 / 3.0
FRACTION_C_RATE_TOLERANCE = 0.0005
```

#### helper 추가

```python
def canonical_c_rate_info(...):
    ...

def format_c_rate_display(value, label=None, digits=C_RATE_DIGITS):
    ...
```

#### `collect_current_fields()`

현재:

```python
"c_rate": current / capacity_mAh if capacity_mAh else None,
"canonical_c_rate": canonical_c_rate(current, capacity_mAh, c_rate_digits) if capacity_mAh else None,
```

변경:

```python
c_info = canonical_c_rate_info(current, capacity_mAh, c_rate_digits, fraction_tolerance)
"c_rate": c_info["raw"],
"canonical_c_rate": c_info["value"],
"c_rate_label": c_info["label"],
```

capacity가 없으면 기존처럼 `None`을 유지한다.

#### `scale_current_fields()`

현재:

```python
old_c_raw = old_current / old_capacity_mAh
old_c = canonical_c_rate(old_current, old_capacity_mAh, c_rate_digits)
new_current = current_from_c_rate(old_c, new_capacity_mAh, current_digits)
...
"old_c": old_c,
"new_c": canonical_c_rate(new_current, new_capacity_mAh, c_rate_digits),
```

변경:

```python
old_c_info = canonical_c_rate_info(
    old_current,
    old_capacity_mAh,
    c_rate_digits,
    fraction_tolerance,
)
new_current = current_from_c_rate(old_c_info["value"], new_capacity_mAh, current_digits)
new_c_info = canonical_c_rate_info(
    new_current,
    new_capacity_mAh,
    c_rate_digits,
    fraction_tolerance,
)
...
"old_c_raw": old_c_info["raw"],
"old_c": old_c_info["value"],
"old_c_label": old_c_info["label"],
"new_c": new_c_info["value"],
"new_c_label": old_c_info["label"] or new_c_info["label"],
```

`new_c_label`은 계산에 사용한 alias를 보존하기 위해 `old_c_info["label"]`을 우선한다. `new_current`가 `CURRENT_DIGITS`로 round되면서 raw reverse 계산이 tolerance 밖으로 밀릴 가능성을 막기 위함이다.

#### 출력 함수

`print_current_fields()`와 `print_summary()`는 `format_c_rate_display()`를 사용한다.

```python
format_c_rate_display(
    item.get("canonical_c_rate", item.get("c_rate")),
    item.get("c_rate_label"),
    c_rate_digits,
)
```

```python
format_c_rate_display(ch["old_c"], ch.get("old_c_label"), c_rate_digits)
format_c_rate_display(ch["new_c"], ch.get("new_c_label"), c_rate_digits)
```

#### CLI parser

옵션 추가:

```python
parser.add_argument(
    "--fraction-tolerance",
    type=float,
    default=FRACTION_C_RATE_TOLERANCE,
    help="C-rate tolerance for recognizing 1/3C fraction alias",
)
```

`collect_current_fields()`와 `scale_current_fields()` 호출에 전달한다.

### `sch_current_rescaler_gui.py`

#### import 추가

```python
FRACTION_C_RATE_TOLERANCE
format_c_rate_display
```

#### 시작 로그 변경

```text
정규화 정책: 1/3C 자동 인식 tolerance 0.0005C, 그 외 C-rate 소수점 2자리, 전류 소수점 3자리 mA
```

#### 원본 전류 목록

기존 `format_c_rate()` 대신 `format_c_rate_display()`를 사용한다.

#### 변환 로그

기존 `format_c_rate()` 대신 `format_c_rate_display()`를 사용한다.

GUI는 `fraction_tolerance`를 함수 호출에 명시적으로 넘기지 않아도 기본값을 사용하게 한다.

## 테스트 계획

### 1. `1/3C` 판정 테스트

```python
def test_canonical_c_rate_info_recognizes_one_third():
    info = canonical_c_rate_info(33.333, 100)
    assert info["label"] == "1/3"
    assert info["value"] == 1.0 / 3.0
```

### 2. tolerance 경계 테스트

```python
def test_one_third_tolerance_bounds():
    assert canonical_c_rate_info(33.30, 100)["label"] == "1/3"
    assert canonical_c_rate_info(33.38, 100)["label"] == "1/3"
    assert canonical_c_rate_info(33.28, 100)["label"] is None
    assert canonical_c_rate_info(33.40, 100)["label"] is None
```

### 3. 변환 전류 테스트

```python
def test_scale_current_fields_preserves_one_third_c_rate():
    src = make_single_cccv_sch(33.333, 5.0)
    out, summary = scale_current_fields(src, 100, 120)
    change = summary["changes"][0]
    assert change["old_c_label"] == "1/3"
    assert change["new"] == 40.0
    assert change["new_c_label"] == "1/3"
```

### 4. `0.33C`와 `1/3C` 구분 테스트

```python
def test_scale_current_fields_keeps_exact_point_33_decimal():
    src = make_single_cccv_sch(33.0, 100)
    out, summary = scale_current_fields(src, 100, 120)
    change = summary["changes"][0]
    assert change["old_c_label"] is None
    assert change["old_c"] == 0.33
    assert change["new"] == 39.6
```

### 5. 출력 formatter 테스트

```python
def test_format_c_rate_display_uses_fraction_label():
    assert format_c_rate_display(1.0 / 3.0, "1/3") == "1/3C"
    assert format_c_rate_display(0.5, None) == "0.5C"
```

## 검증 명령

```bash
python3 -m py_compile battery_scheduler/sch_current_rescaler.py battery_scheduler/sch_current_rescaler_gui.py
cd battery_scheduler && python3 -m unittest discover -s tests
```

필요하면 실제 sample `.sch`에 대해 dry-run도 수행한다.

```bash
cd battery_scheduler
python3 sch_current_rescaler.py dist/windows/form_RPT_100mAh.sch /tmp/form_RPT_120mAh.sch 100 120 --dry-run --show-current
```

## 트레이드오프

### 장점

- `1/3C` 의도 schedule을 `0.33C`로 낮춰 변환하는 문제를 줄인다.
- `1/3C`로 계산하고 `1/3C`로 표시하므로 저장값과 로그의 의미가 맞는다.
- 일반 분수화를 피하므로 예상 밖의 `1/5C`, `1/4C` 표시가 생기지 않는다.

### 단점

- tolerance 범위 안에 있는 `0.333C` 의도 값도 `1/3C`로 해석된다.
- `C_RATE_DIGITS = 2` 정책과 fraction alias 정책이 함께 존재하므로 summary 구조가 약간 복잡해진다.
- GUI에서는 tolerance를 조정할 수 없으므로 특수 파일은 CLI를 써야 한다.

### 대응

- tolerance를 `0.0005C`로 명시하고 CLI 옵션으로 조정 가능하게 한다.
- summary에 `old_c_raw`를 계속 남겨 판정 근거를 확인할 수 있게 한다.
- `1/3C` 외 분수는 이번 범위에서 제외한다.

## 구현 순서

1. `sch_current_rescaler.py`에 `ONE_THIRD_C_RATE`, `FRACTION_C_RATE_TOLERANCE` 상수를 추가한다.
2. `canonical_c_rate_info()`와 `format_c_rate_display()`를 추가한다.
3. `collect_current_fields()`에 fraction label 정보를 추가한다.
4. `scale_current_fields()`가 `canonical_c_rate_info()`를 사용하도록 바꾼다.
5. `print_current_fields()`와 `print_summary()`가 fraction label을 표시하도록 바꾼다.
6. CLI에 `--fraction-tolerance` 옵션을 추가한다.
7. GUI 로그에서 `format_c_rate_display()`를 사용하도록 바꾼다.
8. GUI 시작 로그에 `1/3C` 자동 인식 정책을 표시한다.
9. 단위 테스트를 추가한다.
10. `py_compile`과 `unittest`로 검증한다.

## 완료 기준

- `33.333 mA / 100 mAh`는 `1/3C`로 표시된다.
- 같은 값을 `100 mAh -> 120 mAh`로 변환하면 새 전류는 `40 mA`가 된다.
- `33.0 mA / 100 mAh`는 기존처럼 `0.33C`로 처리되고 `120 mAh`에서 `39.6 mA`가 된다.
- CLI와 GUI 로그 모두 fraction alias를 같은 방식으로 표시한다.
- 기존 테스트와 신규 테스트가 모두 통과한다.

---

# GUI 다중 용량 일괄 변환 계획 및 구현 정리

작성일: 2026-05-28

상태: 구현 완료

## 목표

기존 GUI는 다음 입력 흐름만 지원했다.

```text
원본 .sch 파일
출력 .sch 파일 전체 경로
기존 셀 용량
새 셀 용량 1개
```

이 방식은 동일 schedule을 여러 cell capacity로 반복 변환할 때 같은 작업을 여러 번 해야 한다.

개선 목표는 사용자가 변환할 용량을 comma-separated list로 입력하면 각 용량별 `.sch` 파일을 자동 생성하는 것이다.

예:

```text
원본 파일: example.sch
기존 용량: 50 mAh
출력 폴더: C:\out
출력 파일명 stem: 260528
변환할 용량 목록: 100, 200, 300
```

생성 파일:

```text
C:\out\260528_100mAh.sch
C:\out\260528_200mAh.sch
C:\out\260528_300mAh.sch
```

## 설계 원칙

1. CLI의 기존 단일 변환 인터페이스는 유지한다.
2. GUI만 batch workflow로 바꾼다.
3. comma-separated 용량 파싱과 출력 파일명 생성은 테스트 가능한 helper로 분리한다.
4. 입력 개수 제한은 두지 않는다.
5. 잘못된 입력은 변환 전에 에러로 막는다.
6. 생성 파일명은 `{stem}_{capacity}mAh.sch` 형식을 사용한다.

## 입력 정책

### 출력 경로

기존:

```text
출력 .sch 파일: 전체 파일 경로
```

변경:

```text
출력 폴더
출력 파일명 stem
```

출력 폴더는 `filedialog.askdirectory()`로 선택한다.

원본 파일을 선택하면 기본값은 다음처럼 자동 입력된다.

```text
출력 폴더: 원본 파일이 있는 폴더
출력 파일명 stem: {원본 파일명}_rescaled
```

### 변환할 용량 목록

사용자는 다음처럼 comma-separated format으로 입력한다.

```text
100, 200, 300
100,200,300.5
```

각 항목은 `float`로 파싱한다.

허용:

```text
100
200.5
 300 
```

거부:

```text
빈 문자열
100,,200
100, abc
100, 0
100, -20
```

## 파일명 정책

출력 파일명은 다음 helper가 만든다.

```python
def build_batch_output_path(output_dir, stem, capacity_mAh):
    filename = "%s_%smAh.sch" % (stem, format_capacity_for_filename(capacity_mAh))
    return os.path.join(output_dir, filename)
```

용량 suffix는 compact decimal format을 쓴다.

```text
100.0   -> 100
300.5   -> 300.5
12.3456 -> 12.346
```

현재는 `CURRENT_DIGITS = 3`을 재사용해 파일명 용량도 최대 소수점 셋째 자리까지 표시한다.

## 에러 처리

변환 전 `validate_inputs()`에서 다음을 검사한다.

- 원본 파일 경로가 비어 있지 않은지
- 원본 파일이 존재하는지
- 출력 폴더가 비어 있지 않은지
- 출력 경로가 이미 존재하는 경우 폴더인지
- 출력 파일명 stem이 비어 있지 않은지
- stem에 `/` 또는 `\` 경로 구분자가 들어가지 않았는지
- 기존 셀 용량이 `0`보다 큰지
- 변환할 용량 목록이 비어 있지 않은지
- 각 변환 용량이 숫자인지
- 각 변환 용량이 `0`보다 큰지
- 생성될 출력 파일명이 서로 중복되지 않는지

중복 파일명 검사는 다음 케이스를 막기 위한 것이다.

```text
100, 100.0
```

둘 다 `stem_100mAh.sch`가 되므로 에러로 처리한다.

주의: 현재 구현은 이미 존재하는 출력 파일을 덮어쓸 수 있다. 기존 GUI도 단일 출력 파일을 바로 썼으므로 이번 변경에서는 overwrite confirmation을 추가하지 않았다. 필요하면 후속 단계에서 추가한다.

## 구현 내용

### `battery_scheduler/sch_current_rescaler.py`

추가된 helper:

```python
def parse_capacity_list(text):
    """Parse comma-separated positive mAh capacity values."""
    ...
```

역할:

- comma-separated text를 `list[float]`로 변환한다.
- 빈 값, 숫자가 아닌 값, `0` 이하 값을 `ValueError`로 거부한다.

추가된 helper:

```python
def format_capacity_for_filename(value):
    return format_number(value, CURRENT_DIGITS)
```

역할:

- 파일명 suffix에 들어갈 capacity를 compact string으로 만든다.
- 기존 `format_number()` 정책을 재사용한다.

추가된 helper:

```python
def build_batch_output_path(output_dir, stem, capacity_mAh):
    filename = "%s_%smAh.sch" % (stem, format_capacity_for_filename(capacity_mAh))
    return os.path.join(output_dir, filename)
```

역할:

- batch output file path를 한 곳에서 만든다.
- GUI와 테스트가 같은 파일명 정책을 공유하게 한다.

### `battery_scheduler/sch_current_rescaler_gui.py`

변경된 state:

```python
self.output_path
self.new_capacity
```

위 단일 출력/단일 용량 state를 제거하고 다음으로 교체했다.

```python
self.output_dir
self.output_stem
self.new_capacities
```

변경된 UI:

```text
출력 .sch 파일        -> 출력 폴더
저장 위치             -> 폴더 선택
새 셀 용량 (mAh)      -> 변환할 용량 목록 (mAh)
변환 실행             -> 일괄 변환 실행
```

추가된 UI:

```text
출력 파일명 stem
쉼표로 구분 안내 label
```

변경된 파일 선택 동작:

```python
if not self.output_dir.get():
    self.output_dir.set(os.path.dirname(path))
if not self.output_stem.get():
    base = os.path.splitext(os.path.basename(path))[0]
    self.output_stem.set(base + "_rescaled")
```

변경된 변환 동작:

```python
os.makedirs(output_dir, exist_ok=True)
written_paths = []
for new_cap, output_path in zip(new_caps, output_paths):
    out, summary = scale_current_fields(src, old_cap, new_cap)
    with open(output_path, "wb") as f:
        f.write(out)
    written_paths.append(output_path)
```

각 용량마다 기존 `scale_current_fields()`를 그대로 호출한다. 따라서 C-rate 정규화, 전류 field 변경 범위, summary 생성 정책은 기존 단일 변환과 동일하다.

변환 로그는 각 output file마다 다음 정보를 출력한다.

```text
출력 경로
용량 변환
Header size
Step count
Scale factor
Canonicalization
Changed fields
변경 field preview
```

마지막에는 생성 파일 수를 표시한다.

```text
완료: 3개 파일 생성
```

### `battery_scheduler/tests/test_sch_current_rescaler.py`

추가 테스트:

```python
def test_parse_capacity_list_accepts_comma_separated_values(self):
    self.assertEqual(parse_capacity_list("100, 200,300.5"), [100.0, 200.0, 300.5])
```

추가 테스트:

```python
def test_parse_capacity_list_rejects_bad_values(self):
    for text in ("", "100,,200", "100, abc", "100, 0"):
        ...
```

추가 테스트:

```python
def test_build_batch_output_path_uses_compact_capacity_suffix(self):
    self.assertEqual(format_capacity_for_filename(100.0), "100")
    self.assertEqual(format_capacity_for_filename(300.5), "300.5")
    self.assertEqual(
        build_batch_output_path("/tmp/out", "260528", 100.0),
        os.path.join("/tmp/out", "260528_100mAh.sch"),
    )
```

## 검증 결과

구문 검사:

```bash
python3 -m py_compile battery_scheduler/sch_current_rescaler.py battery_scheduler/sch_current_rescaler_gui.py
```

결과: 통과

단위 테스트:

```bash
cd battery_scheduler && python3 -m unittest discover -s tests
```

결과:

```text
Ran 9 tests in 0.001s

OK
```

## 후속 후보

이번 구현에서는 요청 범위를 넘지 않기 위해 다음 기능은 넣지 않았다.

- 이미 존재하는 출력 파일 overwrite confirmation
- batch 변환 dry-run
- 변환할 용량 목록을 줄바꿈 또는 공백으로도 입력하는 parser
- GUI에서 생성 예정 파일 목록 preview
- CLI batch mode
- `1/3C` fraction alias 구현은 이후 아래 진행 기록에서 완료함

---

# 1/3C fraction alias 구현 진행 기록

작성일: 2026-05-28

## 진행 상태

1. [x] 계획 파일 기준으로 구현 단계와 현재 코드 차이를 확인했다.
2. [x] `ONE_THIRD_C_RATE`, `FRACTION_C_RATE_TOLERANCE`, `canonical_c_rate_info()`, `format_c_rate_display()`를 추가했다.
3. [x] `collect_current_fields()`, `scale_current_fields()`, CLI 옵션, CLI 출력, GUI 로그/출력에 `1/3C` alias 정책을 연결했다.
4. [x] `20 mA / 60 mAh`, tolerance 경계, alias 비활성화, `0.33C` 유지, 출력 formatter 테스트를 추가했다.
5. [x] `py_compile`과 `unittest` 검증을 완료했다.

## 구현 내용

### `battery_scheduler/sch_current_rescaler.py`

추가한 상수:

```python
ONE_THIRD_C_RATE = 1.0 / 3.0
FRACTION_C_RATE_TOLERANCE = 0.0005
```

추가한 helper:

```python
def canonical_c_rate_info(
    current_mA,
    capacity_mAh,
    digits=C_RATE_DIGITS,
    fraction_tolerance=FRACTION_C_RATE_TOLERANCE,
):
    ...
```

역할:

- raw C-rate를 계산한다.
- raw C-rate가 `1/3C`에서 `±0.0005C` 안에 있으면 canonical value를 `1.0 / 3.0`, label을 `"1/3"`으로 반환한다.
- tolerance 밖이면 기존처럼 `round(raw, c_rate_digits)`를 사용하고 label은 `None`으로 둔다.
- `fraction_tolerance=0`이면 자동 alias를 끌 수 있다.

추가한 formatter:

```python
def format_c_rate_display(value, label=None, digits=C_RATE_DIGITS):
    ...
```

역할:

- label이 있으면 `1/3C`처럼 표시한다.
- label이 없으면 `0.5C`, `0.33C`처럼 기존 decimal format에 `C` suffix를 붙인다.
- 값이 없으면 `-`를 반환한다.

변경한 함수:

- `collect_current_fields()`
  - `fraction_tolerance` 인자를 추가했다.
  - 각 field summary에 `c_rate_label`을 추가했다.
  - `20 mA / 60 mAh` 같은 값은 `canonical_c_rate = 1.0 / 3.0`, `c_rate_label = "1/3"`으로 보고한다.

- `scale_current_fields()`
  - `fraction_tolerance` 인자를 추가했다.
  - 새 전류 계산에 `canonical_c_rate_info()["value"]`를 사용한다.
  - summary에 `old_c_label`, `new_c_label`, `fraction_tolerance`를 추가했다.
  - `old_c_info["label"]`을 `new_c_label`에 우선 반영해, 전류 round 후 reverse 계산이 흔들려도 원래 alias 표시가 유지되게 했다.

- `print_current_fields()`, `print_summary()`
  - `format_c_rate_display()`를 사용한다.
  - `Fraction alias: 1/3C tolerance 0.0005C` 정보를 출력한다.

- CLI parser
  - `--fraction-tolerance` 옵션을 추가했다.
  - 기본값은 `0.0005`이다.

### `battery_scheduler/sch_current_rescaler_gui.py`

변경한 import:

```python
FRACTION_C_RATE_TOLERANCE
format_c_rate_display
```

변경한 시작 로그:

```text
정규화 정책: 1/3C 자동 인식 tolerance 0.0005C, 그 외 C-rate 소수점 2자리, 전류 소수점 3자리 mA
```

변경한 원본 전류 표시:

- 기존 `format_c_rate()` 대신 `format_c_rate_display()`를 사용한다.
- `20 mA / 60 mAh`는 `1/3C`로 표시된다.

변경한 변환 로그:

- 기존 `format_c_rate()` 대신 `format_c_rate_display()`를 사용한다.
- 변환 summary에 `1/3C tolerance`를 같이 표시한다.
- `20 mA / 60 mAh -> 120 mAh` 변환 시 C-rate는 `1/3C -> 1/3C`, 새 전류는 `40 mA`로 표시된다.

### `battery_scheduler/tests/test_sch_current_rescaler.py`

추가한 테스트:

- `test_format_c_rate_display_uses_fraction_label`
- `test_collect_current_fields_reports_one_third_label`
- `test_canonical_c_rate_info_recognizes_one_third`
- `test_one_third_tolerance_bounds`
- `test_fraction_tolerance_can_disable_one_third_alias`
- `test_scale_current_fields_preserves_one_third_c_rate`
- `test_scale_current_fields_keeps_exact_point_33_decimal`

핵심 검증:

```text
20 mA / 60 mAh -> 1/3C
60 mAh -> 120 mAh 변환 결과 -> 40 mA
33.0 mA / 100 mAh -> 0.33C
100 mAh -> 120 mAh 변환 결과 -> 39.6 mA
```

## 검증 결과

구문 검사:

```bash
python3 -m py_compile battery_scheduler/sch_current_rescaler.py battery_scheduler/sch_current_rescaler_gui.py
```

결과: 통과

단위 테스트:

```bash
cd battery_scheduler && python3 -m unittest discover -s tests
```

결과:

```text
Ran 16 tests in 0.001s

OK
```
