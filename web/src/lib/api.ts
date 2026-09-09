// The one place that talks to the Python API.
//
// Every gate decision — what may be exported, whether a file is
// equipment-executable — is computed on the server and arrives here as data.
// Nothing in this app recomputes one; see planning/WEB_PORT_PLAN.md §8.

export type Json = Record<string, unknown>;

export interface ApiFailure {
  ok: false;
  error: string;
  detail?: unknown;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function post<T>(path: string, body: Json): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || (payload && payload.ok === false)) {
    const message =
      (payload as ApiFailure | null)?.error ?? `요청이 실패했습니다 (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      (payload as ApiFailure | null)?.error ?? `요청이 실패했습니다 (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return payload as T;
}

export const api = {
  views: (project: Json, selected?: string) =>
    post<{ views: Views }>("/api/views", { project, selected }),

  edit: (action: string, project: Json, args: Json = {}) =>
    post<EditResult>(`/api/edit/${action}`, { project, args }),

  plan: <T>(action: string, project: Json, args: Json = {}) =>
    post<T>(`/api/plan/${action}`, { project, args }),

  library: () => get<{ methods: MethodSummary[] }>("/api/library"),

  saveMethod: (project: Json, name: string, description = "") =>
    post<{ method: MethodSummary }>("/api/library", { project, name, description }),

  loadMethod: (project: Json, methodId: string, replace = false) =>
    post<EditResult & { warnings: string[] }>("/api/library/load", {
      project,
      methodId,
      replace,
    }),
};

// --- payload shapes ---------------------------------------------------------

export interface FormFieldView {
  key: string;
  label: string;
  kind: string;
  unit: string;
  value: string;
  detail: string;
  help: string;
  basis: string;
  affects: string;
  range: string;
  risk: string;
  verification: string;
  advanced: boolean;
  choices: { value: string; label: string; help: string }[];
  checked: boolean;
  notes: string[];
  issues: string[];
  hasError: boolean;
}

export interface SetupFieldView {
  key: string;
  label: string;
  value: string;
  detail: string;
  issue: string;
  readOnly: boolean;
  choices: string[];
}

export interface ReleaseOption {
  kind: string;
  title: string;
  description: string;
  allowed: boolean;
  blockers: string[];
  nextAction: string;
  danger: boolean;
  recommended: boolean;
  status: string;
}

export interface Views {
  title: string;
  dirty: boolean;
  selectedModule: string;
  summary: { headline: string; text: string; totalSteps: number; durationText: string };
  release: {
    stage: string;
    stageLabel: string;
    stageIndex: number;
    label: {
      label: string;
      labelKo: string;
      meaning: string;
      reasons: string[];
      equipmentExecutable: boolean;
      digestMismatch: boolean;
    } | null;
    options: ReleaseOption[];
  };
  setupFields: SetupFieldView[];
  unitChoices: string[];
  currentLimitmA: number | null;
  cRatePresets: { label: string; value: number; usage: string; currentmA: number }[];
  goals: {
    goalId: string;
    title: string;
    question: string;
    outcome: string;
    trust: string;
    note: string;
  }[];
  paletteTypes: string[];
  modules: {
    moduleId: string;
    moduleType: string;
    position: number;
    title: string;
    subtitle: string;
    steps: number;
    range: string;
    duration: string;
    trust: string;
    error: string;
  }[];
  form: {
    moduleId: string;
    moduleType: string;
    title: string;
    trust: string;
    limitations: string[];
    siblingCount: number;
    derived: { label: string; text: string; severity: string; help: string }[];
    sections: { title: string; fields: FormFieldView[] }[];
  };
  procedure: { durationSeconds: number | null; durationExact: boolean; stepCount: number };
  steps: Record<string, string>[];
  canEditSteps: boolean;
  customSteps: {
    index: number;
    number: number;
    stepType: string;
    mode: string;
    label: string;
    fields: { key: string; label: string; kind: string; text: string; detail: string }[];
  }[];
  validation: {
    severity: string;
    severityLabel: string;
    code: string;
    location: string;
    message: string;
    moduleId: string;
    fieldKey: string;
    stepNumber: number;
    remediation: string;
  }[];
  unverified: string[];
}

export interface EditResult {
  project: Json;
  label: string;
  diff: { headline: string } | null;
  views: Views;
}

export interface MethodSummary {
  methodId: string;
  version: number;
  name: string;
  label: string;
  description: string;
  equipmentUnit: string;
  moduleCount: number;
  savedAt: string;
}
