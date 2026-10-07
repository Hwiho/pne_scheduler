"use client";

// Browser-held editing session. The server stays stateless; history and a
// local recovery copy therefore live here.

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type EditResult, type Json, type Views } from "./api";

const STORAGE_KEY = "pne_scheduler.draft.v1";
const UNDO_LIMIT = 50;

interface HistoryEntry {
  project: Json;
  label: string;
}

export interface DocumentState {
  project: Json | null;
  views: Views | null;
  selected: string;
  busy: boolean;
  error: string;
  notice: string;
  lastDiff: EditResult["diff"];
  canUndo: boolean;
  canRedo: boolean;
  undoLabel: string;
}

interface DocumentApi {
  views: (project: Json, selected?: string) => Promise<{ views: Views }>;
  edit: (action: string, project: Json, args?: Json, selected?: string) => Promise<EditResult>;
}

interface RecoveryStorage {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
}

export interface RecoveryRead {
  project: Json | null;
  warning: string;
  writable: boolean;
}

export function readRecovery(storage: RecoveryStorage): RecoveryRead {
  try {
    const saved = storage.getItem(STORAGE_KEY);
    if (!saved) return { project: null, warning: "", writable: true };
    try {
      return { project: JSON.parse(saved) as Json, warning: "", writable: true };
    } catch {
      // Keep malformed data intact: it may still be manually recoverable.
      return {
        project: null,
        warning:
          "브라우저 복구본을 읽을 수 없어 그대로 보존했습니다. 새 작업은 메모리에서 계속할 수 있습니다.",
        writable: false,
      };
    }
  } catch {
    return {
      project: null,
      warning: "브라우저 복구 저장소를 사용할 수 없습니다. 현재 작업은 메모리에서 계속 유지됩니다.",
      writable: false,
    };
  }
}

export function writeRecovery(storage: RecoveryStorage, project: Json): string {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(project));
    return "";
  } catch {
    // Never roll back the live document after a security/private-mode/quota failure.
    return "브라우저 복구본을 저장하지 못했습니다. 현재 작업은 메모리에서 유지되지만 탭을 닫지 마십시오.";
  }
}

function errorMessage(err: unknown): string {
  return err instanceof ApiError || err instanceof Error ? err.message : String(err);
}

/** UI-independent coordinator used by the hook and async regression tests. */
export class DocumentSession {
  private project: Json | null = null;
  private views: Views | null = null;
  private selected = "";
  private error = "";
  private actionNotice = "";
  private recoveryWarning = "";
  private lastDiff: EditResult["diff"] = null;
  private undoStack: HistoryEntry[] = [];
  private redoStack: HistoryEntry[] = [];
  private pending = 0;
  private mutationTail: Promise<void> = Promise.resolve();
  private viewRequest = 0;
  private listeners = new Set<(state: DocumentState) => void>();

  constructor(private readonly client: DocumentApi = api) {}

  snapshot = (): DocumentState => ({
    project: this.project,
    views: this.views,
    selected: this.selected,
    busy: this.pending > 0,
    error: this.error,
    notice: [this.actionNotice, this.recoveryWarning].filter(Boolean).join(" · "),
    lastDiff: this.lastDiff,
    canUndo: this.undoStack.length > 0,
    canRedo: this.redoStack.length > 0,
    undoLabel: this.undoStack[this.undoStack.length - 1]?.label ?? "",
  });

  subscribe = (listener: (state: DocumentState) => void): (() => void) => {
    this.listeners.add(listener);
    listener(this.snapshot());
    return () => this.listeners.delete(listener);
  };

  private publish(): void {
    const state = this.snapshot();
    this.listeners.forEach((listener) => listener(state));
  }

  private begin(): void {
    this.pending += 1;
    this.publish();
  }

  private end(): void {
    this.pending = Math.max(0, this.pending - 1);
    this.publish();
  }

  private enqueue(operation: () => Promise<void>): Promise<void> {
    this.begin();
    const run = this.mutationTail.then(operation, operation);
    this.mutationTail = run.catch(() => undefined);
    return run
      .catch((err: unknown) => {
        this.error = errorMessage(err);
        this.publish();
      })
      .finally(() => this.end());
  }

  private invalidateViewRequests(): void {
    this.viewRequest += 1;
  }

  setError = (message: string): void => {
    this.error = message;
    this.publish();
  };

  setRecoveryWarning = (message: string): void => {
    this.recoveryWarning = message;
    this.publish();
  };

  open = (next: Json): Promise<void> =>
    this.enqueue(async () => {
      this.error = "";
      const ticket = ++this.viewRequest;
      const body = await this.client.views(next, this.selected);
      if (ticket !== this.viewRequest) return;

      this.project = next;
      this.views = body.views;
      this.selected = body.views.selectedModule;
      this.undoStack = [];
      this.redoStack = [];
      this.actionNotice = "";
      this.lastDiff = null;
      this.publish();
    });

  apply = (action: string, args: Json = {}): Promise<void> =>
    this.enqueue(async () => {
      const before = this.project;
      if (!before) return;
      this.error = "";
      const result = await this.client.edit(action, before, args, this.selected);

      // A selection refresh based on `before` cannot overwrite this edit.
      this.invalidateViewRequests();
      this.undoStack = [...this.undoStack, { project: before, label: result.label }].slice(
        -UNDO_LIMIT,
      );
      this.redoStack = [];
      this.project = result.project;
      this.views = result.views;
      this.selected = result.views.selectedModule;
      this.actionNotice = result.label || "";
      this.lastDiff = result.diff;
      this.publish();
    });

  replace = (next: Json, label = "프로젝트 열기"): Promise<void> =>
    this.enqueue(async () => {
      const before = this.project;
      this.error = "";
      const ticket = ++this.viewRequest;
      const body = await this.client.views(next);
      if (ticket !== this.viewRequest) return;
      if (before) this.undoStack = [...this.undoStack, { project: before, label }].slice(-UNDO_LIMIT);
      this.redoStack = [];
      this.project = next;
      this.views = body.views;
      this.selected = body.views.selectedModule;
      this.actionNotice = label + " · 이전 작업은 되돌리기로 복원할 수 있습니다.";
      this.lastDiff = null;
      this.publish();
    });

  undo = (): Promise<void> =>
    this.enqueue(async () => {
      const entry = this.undoStack[this.undoStack.length - 1];
      const before = this.project;
      if (!entry || !before) return;
      this.error = "";
      const ticket = ++this.viewRequest;
      const body = await this.client.views(entry.project, this.selected);
      if (ticket !== this.viewRequest || this.project !== before) return;

      // Move one history entry only after the target has valid views.
      this.undoStack = this.undoStack.slice(0, -1);
      this.redoStack = [...this.redoStack, { project: before, label: entry.label }];
      this.project = entry.project;
      this.views = body.views;
      this.selected = body.views.selectedModule;
      this.actionNotice = `되돌림: ${entry.label}`;
      this.lastDiff = null;
      this.publish();
    });

  redo = (): Promise<void> =>
    this.enqueue(async () => {
      const entry = this.redoStack[this.redoStack.length - 1];
      const before = this.project;
      if (!entry || !before) return;
      this.error = "";
      const ticket = ++this.viewRequest;
      const body = await this.client.views(entry.project, this.selected);
      if (ticket !== this.viewRequest || this.project !== before) return;

      this.redoStack = this.redoStack.slice(0, -1);
      this.undoStack = [...this.undoStack, { project: before, label: entry.label }].slice(
        -UNDO_LIMIT,
      );
      this.project = entry.project;
      this.views = body.views;
      this.selected = body.views.selectedModule;
      this.actionNotice = `다시 실행: ${entry.label}`;
      this.lastDiff = null;
      this.publish();
    });

  select = async (moduleId: string): Promise<void> => {
    const previousSelected = this.selected;
    this.selected = moduleId;
    const base = this.project;
    this.publish();
    if (!base) return;

    const ticket = ++this.viewRequest;
    this.begin();
    try {
      const body = await this.client.views(base, moduleId);
      if (ticket !== this.viewRequest || this.project !== base) return;
      this.views = body.views;
      this.selected = body.views.selectedModule;
      this.error = "";
      this.publish();
    } catch (err) {
      if (ticket === this.viewRequest && this.project === base) {
        this.selected = this.views?.selectedModule ?? previousSelected;
        this.error = errorMessage(err);
        this.publish();
      }
    } finally {
      this.end();
    }
  };
}

export function useDocument() {
  const sessionRef = useRef<DocumentSession | null>(null);
  if (!sessionRef.current) sessionRef.current = new DocumentSession();
  const session = sessionRef.current;
  const [state, setState] = useState<DocumentState>(() => session.snapshot());
  const initialized = useRef(false);
  const recoveryWritable = useRef(true);

  useEffect(() => session.subscribe(setState), [session]);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    let recovery: RecoveryRead = { project: null, warning: "", writable: true };
    if (typeof window !== "undefined") {
      try {
        recovery = readRecovery(window.localStorage);
      } catch {
        // Accessing the localStorage property itself can throw.
        recovery.warning =
          "브라우저 복구 저장소를 사용할 수 없습니다. 현재 작업은 메모리에서 계속 유지됩니다.";
        recovery.writable = false;
      }
    }
    recoveryWritable.current = recovery.writable;
    session.setRecoveryWarning(recovery.warning);
    void session.open(recovery.project ?? emptyProject());
  }, [session]);

  useEffect(() => {
    if (!state.project || typeof window === "undefined" || !recoveryWritable.current) return;
    let warning: string;
    try {
      warning = writeRecovery(window.localStorage, state.project);
    } catch {
      warning =
        "브라우저 복구본을 저장하지 못했습니다. 현재 작업은 메모리에서 유지되지만 탭을 닫지 마십시오.";
    }
    session.setRecoveryWarning(warning);
  }, [session, state.project]);

  const open = useCallback((next: Json) => session.open(next), [session]);
  const apply = useCallback(
    (action: string, args: Json = {}) => session.apply(action, args),
    [session],
  );
  const replace = useCallback((next: Json, label?: string) => session.replace(next, label), [session]);
  const undo = useCallback(() => session.undo(), [session]);
  const redo = useCallback(() => session.redo(), [session]);
  const select = useCallback((moduleId: string) => session.select(moduleId), [session]);
  const setError = useCallback((message: string) => session.setError(message), [session]);

  return { ...state, open, replace, apply, undo, redo, select, setError };
}

export function emptyProject(): Json {
  return {
    schema: "pne_scheduler.schproj/v2",
    name: "새 스케줄",
    sch_version: 0x00010003,
    cell_profile: { nominal_capacity_mAh: 80.0, v_min: 2.5, v_max: 4.2 },
    modules: [],
    connections: [],
  };
}
