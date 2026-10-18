"use client";

import { useRef, useState } from "react";
import type { Json, Views } from "@/lib/api";
import { Field } from "./Field";

export function KeyConditions({ views, apply, select, busy, inputError }: {
  views: Views; apply: (action: string, args?: Json) => Promise<void>;
  select: (id: string) => Promise<void>; busy?: boolean; inputError?: string;
}) {
  const root = useRef<HTMLElement>(null);
  const [child, setChild] = useState("");
  const [lastField, setLastField] = useState("");
  const setup = views.setupFields.filter((field) => ["nominal_capacity_mAh", "v_max", "v_min"].includes(field.key));
  const chosen = views.groupChildren?.find((entry) => String(entry.index) === child);
  const form = chosen?.form ?? views.form;
  const fields = form.sections.flatMap((section) => section.fields);
  const core = fields.filter((field) => field.keyCondition);
  const other = fields.filter((field) => !field.keyCondition);
  function focus(key: string) {
    const field = Array.from(root.current?.querySelectorAll<HTMLElement>("[data-field-key]") ?? []).find((item) => item.dataset.fieldKey === key);
    let parent = field?.parentElement;
    while (parent && parent !== root.current) { if (parent instanceof HTMLDetailsElement) parent.open = true; parent = parent.parentElement; }
    field?.scrollIntoView({ block: "center", behavior: "smooth" });
    field?.querySelector<HTMLElement>("input, select")?.focus({ preventScroll: true });
  }
  const render = (field: typeof fields[number]) => <Field
    key={`${views.form.moduleId}-${chosen?.index ?? "module"}-${field.key}`}
    field={field} compact disabled={busy}
    onCommit={(key, text) => { setLastField(key); void apply(chosen ? "setGroupChildParam" : "setParam", {
      moduleId: views.form.moduleId, ...(chosen ? { index: chosen.index } : {}), key, text,
    }); }} />;
  return <section className="card key-conditions" aria-label="실험 핵심 조건" ref={root}>
    <h2>실험 핵심 조건</h2>
    <p className="muted">박스를 펼치지 않고 선택한 구간의 조건을 수정합니다. 기준용량은 프로젝트 전체에, 구간 조건은 선택한 대상에만 적용됩니다.</p>
    <div className="key-condition-controls">
      {setup.map((field) => {
        const value = field.numericValue == null ? field.value.replace(/\s*V$/, "") : String(field.numericValue);
        return <div data-field-key={field.key} key={field.key}><label htmlFor={`core-${field.key}`}>{field.key === "nominal_capacity_mAh" ? "기준용량 (mAh)" : `${field.label} (V)`}</label><input id={`core-${field.key}`} key={value} defaultValue={value} disabled={busy} aria-invalid={Boolean(field.issue) || undefined} onBlur={(e) => { if (e.target.value !== value) { setLastField(field.key); void apply("setCellValue", { key: field.key, text: e.target.value }); } }} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); } }} />{field.issue && <button type="button" className="issue-link" disabled={busy} onClick={() => focus(field.key)}>{field.issue} · 수정</button>}</div>;
      })}
      <label>편집할 구간<select aria-label="핵심 조건 구간" disabled={busy || !views.modules.length} value={views.selectedModule} onChange={(e) => { setChild(""); void select(e.target.value); }}>
        {!views.modules.length && <option value="">먼저 구간을 추가하세요</option>}
        {views.modules.map((module) => <option key={module.moduleId} value={module.moduleId}>{module.position}. {module.title}</option>)}
      </select></label>
      {views.groupChildren?.length > 0 && <label>그룹 안의 대상<select aria-label="핵심 조건 그룹 대상" value={chosen ? child : ""} disabled={busy} onChange={(e) => { setChild(e.target.value); setLastField(""); }}>
        <option value="">그룹 전체 설정</option>{views.groupChildren.map((entry) => <option key={entry.index} value={entry.index}>{entry.index + 1}. {entry.form.title}</option>)}
      </select></label>}
    </div>
    {inputError && lastField && <div role="alert" className="input-issues"><span>{inputError}</span> <button type="button" className="issue-link" onClick={() => focus(lastField)}>입력한 값 바로 수정</button></div>}
    {fields.some((field) => field.hasError) && <div className="input-issues" aria-label="수정할 조건">
      {fields.filter((field) => field.hasError).map((field) => <button type="button" className="issue-link" key={field.key} onClick={() => focus(field.key)}>{field.label}: {field.issues.join(" · ")} → 수정</button>)}
    </div>}
    <div className="key-condition-fields">{core.map(render)}</div>
    {!core.length && <p className="muted">이 구간은 아래 상세 조건 또는 개별 스텝 편집을 사용하세요.</p>}
    {other.length > 0 && <details className="key-condition-details"><summary>나머지 조건 {other.length}개</summary><div className="key-condition-fields">{other.map(render)}</div></details>}
    {form.derived.length > 0 && <div className="key-condition-readings">{form.derived.map((item) => <p key={item.label} className={item.severity === "error" ? "danger" : "muted"}>{item.label}: {item.text}</p>)}</div>}
    <p className="muted">{views.summary.durationText} · 안전 시간제한은 예상 소요시간이 아닙니다.</p>
  </section>;
}
