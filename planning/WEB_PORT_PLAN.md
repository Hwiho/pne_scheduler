# 웹 포팅 계획 — API 경계 설계

개정: 2026-09-09
근거: 현재 `ui/workspace_model.py`(50개 공개 메서드), `ui/workspace_qt.py`(58개 슬롯),
`ir/project.py`, `release.py`, `import_session.py`, `library.py` 실측.
관련: [`GATE_E_PLAN.md`](GATE_E_PLAN.md), [`GUARDRAILS.md`](GUARDRAILS.md), [`ROADMAP.md`](ROADMAP.md)

---

## 1. 결론

**경계는 계층이 아니라 "장비로 갈 바이트를 만지는가"로 긋는다.**

두 가지를 먼저 확정해야 하고, 나머지는 그 두 결정에서 따라온다.

1. **서버는 랩 PC에서 돈다.** 중앙 서버가 아니다. 저작·검증은 어디서 돌아도 되지만,
   `.sch` 원본과 CTSEditorPro 는 랩 PC에만 있다.
2. **핵심 API 는 무상태다.** 프로젝트 전체를 요청마다 주고받고, 서버는 순수 함수처럼
   동작한다. Undo 는 클라이언트가 갖는다.

이 둘을 지키면 현재의 안전 모델(저장은 항상 허용, 내보내기만 게이트)이 웹에서도
그대로 성립한다. 어느 하나라도 어기면 게이트를 다시 설계해야 한다.

---

## 2. 이미 확보되어 있는 것

포팅이 수월한 이유는 우연이 아니라 지켜온 규칙 덕분이다.

| 자산 | 상태 | 웹에서의 의미 |
|------|------|---------------|
| `ui/workspace_model.py` | Qt·Tk 를 import 하지 않음 | 그대로 서비스 계층이 된다 |
| `ScheduleProject.to_dict/from_dict` | 완전한 왕복, `copy()` 가 이것으로 구현됨 | 프로젝트가 곧 JSON 문서다 |
| `ui/workspace_qt.py` 58개 슬롯 | 이미 모델 → dict/list 변환 | REST 핸들러의 초안이다 |
| `release.py` / `exporting.py` | 게이트가 화면이 아니라 모델에 있음 | 브라우저가 게이트를 우회할 수 없다 |
| `spec/` ParameterSpec | 단위·범위·근거가 데이터 | 폼을 프런트에서 렌더할 수 있다 |

코드량 기준으로도 갈라져 있다.

```
UI 계층 (버려짐)        5,691줄   Tk 워크스페이스 · Qt/QML · 도구 4개
UI 무관 로직 (재사용)    6,561줄   workspace_model · spec · protocol · ir
                                  release · library · import_session · edit
```

---

## 3. 결정 1 — 서버는 어디서 도는가

### 3.1 왜 중앙 서버가 아닌가

중앙 서버로 가면 다음이 전부 바뀐다.

- CTSPro 가 만든 원본 `.sch` 를 **업로드**해야 한다. 지금은 파일이 랩 PC 밖으로
  나가지 않는다.
- 내보낸 결과를 **다운로드**해야 한다. `import_session` 이 보장하는 "원본 바이트를
  그대로 두고 2바이트만 바꾼다"가 전송 경로 하나를 더 통과한다.
- `record_ctspro_review` 가 **누구의** 승인인지 물어야 한다. 지금은 그 PC를 쓰는
  사람이다.
- 장비 실행용 파일을 만들 수 있는 서버가 네트워크에 노출된다.

### 3.2 권장 형태

```
랩 PC
├── Next.js (localhost:3000)        화면
└── Python API (localhost:8000)     현재 코드 그대로
    └── 파일시스템: .sch 원본 · ~/.pne_scheduler/library · 내보내기 대상
```

브라우저는 UI 일 뿐이고 파일은 계속 랩 PC 안에 있다. 배포는 "이 두 프로세스를
띄우는 스크립트" 하나면 된다.

### 3.3 나중에 중앙으로 옮겨도 되는 것

**방법 라이브러리만** 중앙화 가치가 있다 — 팀이 프로토콜을 공유하는 것이 원래 목적이고,
`library.py` 는 장비 파일을 쓰지 않는다. 그때도 `plan_load` 의 장비 불일치 경고는
그대로 유효하다.

---

## 4. 결정 2 — 상태를 누가 갖는가

### 4.1 무상태를 택하는 이유

현재 `ProjectDocument` 는 undo 스택(`UndoEntry(label, before)` 스냅샷 목록)을
메모리에 들고 있다. 이걸 서버에 두면 세션 고정, 메모리 누수, 재시작 시 작업 손실이
따라온다.

그런데 **undo 항목이 이미 프로젝트 스냅샷**이다. 즉 undo 스택은 `.schproj` 문서의
배열일 뿐이고, 클라이언트가 갖는 편이 자연스럽다.

### 4.2 형태

```
클라이언트(브라우저)              서버(Python)
─────────────────────            ──────────────────────
현재 프로젝트 JSON        ──POST──▶  WorkspaceModel 을 요청마다 구성
undo/redo 스택            ◀─────────  { project, views, notes, warnings }
localStorage 자동저장
```

- 서버는 세션을 갖지 않는다. 재시작해도 작업이 남는다.
- undo/redo 는 클라이언트 배열 조작이다. 서버 왕복이 없다.
- 자동저장·크래시 복구는 `ui/document.py` 의 역할을 브라우저 저장소가 대신한다.

### 4.3 무상태로 못 만드는 것

두 가지는 본질적으로 상태를 갖는다. **작게 격리한다.**

| 대상 | 왜 | 처리 |
|------|-----|------|
| `ImportSession` | 원본 바이트와 해시를 들고 있어야 함 | 서버가 세션 id 로 보관, TTL 부여 |
| 내보내기 | 파일을 실제로 씀 | 요청 1건 = 파일 1건, 상태 없음 |

---

## 5. API 형태 — 연산을 네 종류로 나눈다

현재 모델의 50개 메서드는 정확히 네 부류로 갈린다. 이 분류가 그대로 엔드포인트 설계다.

### 5.1 파생 (project → view) · 부작용 없음

`summary` `release` `module_rows` `form` `procedure` `step_rows` `display_step_rows`
`validation_rows` `unverified_notes` `setup_fields` `goal_rows` `palette_types`
`unit_choices` `current_limit_breaches` `c_rate_presets` `custom_step_rows`
`step_field_views` `can_edit_steps` `modules_of_type`

```
POST /api/views   { project }  →  { summary, release, procedure, validation, form, ... }
```

한 번에 묶어 돌려준다. 화면 하나가 여러 뷰를 동시에 필요로 하고, 전부 같은
프로젝트에서 파생되므로 왕복을 나눌 이유가 없다.

### 5.2 변환 (project + 인자 → project) · 서버는 저장하지 않음

`set_project_name` `set_equipment_unit` `set_cell_value` `add_goal` `add_module`
`add_campaign` `remove_module` `duplicate_module` `set_param` `apply_to_all_of_type`
`move` `reorder` `detach` `insert_step` `remove_step` `move_step` `set_step_field`
`set_cycle_count` `apply_qc_fast_charge` `load_method` `record_ctspro_review`
`record_equipment_approval` `clear_approvals`

```
POST /api/edit/{action}   { project, args }  →  { project, label, diff, views }
```

`label` 은 클라이언트가 undo 항목 이름으로 쓴다(현재 `document.apply()` 의 문자열과
같은 것). `diff` 는 `StepDiff` 로, 무엇이 바뀌었는지 화면이 바로 보여줄 수 있다.

### 5.3 계획 (project + 인자 → plan) · 아무것도 바꾸지 않음

`plan_campaign` `plan_qc_fast_charge` `cycles_within` `preview_param`
`preview_step_field` `plan_method_load`

```
POST /api/plan/{action}   { project, args }  →  { plan, notes, warnings, errors }
```

**이 부류를 5.2 와 반드시 분리한다.** 지금 UI 가 "미리보기 → 적용" 2단계인 이유가
그대로 유효하고, 경고(예: DC-IR 저항 창이 장비 파일에 안 들어간다)는 적용 전에
보여야 한다.

### 5.4 로컬 자원 · 랩 PC 에서만 동작

`open_path` `new_document` `save_method` `saved_methods` `method_versions`
import 세션 · 내보내기 전체

```
GET  /api/library                      저장된 방법 목록
POST /api/library                      { project, name } → 새 버전
POST /api/import/open                  { path } → { sessionId, digest, editableFields }
POST /api/import/{sessionId}/stage     { stepNo, field, value }
POST /api/import/{sessionId}/patch     → 파일 작성
POST /api/export/{kind}                { project, outDir } → { path, manifest }
```

이 그룹만 파일시스템에 닿는다. 중앙 서버로 옮길 때 **경계선이 여기다.**

---

## 6. 그대로 옮겨지지 않는 것

정직하게 적어 둔다.

| 현재 | 웹에서 |
|------|--------|
| `ui/document.py` 자동저장·복구 | 브라우저 저장소로 이동. 서버는 관여하지 않는다 |
| Tk 워크스페이스 (`ui/workspace.py`, 1,700줄 상당) | **버린다.** 이식하지 않는다 |
| Qt/QML (`workspace_qt.py` + `qml/`) | 버리되 브리지의 dict 변환은 핸들러로 옮긴다 |
| 파일 대화상자 | 경로 입력 또는 서버측 파일 브라우저 |
| viewer / flow / resume / bulk editor (4개 Tk 도구) | 별도 판단. 웹 이전까지는 유지 |

---

## 7. 지금 코드에서 고쳐야 하는 것

포팅 전에 정리하면 이후가 훨씬 단순해진다. 전부 UI 무관 계층이라 **웹으로 가도 살아남는
작업**이다.

1. **`WorkspaceModel` 을 undo 없이 쓸 수 있게** — 현재 모든 변환이
   `document.apply()` 를 거쳐 undo 를 쌓는다. 무상태 요청에서는 불필요하다.
   변환 결과와 라벨만 돌려주는 경로가 필요하다.
2. **`SchPatchPlan.to_dict()` 추가** — 지금 직렬화가 없어 `ImportSession` 이 만든 계획을
   `patch-sch` 로 넘길 수 없다. 웹에서는 필수다.
3. **라이브러리 저장 경로 노출** — `save_method()` 가 모델에만 있고 어떤 UI·CLI 에도
   없다. E2.3 이 실질적으로 도달 불가 상태다.
4. **문서 정정** — README/docs 가 Tk 를 "같은 다섯 화면"이라고 하는데 사실이 아니다.
   Tk 는 축소 폴백이며 곧 제거 대상이라고 적는다.

---

## 8. 단계

| 단계 | 내용 | 장비 필요 |
|------|------|:---:|
| W0 | §7 의 4건 정리 (무상태 경로, 직렬화, 저장 노출, 문서) | 아니오 |
| W1 | Python API — §5.1/5.2/5.3 (파일 안 만짐). 기존 테스트가 그대로 계약 검증 | 아니오 |
| W2 | Next.js 화면 — 설정/프로토콜/절차/검증. 폼은 `spec/` 메타데이터로 렌더 | 아니오 |
| W3 | §5.4 로컬 자원 — 라이브러리, import 세션, 내보내기 | 아니오 |
| W4 | Tk 워크스페이스 제거, 런처를 웹으로 전환 | 아니오 |

W1 까지는 화면 없이 진행 가능하고, 현재 591개 테스트가 계약 회귀를 잡아 준다.

---

## 9. 하지 말아야 할 것

- **게이트를 프런트엔드로 옮기지 않는다.** `release.py` 가 판단하고 API 가 그것을
  전달만 한다. 브라우저가 `equipment_executable` 을 계산하는 순간 안전 모델이 끝난다.
- **Tk 에 기능을 이식하지 않는다.** 곧 버릴 계층이다.
- **중앙 서버에서 장비 실행용 파일을 만들지 않는다.** §3.1.
- **`workspace_model.py` 에 웹 의존성을 넣지 않는다.** Qt·Tk 를 넣지 않아서 이번
  포팅이 가능해진 것이고, 같은 규칙이 다음 이식에도 적용된다.
