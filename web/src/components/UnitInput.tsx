"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  commitValue,
  convertDraft,
  defaultUnit,
  displayValue,
  inferNumericValue,
  type UnitInputKind,
  unitChoices,
} from "@/lib/unitInput";

interface UnitInputProps {
  kind: UnitInputKind;
  value: string;
  numericValue?: number | null;
  numericValues?: number[] | null;
  disabled?: boolean;
  inputId?: string;
  inputLabel?: string;
  className?: string;
  describedBy?: string;
  invalid?: boolean;
  onApply: (value: string) => void;
  onDraftChange?: (value: string) => void;
}

export function UnitInput({
  kind,
  value,
  numericValue = null,
  numericValues = null,
  disabled = false,
  inputId,
  inputLabel,
  className,
  describedBy,
  invalid = false,
  onApply,
  onDraftChange,
}: UnitInputProps) {
  const generatedId = useId().replace(/:/g, "");
  const id = inputId ?? `unit-input-${generatedId}`;
  const choices = unitChoices(kind);
  const canonical = numericValue ?? inferNumericValue(kind, value);
  const [unit, setUnit] = useState(() => defaultUnit(kind, canonical, numericValues));
  const [draft, setDraft] = useState(() => displayValue(kind, canonical, value, defaultUnit(kind, canonical, numericValues), numericValues));
  const baseline = useRef(draft);
  const suppressNextBlur = useRef(false);
  const unitSelect = useRef<HTMLSelectElement>(null);
  const preferredUnit = useRef<{ kind: UnitInputKind; unit: string } | null>(null);

  useEffect(() => {
    const nextUnit = preferredUnit.current?.kind === kind
      ? preferredUnit.current.unit : defaultUnit(kind, canonical, numericValues);
    const nextDraft = displayValue(kind, canonical, value, nextUnit, numericValues);
    setUnit(nextUnit);
    setDraft(nextDraft);
    baseline.current = nextDraft;
    suppressNextBlur.current = false;
  }, [kind, canonical, numericValues, value]);

  const apply = () => {
    if (disabled || draft === baseline.current) return;
    onApply(commitValue(kind, draft, unit));
  };

  return (
    <span className="unit-input">
      <input
        id={id}
        aria-label={inputLabel}
        className={className}
        value={draft}
        disabled={disabled}
        inputMode={kind === "c_rate" || kind.endsWith("_list") ? "text" : "decimal"}
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
        onChange={(event) => {
          suppressNextBlur.current = false;
          setDraft(event.target.value);
          onDraftChange?.(commitValue(kind, event.target.value, unit));
        }}
        onBlur={(event) => {
          if (event.relatedTarget === unitSelect.current) return;
          if (suppressNextBlur.current) {
            suppressNextBlur.current = false;
            return;
          }
          apply();
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.repeat) {
            event.preventDefault();
            suppressNextBlur.current = true;
            apply();
            event.currentTarget.blur();
          } else if (event.key === "Escape") {
            event.preventDefault();
            suppressNextBlur.current = true;
            setDraft(baseline.current);
            onDraftChange?.(commitValue(kind, baseline.current, unit));
            event.currentTarget.blur();
          }
        }}
      />
      {choices.length > 1 ? (
        <label className="unit-input-unit">
          <span>단위</span>
          <select
            ref={unitSelect}
            value={unit}
            aria-label={`${inputLabel ?? "입력"} 단위`}
            disabled={disabled}
            onBlur={apply}
            onChange={(event) => {
              const nextUnit = event.target.value;
              const converted = convertDraft(kind, draft, unit, nextUnit);
              const convertedBaseline = convertDraft(kind, baseline.current, unit, nextUnit);
              if (converted === null || convertedBaseline === null) return;
              setDraft(converted);
              baseline.current = convertedBaseline;
              setUnit(nextUnit);
              preferredUnit.current = { kind, unit: nextUnit };
              onDraftChange?.(commitValue(kind, converted, nextUnit));
            }}
          >
            {choices.map((choice) => <option key={choice.label}>{choice.label}</option>)}
          </select>
        </label>
      ) : (
        <span className="unit-input-suffix" aria-label={`단위 ${unit}`}>{unit}</span>
      )}
    </span>
  );
}
