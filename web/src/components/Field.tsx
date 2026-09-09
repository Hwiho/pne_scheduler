"use client";

// One parameter, rendered from its spec rather than from hand-written markup.
//
// `spec/module_params.py` already declares each parameter's Korean label, unit,
// allowed and recommended range, the basis for its default and how far it has
// been verified. Rendering from that means a new parameter appears here with its
// documentation intact, and cannot arrive as an undocumented JSON key.

import { useEffect, useState } from "react";
import type { FormFieldView } from "@/lib/api";

interface Props {
  field: FormFieldView;
  presets?: { label: string; value: number; usage: string; currentmA: number }[];
  siblingCount?: number;
  onCommit: (key: string, value: string) => void;
  onApplyAll?: (key: string, value: string) => void;
}

export function Field({ field, presets = [], siblingCount = 1, onCommit, onApplyAll }: Props) {
  const [draft, setDraft] = useState(field.value);
  useEffect(() => setDraft(field.value), [field.value]);

  const commit = () => {
    if (draft !== field.value) onCommit(field.key, draft);
  };

  return (
    <div style={{ padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
      <div className="row">
        <label
          style={{ width: 170, fontWeight: 600, color: field.risk === "critical" ? "var(--danger)" : undefined }}
        >
          {field.label}
          {field.risk === "critical" ? " ⚠" : ""}
        </label>

        {field.kind === "bool" ? (
          <input
            type="checkbox"
            checked={field.checked}
            onChange={(e) => onCommit(field.key, e.target.checked ? "예" : "아니오")}
          />
        ) : field.kind === "choice" ? (
          <select value={field.value} onChange={(e) => onCommit(field.key, e.target.value)}>
            {field.choices.map((choice) => (
              <option key={choice.value} value={choice.label}>
                {choice.label}
              </option>
            ))}
          </select>
        ) : (
          <input
            className={field.hasError ? "error" : ""}
            style={{ width: 200 }}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && commit()}
          />
        )}

        <span className="muted">{field.unit}</span>
        <span className="grow" />
        {siblingCount > 1 && onApplyAll && (
          <button className="chip" onClick={() => onApplyAll(field.key, draft)}>
            같은 실험 {siblingCount}개에 적용
          </button>
        )}
      </div>

      {field.kind === "c_rate" && presets.length > 0 && (
        <div className="row" style={{ marginLeft: 170, flexWrap: "wrap", gap: 4, marginTop: 4 }}>
          {presets.map((preset) => (
            <button
              key={preset.label}
              className="chip"
              title={`${preset.usage} · ${preset.currentmA.toFixed(0)} mA`}
              onClick={() => onCommit(field.key, preset.label)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      )}

      <div className="muted" style={{ marginLeft: 170, marginTop: 3, whiteSpace: "pre-line" }}>
        {[
          field.detail && `→ ${field.detail}`,
          field.help,
          field.range,
          field.basis && `근거: ${field.basis}`,
          field.affects && `영향: ${field.affects}`,
          field.verification && `검증: ${field.verification}`,
        ]
          .filter(Boolean)
          .join("\n")}
      </div>

      {field.issues.length > 0 && (
        <div
          className={field.hasError ? "danger" : "warn"}
          style={{ marginLeft: 170, fontSize: 11, marginTop: 3 }}
        >
          {field.issues.join("\n")}
        </div>
      )}
    </div>
  );
}
