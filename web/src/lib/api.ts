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

async function post<T>(path: string, body: Json, allowNotOk = false): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || (!allowNotOk && payload && payload.ok === false)) {
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
  openProject: (data: Json) => post<{ project: Json; repairs: string[]; migratedFrom: string | null }>("/api/project/open", { data }),
  views: (project: Json, selected?: string) =>
    post<{ views: Views }>("/api/views", { project, selected }),

  // The expanded step table is fetched only by the tab that shows it: it is
  // read-only and was 312 KB of a 400 KB response on a large campaign, resent on
  // every edit.
  steps: (project: Json) => post<{ steps: Record<string, string>[] }>("/api/steps", { project }),

  moduleContent: (project: Json, moduleId: string, childIndex?: number) =>
    post<ModuleContent>("/api/module-content", { project, moduleId, childIndex }),

  edit: (action: string, project: Json, args: Json = {}, selected?: string) =>
    post<EditResult>(`/api/edit/${action}`, { project, args, selected }),

  plan: <T>(action: string, project: Json, args: Json = {}) =>
    post<T>(`/api/plan/${action}`, { project, args }, true),

  library: () => get<{ methods: MethodSummary[] }>("/api/library"),

  saveMethod: (project: Json, name: string, description = "", moduleIds?: string[]) =>
    post<{ method: MethodSummary }>("/api/library", { project, name, description, moduleIds }),

  loadMethod: (project: Json, methodId: string, replace = false) =>
    post<EditResult & { warnings: string[] }>("/api/library/load", {
      project,
      methodId,
      replace,
    }),

  openImport: (path: string) =>
    post<ImportInfo>("/api/import/open", { path }),

  stageImport: (sessionId: string, stepNo: number, field: string, value: number) =>
    post<ImportProposal>(`/api/import/${sessionId}/stage`, { stepNo, field, value }, true),

  clearImport: (sessionId: string) =>
    post<ImportProposal>(`/api/import/${sessionId}/clear`, {}, true),

  patchImport: (sessionId: string, outputPath: string) =>
    post<ImportPatchResult>(`/api/import/${sessionId}/patch`, {
      outputPath,
      allowAnalysisOutput: true,
    }),

  exportProject: (project: Json, kind: "draft_save" | "preview" | "review_candidate", outDir: string) =>
    post<{ ok: true; paths: string[]; note: string }>("/api/export", {
      project, kind, outDir,
    }),

  planCellBatch: (project: Json, args: Json) =>
    post<CellBatchPlan>("/api/plan/cellBatch", { project, args }, true),

  exportCellBatch: (project: Json, args: Json, token: string, outDir: string) =>
    post<{ ok: true; paths: string[]; note: string }>("/api/export/cell-batch", {
      project, args, token, outDir,
    }),

  storage: () => get<StorageResponse>("/api/storage"),
  addStorage: (record: Json) => post<{ ok: true; record: StorageRecord }>("/api/storage", record),
  importStorage: (records: StorageRecord[]) =>
    post<{ ok: true; inserted: number; alreadyPresent: number }>("/api/storage/import-legacy", { records }),
  completeStorage: (id: string, completed: boolean) =>
    post<{ ok: true }>(`/api/storage/${encodeURIComponent(id)}/complete`, { completed }),
  storageNotifications: (id: string, enabled: boolean) =>
    post<{ ok: true }>(`/api/storage/${encodeURIComponent(id)}/notifications`, { enabled }),
  acknowledgeStorageAlert: (id: string, alertId: string) =>
    post<{ ok: true }>(`/api/storage/${encodeURIComponent(id)}/alerts/${encodeURIComponent(alertId)}/acknowledge`, {}),
  snoozeStorageAlert: (id: string, alertId: string, until: string) =>
    post<{ ok: true }>(`/api/storage/${encodeURIComponent(id)}/alerts/${encodeURIComponent(alertId)}/snooze`, { until }),
};

export interface StorageAlert {
  id: string;
  kind: "checkpoint" | "final";
  checkpointDay: number | null;
  dueAt: string;
  acknowledgedAt: string | null;
  snoozedUntil: string | null;
  notifiedAt: string | null;
}

export interface StorageRecord {
  id: string;
  sample: string;
  temperatureC: number;
  startedAt: string;
  targetDays: number;
  dueAt: string;
  checkpointDays: number[];
  notifyEnabled: boolean;
  completedAt: string | null;
  notifiedAt: string | null;
  alerts: StorageAlert[];
}

export interface StorageResponse {
  ok: true;
  records: StorageRecord[];
  companion: { active: boolean; lastHeartbeatAt: string | null };
}

export interface CellBatchPlan {
  ok: boolean;
  token: string;
  note: string;
  errors: string[];
  warnings: string[];
  rows: {
    cellId: string;
    designCapacityMah: number | null;
    selectedCapacityMah: number | null;
    basis: string;
    oneCmA: number | null;
    maxCurrentmA: number | null;
    fixedCurrentSteps: number;
    allowed: boolean;
    blockers: string[];
  }[];
}

// --- payload shapes ---------------------------------------------------------

export interface FormFieldView {
  key: string;
  label: string;
  kind: string;
  unit: string;
  value: string;
  numericValue?: number | null;
  numericValues?: number[] | null;
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

export interface ModuleContentStep {
  index: number;
  number: number;
  stepType: string;
  mode: string;
  title: string;
  summary: string;
  fields: { key: string; label: string; kind: string; text: string; numericValue?: number | null; detail: string }[];
}

export interface ModuleContent {
  ok: true;
  moduleId: string;
  childIndex: number | null;
  moduleType: string;
  title: string;
  customized: boolean;
  stepCount: number;
  steps: ModuleContentStep[];
  children: {
    index: number;
    moduleId: string;
    moduleType: string;
    title: string;
    summary: string;
    repeatCount: number;
    stepCount: number;
    form: Views["form"];
  }[];
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
  groupChildren: { index: number; form: Views["form"] }[];
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
  palette: {
    moduleType: string;
    title: string;
    category: string;
    description: string;
    trust: string;
  }[];
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
  procedure: { durationSeconds: number | null; durationExact: boolean; durationComplete?: boolean; durationUpperBoundSeconds?: number | null; stepCount: number };
  steps: Record<string, string>[];
  canEditSteps: boolean;
  customSteps: {
    index: number;
    number: number;
    stepType: string;
    mode: string;
    label: string;
    fields: { key: string; label: string; kind: string; text: string; numericValue?: number | null; detail: string }[];
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
  diff: {
    headline: string;
    beforeCount?: number;
    afterCount?: number;
    changes?: { kind: string; label: string; fields: { field: string; before: unknown; after: unknown }[] }[];
  } | null;
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

export interface ImportInfo {
  ok: true;
  sessionId: string;
  path: string;
  sha256: string;
  schVersion: string;
  stepCount: number;
  editableFields: { name: string; offset: number; dtype: string; evidence: string; label?: string; unit?: string }[];
  dropIfCloned: string[];
  explanation: string;
}

export interface ImportProposal {
  ok: boolean;
  accepted: { stepNo: number; field: string; value: number }[];
  rejected: { stepNo: number; field: string; reason: string }[];
  notes: string[];
  warnings: string[];
  plan: Json | null;
}

export interface ImportPatchResult {
  ok: true;
  outputPath: string;
  manifestPath: string;
  equipmentExecutable: false;
  changedByteCount: number;
}
