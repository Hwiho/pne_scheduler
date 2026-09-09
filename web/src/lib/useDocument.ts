"use client";

// The editing session, held in the browser.
//
// The server is stateless by design: an undo entry is just a past project, so
// the stack lives here rather than pinning memory server-side and dying on a
// restart. Autosave goes to localStorage for the same reason the desktop build
// wrote a recovery file — a closed tab must not lose an afternoon.

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
  canUndo: boolean;
  canRedo: boolean;
  undoLabel: string;
}

export function useDocument() {
  const [project, setProject] = useState<Json | null>(null);
  const [views, setViews] = useState<Views | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const undo = useRef<HistoryEntry[]>([]);
  const redo = useRef<HistoryEntry[]>([]);
  const [, force] = useState(0);

  const refresh = useCallback(
    async (next: Json, pick?: string) => {
      const body = await api.views(next, pick ?? selected);
      setViews(body.views);
      if (!pick && !selected) setSelected(body.views.selectedModule);
    },
    [selected],
  );

  // --- loading ---------------------------------------------------------

  const open = useCallback(
    async (next: Json) => {
      setBusy(true);
      setError("");
      try {
        setProject(next);
        undo.current = [];
        redo.current = [];
        await refresh(next);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  useEffect(() => {
    const saved = typeof window !== "undefined" && localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        void open(JSON.parse(saved));
        return;
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
    void fetch("/api/views", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: emptyProject() }),
    })
      .then(() => open(emptyProject()))
      .catch(() => setError("API 에 연결할 수 없습니다. run_pne_scheduler_api.py 를 실행하십시오."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (project) localStorage.setItem(STORAGE_KEY, JSON.stringify(project));
  }, [project]);

  // --- editing ---------------------------------------------------------

  const apply = useCallback(
    async (action: string, args: Json = {}) => {
      if (!project) return;
      setBusy(true);
      setError("");
      try {
        const result: EditResult = await api.edit(action, project, args);
        undo.current = [...undo.current, { project, label: result.label }].slice(-UNDO_LIMIT);
        redo.current = [];
        setProject(result.project);
        setViews(result.views);
        setNotice(result.label || "");
        force((n) => n + 1);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [project],
  );

  const stepBack = useCallback(async () => {
    const entry = undo.current[undo.current.length - 1];
    if (!entry || !project) return;
    undo.current = undo.current.slice(0, -1);
    redo.current = [...redo.current, { project, label: entry.label }];
    setProject(entry.project);
    setNotice(`되돌림: ${entry.label}`);
    await refresh(entry.project);
    force((n) => n + 1);
  }, [project, refresh]);

  const stepForward = useCallback(async () => {
    const entry = redo.current[redo.current.length - 1];
    if (!entry || !project) return;
    redo.current = redo.current.slice(0, -1);
    undo.current = [...undo.current, { project, label: entry.label }];
    setProject(entry.project);
    setNotice(`다시 실행: ${entry.label}`);
    await refresh(entry.project);
    force((n) => n + 1);
  }, [project, refresh]);

  const select = useCallback(
    async (moduleId: string) => {
      setSelected(moduleId);
      if (project) await refresh(project, moduleId);
    },
    [project, refresh],
  );

  return {
    project,
    views,
    selected,
    busy,
    error,
    notice,
    canUndo: undo.current.length > 0,
    canRedo: redo.current.length > 0,
    undoLabel: undo.current[undo.current.length - 1]?.label ?? "",
    open,
    apply,
    undo: stepBack,
    redo: stepForward,
    select,
    setError,
  };
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
