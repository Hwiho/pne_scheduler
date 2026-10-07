"use client";

// One parameter, rendered from its spec rather than from hand-written markup.
//
// `spec/module_params.py` already declares each parameter's Korean label, unit,
// allowed and recommended range, the basis for its default and how far it has
// been verified. Rendering from that means a new parameter appears here with its
// documentation intact, and cannot arrive as an undocumented JSON key.

import { useEffect, useId, useRef, useState } from "react";
import type { FormFieldView } from "@/lib/api";
import { isRepeatedUnitDetail, supportsUnitInput } from "@/lib/unitInput";
import { UnitInput } from "./UnitInput";

interface Props {
  field: FormFieldView;
  presets?: { label: string; value: number; usage: string; currentmA: number }[];
  siblingCount?: number;
  disabled?: boolean;
  compact?: boolean;
  onCommit: (key: string, value: string) => void;
  onApplyAll?: (key: string, value: string) => void;
}

export function Field({
  field,
  presets = [],
  siblingCount = 1,
  disabled = false,
  compact = false,
  onCommit,
  onApplyAll,
}: Props) {
  const [draft, setDraft] = useState(field.value);
  const generatedId = useId();
  const inputId = `field-${field.key.replace(/[^a-zA-Z0-9_-]/g, "-")}-${generatedId.replace(/:/g, "")}`;
  const helpId = `${inputId}-help`;
  const issuesId = `${inputId}-issues`;
  const describedBy = field.issues.length > 0 ? `${helpId} ${issuesId}` : helpId;
  const suppressNextBlur = useRef(false);
  useEffect(() => {
    setDraft(field.value);
    suppressNextBlur.current = false;
  }, [field.value]);

  const commit = () => {
    if (!disabled && draft !== field.value) onCommit(field.key, draft);
  };
  const helpLines = [
    field.help,
    field.range,
    field.basis && `근거: ${field.basis}`,
    field.affects && `영향: ${field.affects}`,
    field.verification && `검증: ${field.verification}`,
  ].filter(Boolean).join("\n");
  const showDetail = Boolean(field.detail && !isRepeatedUnitDetail(field.kind, field.value, field.detail));

  return (
    <div style={{ padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
      <div className="field-row">
        <label
          htmlFor={inputId}
          style={{ color: field.risk === "critical" ? "var(--danger)" : undefined }}
        >
          {field.label}
          {field.risk === "critical" ? " ⚠" : ""}
        </label>

        {field.kind === "bool" ? (
          <input
            id={inputId}
            type="checkbox"
            checked={field.checked}
            disabled={disabled}
            aria-describedby={describedBy}
            onChange={(e) => onCommit(field.key, e.target.checked ? "예" : "아니오")}
          />
        ) : field.kind === "choice" ? (
          <select
            id={inputId}
            value={field.value}
            disabled={disabled}
            aria-describedby={describedBy}
            onChange={(e) => onCommit(field.key, e.target.value)}
          >
            {field.choices.map((choice) => (
              <option key={choice.value} value={choice.label}>
                {choice.label}
              </option>
            ))}
          </select>
        ) : supportsUnitInput(field.kind) ? (
          <UnitInput
            inputId={inputId}
            inputLabel={field.label}
            kind={field.kind}
            value={field.value}
            numericValue={field.numericValue}
            numericValues={field.numericValues}
            disabled={disabled}
            className={field.hasError ? "error" : ""}
            describedBy={describedBy}
            invalid={field.hasError}
            onApply={(value) => onCommit(field.key, value)}
            onDraftChange={setDraft}
          />
        ) : (
          <input
            id={inputId}
            className={field.hasError ? "error" : ""}
            value={draft}
            disabled={disabled}
            aria-describedby={describedBy}
            aria-invalid={field.hasError || undefined}
            onChange={(e) => {
              suppressNextBlur.current = false;
              setDraft(e.target.value);
            }}
            onBlur={() => {
              if (suppressNextBlur.current) {
                suppressNextBlur.current = false;
                return;
              }
              commit();
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter" || e.repeat) return;
              e.preventDefault();
              suppressNextBlur.current = true;
              commit();
            }}
          />
        )}

        {!supportsUnitInput(field.kind) && <span className="muted">{field.unit}</span>}
        {siblingCount > 1 && onApplyAll && (
          <button
            type="button"
            className="chip"
            disabled={disabled}
            onClick={() => onApplyAll(field.key, draft)}
          >
            같은 실험 {siblingCount}개에 적용
          </button>
        )}
      </div>

      {field.kind === "c_rate" && presets.length > 0 && (
        <div className="field-help field-presets">
          {presets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className="chip"
              disabled={disabled}
              title={`${preset.usage} · ${preset.currentmA.toFixed(0)} mA`}
              onClick={() => onCommit(field.key, preset.label)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      )}

      {field.kind === "duration_s" && /pulse.*_s|dcir_pulse_s/i.test(field.key) && (
        <div className="field-help field-presets" aria-label="펄스 길이 빠른 선택">
          {[10, 30].map((seconds) => (
            <button key={seconds} type="button" className="chip" disabled={disabled} onClick={() => onCommit(field.key, `${seconds}초`)}>
              {seconds}초
            </button>
          ))}
        </div>
      )}

      <div id={helpId} className="muted field-help" style={{ whiteSpace: "pre-line" }}>
        {showDetail && <div>→ {field.detail}</div>}
        {compact ? <details className="parameter-help"><summary>입력 도움말</summary>{helpLines}</details> : helpLines}
      </div>

      {field.issues.length > 0 && (
        <div
          id={issuesId}
          className={`field-help ${field.hasError ? "danger" : "warn"}`}
        >
          {field.issues.join("\n")}
        </div>
      )}
    </div>
  );
}
