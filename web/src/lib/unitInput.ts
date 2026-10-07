export type UnitInputKind =
  | "duration_s"
  | "voltage_v"
  | "current_mA"
  | "c_rate"
  | "c_rate_list"
  | "duration_list"
  | "voltage_list"
  | "percent"
  | "fraction"
  | "soc_percent"
  | "soc_percent_list"
  | "count";

export interface UnitChoice {
  label: string;
  factor: number;
}

/** Never silently omit a malformed stage from a current-linked protocol. */
export function parsePositiveRateList(text: string): number[] {
  const tokens = text.split(",").map((token) => token.trim());
  if (tokens.some((token) => !token)) throw new Error("충전율을 쉼표로 구분해 모두 입력하세요. 비어 있는 단계는 사용할 수 없습니다.");
  const rates = tokens.map(Number);
  if (rates.some((rate) => !Number.isFinite(rate) || rate <= 0)) throw new Error("충전율은 양수인 숫자만 입력하세요. 잘못된 단계를 빼고 계산하지 않습니다.");
  return rates;
}

const UNIT_CHOICES: Record<UnitInputKind, readonly UnitChoice[]> = {
  duration_s: [
    { label: "초", factor: 1 },
    { label: "분", factor: 60 },
    { label: "시간", factor: 3600 },
    { label: "일", factor: 86400 },
  ],
  voltage_v: [{ label: "V", factor: 1 }, { label: "mV", factor: 0.001 }],
  current_mA: [{ label: "mA", factor: 1 }, { label: "A", factor: 1000 }],
  c_rate: [{ label: "C", factor: 1 }],
  c_rate_list: [{ label: "C", factor: 1 }],
  voltage_list: [{ label: "V", factor: 1 }, { label: "mV", factor: 0.001 }],
  duration_list: [
    { label: "초", factor: 1 },
    { label: "분", factor: 60 },
    { label: "시간", factor: 3600 },
    { label: "일", factor: 86400 },
  ],
  percent: [{ label: "%", factor: 1 }],
  fraction: [{ label: "%", factor: 0.01 }],
  soc_percent: [{ label: "%", factor: 0.01 }],
  soc_percent_list: [{ label: "%", factor: 0.01 }],
  count: [{ label: "회", factor: 1 }],
};

const UNIT_KINDS = new Set(Object.keys(UNIT_CHOICES));

export function supportsUnitInput(kind: string): kind is UnitInputKind {
  return UNIT_KINDS.has(kind);
}

export function unitChoices(kind: UnitInputKind): readonly UnitChoice[] {
  return UNIT_CHOICES[kind];
}

export function defaultUnit(kind: UnitInputKind, canonical: number | null, values?: readonly number[] | null): string {
  if (kind === "duration_list") {
    if (values?.length) {
      for (const choice of [...UNIT_CHOICES.duration_list].reverse()) {
        if (values.every((value) => Number.isFinite(value) && value >= choice.factor && value % choice.factor === 0)) return choice.label;
      }
    }
    return "초";
  }
  if (kind !== "duration_s" || canonical === null || !Number.isFinite(canonical)) {
    return UNIT_CHOICES[kind][0].label;
  }
  if (canonical >= 86400 && canonical % 86400 === 0) return "일";
  if (canonical >= 3600 && canonical % 3600 === 0) return "시간";
  if (canonical >= 60 && canonical % 60 === 0) return "분";
  return "초";
}

function factorFor(kind: UnitInputKind, unit: string): number {
  return UNIT_CHOICES[kind].find((choice) => choice.label === unit)?.factor ?? 1;
}

/** Number#toString is the shortest decimal that round-trips to the same double. */
export function exactNumber(value: number): string {
  return Object.is(value, -0) ? "0" : value.toString();
}

/** Compatibility for views from an older API; never label 6시간 as 6초. */
export function inferNumericValue(kind: UnitInputKind, text: string): number | null {
  const raw = text.trim();
  if (!raw || kind.endsWith("_list")) return null;
  if (kind === "duration_s") {
    const compact = raw.replace(/\s/g, "");
    const token = /(\d+(?:\.\d+)?)(시간|분|초|일|h|m|s|d)?/gy;
    const factors: Record<string, number> = { 시간: 3600, 분: 60, 초: 1, 일: 86400, h: 3600, m: 60, s: 1, d: 86400 };
    let total = 0, end = 0, match;
    while ((match = token.exec(compact)) !== null) {
      total += Number(match[1]) * (factors[match[2] ?? "s"] ?? 1);
      end = token.lastIndex;
    }
    return end === compact.length ? total : null;
  }
  if (kind === "c_rate" && /^C\s*\/\s*\d+(?:\.\d+)?$/i.test(raw)) {
    const denominator = Number(raw.split("/")[1]);
    return denominator > 0 ? 1 / denominator : null;
  }
  const numeric = Number(stripVisibleUnit(kind, raw));
  if (!Number.isFinite(numeric)) return null;
  if (kind === "soc_percent") return numeric / 100;
  if (kind === "voltage_v" && /mV$/i.test(raw)) return numeric / 1000;
  if (kind === "current_mA" && /(?<!m)A$/i.test(raw)) return numeric * 1000;
  return numeric;
}

function stripVisibleUnit(kind: UnitInputKind, value: string): string {
  const trimmed = value.trim();
  if (kind === "soc_percent_list") {
    return trimmed.replace(/[%％]/g, "").replace(/\s*,\s*/g, ", ");
  }
  if (kind === "c_rate_list") {
    return trimmed.split(",").map((part) => /^C\s*\//i.test(part.trim())
      ? part.trim().replace(/^C\s*\//i, "1/") : part.trim().replace(/\s*C\s*$/i, "")).join(", ");
  }
  if (kind === "c_rate" && /^C\s*\//i.test(trimmed)) return trimmed;
  if (kind === "duration_s") return trimmed.replace(/\s*(초|분|시간|일)\s*$/i, "");
  if (kind === "voltage_v") return trimmed.replace(/\s*(mV|V|ｍＶ|Ｖ)\s*$/i, "");
  if (kind === "current_mA") return trimmed.replace(/\s*(mA|A)\s*$/i, "");
  if (kind === "c_rate") return trimmed.replace(/\s*C\s*$/i, "");
  if (kind === "percent" || kind === "fraction" || kind === "soc_percent") return trimmed.replace(/\s*[%％]\s*$/, "");
  if (kind === "count") return trimmed.replace(/\s*회\s*$/, "").replaceAll(",", "");
  return trimmed;
}

export function displayValue(
  kind: UnitInputKind,
  canonical: number | null,
  sourceText: string,
  unit: string,
  values?: readonly number[] | null,
): string {
  if (kind === "c_rate_list" && values?.length) return values.map((value) => value === 1 / 3 ? "1/3" : exactNumber(value)).join(", ");
  if ((kind === "duration_list" || kind === "voltage_list") && values?.length) return values.map((value) => exactNumber(value / factorFor(kind, unit))).join(", ");
  if (kind === "soc_percent_list") return stripVisibleUnit(kind, sourceText);
  if (canonical === null || !Number.isFinite(canonical)) return stripVisibleUnit(kind, sourceText);
  if (kind === "c_rate" && canonical === 1 / 3) return "1/3";
  return exactNumber(canonical / factorFor(kind, unit));
}

export function convertDraft(
  kind: UnitInputKind,
  draft: string,
  fromUnit: string,
  toUnit: string,
): string | null {
  if (!draft.trim()) return null;
  if (kind === "duration_list" || kind === "voltage_list") {
    const parts = draft.split(",").map((part) => convertDraft(kind === "duration_list" ? "duration_s" : "voltage_v", part, fromUnit, toUnit));
    return parts.some((part) => part === null) ? null : parts.join(", ");
  }
  const numeric = Number(draft.trim());
  if (!Number.isFinite(numeric)) return null;
  const canonical = numeric * factorFor(kind, fromUnit);
  return exactNumber(canonical / factorFor(kind, toUnit));
}

/** Convert only the selected display unit; range and protocol validation stay server-side. */
export function commitValue(kind: UnitInputKind, draft: string, unit: string): string {
  const trimmed = draft.trim();
  if (!trimmed) return "";
  if (kind === "c_rate_list") return trimmed.split(",").map((part) => commitValue("c_rate", part, unit)).join(", ");
  if (kind === "duration_list") return trimmed.split(",").map((part) => commitValue("duration_s", part, unit)).join(", ");
  if (kind === "voltage_list") return trimmed.split(",").map((part) => commitValue("voltage_v", part, unit)).join(", ");
  if (kind === "c_rate" && /^C\s*\//i.test(trimmed)) return trimmed;
  if (kind === "c_rate" && /^1\s*\/\s*\d+(?:\.\d+)?$/.test(trimmed)) return `C/${trimmed.split("/")[1].trim()}`;
  if (kind === "fraction" || kind === "soc_percent" || kind === "soc_percent_list") return `${trimmed}%`;
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return trimmed;
  return exactNumber(numeric * factorFor(kind, unit));
}

function comparableDetail(value: string): string {
  return value
    .replace(/\bSOC\b/gi, "")
    .replace(/[／/]/g, ",")
    .replace(/[％]/g, "%")
    .replace(/\s+/g, "")
    .replace(/,+/g, ",")
    .replace(/^,|,$/g, "");
}

/** Hide server detail only when it restates the same quantity, not semantic context. */
export function isRepeatedUnitDetail(kind: string, value: string, detail: string): boolean {
  if (!detail) return false;
  if (kind === "duration_s" || kind === "duration_list") return true;
  if (!["soc_percent", "soc_percent_list", "fraction", "fraction_list"].includes(kind)) return false;
  return comparableDetail(value) === comparableDetail(detail);
}
