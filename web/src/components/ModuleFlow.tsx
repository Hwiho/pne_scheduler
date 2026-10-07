"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import type { Json, Views } from "@/lib/api";
import { ModuleContents } from "./ModuleContents";

interface ModuleFlowProps {
  views: Views;
  project: Json;
  apply: (action: string, args?: Json) => Promise<void>;
  select: (moduleId: string) => Promise<void>;
  onEdit?: (moduleId: string) => void;
  busy?: boolean;
}

interface PaletteEntry {
  key: string;
  moduleType: string;
  title: string;
  description: string;
  params?: Json;
  kind: "basic" | "preset";
  category?: string;
}

interface FlowDrag {
  pointerId: number;
  kind: "module" | "palette";
  value: string;
  label: string;
  startX: number;
  startY: number;
  active: boolean;
}

const BASIC_STEPS: PaletteEntry[] = [
  { key: "primitive:cc_charge", moduleType: "primitive", title: "CC 충전", description: "정전류 충전", params: { kind: "cc_charge" }, kind: "basic" },
  { key: "primitive:cccv_charge", moduleType: "primitive", title: "CCCV 충전", description: "정전류·정전압 충전", params: { kind: "cccv_charge" }, kind: "basic" },
  { key: "primitive:cc_discharge", moduleType: "primitive", title: "CC 방전", description: "정전류 방전", params: { kind: "cc_discharge" }, kind: "basic" },
  { key: "primitive:rest", moduleType: "primitive", title: "휴지", description: "지정 시간 휴지", params: { kind: "rest" }, kind: "basic" },
  { key: "primitive:ocv", moduleType: "primitive", title: "OCV", description: "개방전압 측정", params: { kind: "ocv" }, kind: "basic" },
];

/** Linear method editor. Server actions remain the only source of project mutations. */
export function ModuleFlow({ views, project, apply, select, onEdit, busy = false }: ModuleFlowProps) {
  const [insertAt, setInsertAt] = useState<number | null>(null);
  const [insertKey, setInsertKey] = useState("");
  const [dragging, setDragging] = useState("");
  const [dropAt, setDropAt] = useState<number | null>(null);
  const [dragPreview, setDragPreview] = useState<{ x: number; y: number; label: string } | null>(null);
  const [movingId, setMovingId] = useState("");
  const [menuId, setMenuId] = useState("");
  const [paletteQuery, setPaletteQuery] = useState("");
  const [groupSelection, setGroupSelection] = useState<string[]>([]);
  const [groupName, setGroupName] = useState("내 모듈");
  const [repeatCount, setRepeatCount] = useState("1");
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [maximizedId, setMaximizedId] = useState("");
  const canvasRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const maximizeButtons = useRef(new Map<string, HTMLButtonElement>());
  const pointerDrag = useRef<FlowDrag | null>(null);
  const pointerTarget = useRef<number | null>(null);
  const suppressClick = useRef(false);
  const ids = views.modules.map((module) => module.moduleId);

  const paletteEntries = useMemo<PaletteEntry[]>(() => [
    ...BASIC_STEPS,
    ...views.palette
      .filter((item) => !["primitive", "rest"].includes(item.moduleType))
      .map((item) => ({
        key: `module:${item.moduleType}`,
        moduleType: item.moduleType,
        title: item.title,
        description: item.description,
        category: item.category,
        kind: "preset" as const,
      })),
  ], [views.palette]);

  const entryByKey = useMemo(() => new Map(paletteEntries.map((entry) => [entry.key, entry])), [paletteEntries]);
  const filteredPalette = useMemo(() => {
    const query = paletteQuery.trim().toLocaleLowerCase("ko");
    if (!query) return paletteEntries;
    return paletteEntries.filter((entry) => [entry.title, entry.description, entry.category, entry.moduleType]
      .join(" ").toLocaleLowerCase("ko").includes(query));
  }, [paletteEntries, paletteQuery]);
  const basicEntries = filteredPalette.filter((entry) => entry.kind === "basic");
  const presetEntries = filteredPalette.filter((entry) => entry.kind === "preset");
  const maximizedModule = views.modules.find((module) => module.moduleId === maximizedId);

  useEffect(() => {
    setGroupSelection((selected) => selected.filter((id) => ids.includes(id)));
    setExpandedIds((selected) => selected.filter((id) => ids.includes(id)));
    if (maximizedId && !ids.includes(maximizedId)) setMaximizedId("");
  }, [views.modules]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!maximizedId || !dialog) return;
    if (!dialog.open) dialog.showModal();
    window.requestAnimationFrame(() => dialog.querySelector<HTMLButtonElement>("[data-dialog-close]")?.focus());
  }, [maximizedId]);

  function closeMaximized() {
    const restoreTo = maximizedId;
    if (dialogRef.current?.open) dialogRef.current.close();
    setMaximizedId("");
    window.requestAnimationFrame(() => maximizeButtons.current.get(restoreTo)?.focus());
  }

  function nearestSlot(x: number, y: number): number | null {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const bounds = canvas.getBoundingClientRect();
    if (x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom) return null;
    let nearest: number | null = null;
    let distance = Infinity;
    for (const slot of canvas.querySelectorAll<HTMLElement>("[data-flow-slot]")) {
      const rect = slot.getBoundingClientRect();
      const next = Math.abs(y - (rect.top + rect.height / 2));
      if (next < distance) {
        distance = next;
        nearest = Number(slot.dataset.flowSlot);
      }
    }
    return nearest;
  }

  function startPointerDrag(event: PointerEvent<HTMLElement>, kind: FlowDrag["kind"], value: string, label: string) {
    if (busy || event.button !== 0) return;
    pointerDrag.current = { pointerId: event.pointerId, kind, value, label, startX: event.clientX, startY: event.clientY, active: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function movePointerDrag(event: PointerEvent<HTMLElement>) {
    const drag = pointerDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (!drag.active && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 8) return;
    drag.active = true;
    event.preventDefault();
    setDragging(`${drag.kind}:${drag.value}`);
    setDragPreview({ x: event.clientX, y: event.clientY, label: drag.label });
    const canvas = canvasRef.current;
    if (canvas) {
      const bounds = canvas.getBoundingClientRect();
      if (event.clientX >= bounds.left && event.clientX <= bounds.right) {
        if (event.clientY > bounds.bottom - 42) canvas.scrollTop += 18;
        else if (event.clientY < bounds.top + 42) canvas.scrollTop -= 18;
      }
    }
    pointerTarget.current = nearestSlot(event.clientX, event.clientY);
    setDropAt(pointerTarget.current);
  }

  function endPointerDrag(event: PointerEvent<HTMLElement>, cancelled = false) {
    const drag = pointerDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    const target = pointerTarget.current;
    pointerDrag.current = null;
    pointerTarget.current = null;
    setDragging("");
    setDropAt(null);
    setDragPreview(null);
    if (!drag.active) return;
    event.preventDefault();
    suppressClick.current = true;
    window.setTimeout(() => { suppressClick.current = false; }, 0);
    if (cancelled || target === null) return;
    if (drag.kind === "palette") {
      const entry = entryByKey.get(drag.value);
      if (entry) insert(entry, target);
    } else moveTo(drag.value, target);
  }

  function insert(entry: PaletteEntry, index: number) {
    if (busy) return;
    setInsertAt(null);
    setInsertKey("");
    setMovingId("");
    void apply("addModule", { moduleType: entry.moduleType, ...(entry.params ? { params: entry.params } : {}), index });
  }

  function moveTo(moduleId: string, index: number) {
    if (busy) return;
    setMovingId("");
    const from = ids.indexOf(moduleId);
    if (from < 0) return;
    const order = [...ids];
    order.splice(from, 1);
    order.splice(index > from ? index - 1 : index, 0, moduleId);
    if (order.some((id, position) => id !== ids[position])) void apply("reorder", { order });
  }

  function toggleGroupSelection(moduleId: string, shiftKey: boolean) {
    const index = ids.indexOf(moduleId);
    if (index < 0 || views.modules[index]?.moduleType === "sequence") return;
    setGroupSelection((selected) => {
      if (shiftKey && selected.length) {
        const anchor = ids.indexOf(selected[selected.length - 1]);
        const [start, end] = anchor < index ? [anchor, index] : [index, anchor];
        const range = views.modules.slice(start, end + 1);
        return range.some((module) => module.moduleType === "sequence") ? [moduleId] : range.map((module) => module.moduleId);
      }
      const positions = selected.map((id) => ids.indexOf(id)).sort((a, b) => a - b);
      if (!selected.includes(moduleId)) {
        if (!positions.length || index === positions[0] - 1 || index === positions[positions.length - 1] + 1) return [...selected, moduleId].sort((a, b) => ids.indexOf(a) - ids.indexOf(b));
        return [moduleId];
      }
      if (positions.length === 1) return [];
      if (index === positions[0] || index === positions[positions.length - 1]) return selected.filter((id) => id !== moduleId);
      return [moduleId];
    });
  }

  async function createGroup() {
    const count = Number(repeatCount);
    if (busy || groupSelection.length < 2 || !groupName.trim() || !Number.isInteger(count) || count < 1 || count > 10000) return;
    await apply("groupModules", { moduleIds: groupSelection, name: groupName.trim(), repeatCount: count });
    setGroupSelection([]);
  }

  function openEditor(moduleId: string) {
    void select(moduleId).then(() => onEdit?.(moduleId));
  }

  function ungroup(moduleId: string) {
    if (!window.confirm("그룹을 해제하면 반복 횟수만큼 박스를 풀어 놓습니다. 계속할까요?")) return;
    setMenuId("");
    void apply("ungroupModule", { moduleId });
  }

  function slot(index: number) {
    return (
      <div key={`slot-${index}`} data-flow-slot={index} className={`flow-slot${dropAt === index ? " flow-slot-active" : ""}${movingId || dragging ? " flow-slot-ready" : ""}`}>
        <span className="flow-connector" aria-hidden="true" />
        <button type="button" className="flow-insert-trigger" aria-label={movingId ? `선택한 모듈을 ${index + 1}번째 위치로 이동` : `${index + 1}번째 위치에 모듈 삽입`} aria-expanded={!movingId && insertAt === index} disabled={busy} onClick={() => movingId ? moveTo(movingId, index) : (setInsertAt(index), setInsertKey(""))} title={movingId ? "여기로 이동" : "이 위치에 모듈 삽입"}>{movingId ? "↳" : "+"}</button>
      </div>
    );
  }

  function paletteButton(entry: PaletteEntry) {
    return (
      <button key={entry.key} type="button" className={`flow-palette-item flow-palette-${entry.kind}`} data-module-type={entry.moduleType} disabled={busy} onPointerDown={(event) => startPointerDrag(event, "palette", entry.key, entry.title)} onPointerMove={movePointerDrag} onPointerUp={endPointerDrag} onPointerCancel={(event) => endPointerDrag(event, true)} onClick={() => {
        if (suppressClick.current) { suppressClick.current = false; return; }
        insert(entry, ids.length);
      }} title={`${entry.description} — 클릭: 끝에 추가 / 끌기: 원하는 위치에 삽입`}>
        <span>{entry.title}</span><small>{entry.description}</small>{entry.kind === "preset" && <b>PRESET</b>}
      </button>
    );
  }

  return (
    <section className="card flow-builder" aria-label="모듈 연결 편집기">
      <div className="flow-heading">
        <div><span className="eyebrow">METHOD FLOW</span><h2>모듈 연결</h2><p className="muted">기본 스텝과 실험 프리셋을 같은 흐름에 놓고, 연속된 박스를 재사용 가능한 내 모듈로 묶을 수 있습니다.</p></div>
        <span className="flow-count">{views.modules.length}개 모듈 · {views.procedure.stepCount}스텝</span>
      </div>

      <div className="flow-workspace">
        <aside className="flow-palette" aria-label="추가할 모듈">
          <div className="flow-palette-heading"><h3>모듈 팔레트</h3><span>{paletteEntries.length}개</span></div>
          <label className="flow-search"><span className="flow-sr-only">모듈 검색</span><input type="search" value={paletteQuery} onChange={(event) => setPaletteQuery(event.target.value)} placeholder="스텝·프리셋 검색" /></label>
          <div className="flow-palette-list">
            <section className="flow-palette-group"><h4>Basic steps <span>{basicEntries.length}</span></h4><p>한 개씩 조합하는 기본 박스</p><div className="flow-palette-items">{basicEntries.map(paletteButton)}</div></section>
            <section className="flow-palette-group flow-palette-presets"><h4>Experiment presets <span>{presetEntries.length}</span></h4><p>Formation · Cycle Life · QPEED 등</p><div className="flow-palette-items">{presetEntries.map(paletteButton)}</div></section>
            {filteredPalette.length === 0 && <p className="flow-palette-empty">검색 결과가 없습니다.</p>}
          </div>
        </aside>

        <div className="flow-lane">
          <div className="flow-lane-label">{movingId || dragging ? "이동할 위치를 선택하세요" : "실행 순서"}<span>위에서 아래로 실행</span></div>
          {groupSelection.length > 0 && <div className="flow-group-editor" role="group" aria-label="선택한 모듈 그룹 만들기">
            <div><strong>{groupSelection.length}개 연속 선택</strong><span>Shift+클릭으로 범위를 빠르게 고를 수 있습니다.</span></div>
            <label>이름<input value={groupName} onChange={(event) => setGroupName(event.target.value)} /></label>
            <label>반복<input type="number" min="1" max="10000" step="1" value={repeatCount} onChange={(event) => setRepeatCount(event.target.value)} /></label>
            <button type="button" className="primary" disabled={busy || groupSelection.length < 2 || !groupName.trim() || !Number.isInteger(Number(repeatCount)) || Number(repeatCount) < 1 || Number(repeatCount) > 10000} onClick={createGroup}>내 모듈 만들기</button>
            <button type="button" onClick={() => setGroupSelection([])}>선택 해제</button>
          </div>}

          <div ref={canvasRef} className="flow-canvas" role="group" aria-label="모듈 실행 흐름"><div className="flow-track">
            <div className="flow-terminal flow-start"><span>START</span><strong>실험 시작</strong></div>
            {views.modules.map((module, index) => {
              const grouped = module.moduleType === "sequence";
              const custom = module.moduleType === "custom_steps";
              const expanded = expandedIds.includes(module.moduleId);
              const expandable = grouped || custom || module.steps > 1;
              const selected = module.moduleId === views.selectedModule;
              return <div className="flow-segment" key={module.moduleId}>
                {slot(index)}
                <article data-module-type={module.moduleType} className={`flow-node${selected ? " flow-node-selected" : ""}${groupSelection.includes(module.moduleId) ? " flow-node-group-selected" : ""}${grouped ? " flow-node-group" : ""}${expanded ? " flow-node-expanded" : ""}${module.error ? " flow-node-error" : ""}`}>
                  <div className="flow-node-top">
                    <span className="flow-node-drag" title="끌어서 실행 순서 변경" onPointerDown={(event) => startPointerDrag(event, "module", module.moduleId, module.title)} onPointerMove={movePointerDrag} onPointerUp={endPointerDrag} onPointerCancel={(event) => endPointerDrag(event, true)}>STEP {String(module.position).padStart(2, "0")} <b aria-hidden="true">⠿</b></span>
                    <div className="flow-node-tools">
                      <button type="button" disabled={busy || index === 0} aria-label={`${module.title} 앞으로 이동`} title="앞으로 이동" onClick={() => void apply("move", { moduleId: module.moduleId, delta: -1 })}>↑</button>
                      <button type="button" disabled={busy || index === ids.length - 1} aria-label={`${module.title} 뒤로 이동`} title="뒤로 이동" onClick={() => void apply("move", { moduleId: module.moduleId, delta: 1 })}>↓</button>
                      <button type="button" disabled={busy} aria-label={`${module.title} 조건 편집`} title="조건 편집" onClick={() => openEditor(module.moduleId)}>편집</button>
                      <button type="button" disabled={busy} aria-label={`${module.title} 추가 작업`} aria-expanded={menuId === module.moduleId} title="추가 작업" onClick={() => setMenuId(menuId === module.moduleId ? "" : module.moduleId)}>⋯</button>
                    </div>
                  </div>
                  <div className="flow-node-main">
                    <button type="button" className="flow-group-check" aria-label={grouped ? `${module.title} 그룹은 중첩 선택할 수 없음` : `${module.title} 그룹 선택`} aria-pressed={groupSelection.includes(module.moduleId)} disabled={busy || grouped} onClick={(event) => toggleGroupSelection(module.moduleId, event.shiftKey)} title={grouped ? "사용자 그룹은 중첩할 수 없습니다" : "연속된 박스를 선택해 내 모듈 만들기"}>{groupSelection.includes(module.moduleId) ? "✓" : ""}</button>
                    <button type="button" className="flow-node-select" aria-pressed={selected} disabled={busy} onClick={() => void select(module.moduleId)}>
                      <span className="flow-node-kind">{grouped ? "내 모듈" : custom ? "개별 스텝" : module.moduleType === "primitive" ? "기본 스텝" : "PRESET"}</span><strong>{module.title}</strong><span>{module.subtitle || module.moduleType}</span>
                    </button>
                    <div className="flow-node-summary"><b>{module.steps}</b><span>스텝</span><b>{module.duration}</b><span>예상</span></div>
                    {expandable && <div className="flow-node-view-actions">
                      <button type="button" aria-expanded={expanded} onClick={() => setExpandedIds((open) => open.includes(module.moduleId) ? open.filter((id) => id !== module.moduleId) : [...open, module.moduleId])}>{expanded ? "구성 접기" : "구성 펼치기"}<span aria-hidden="true">{expanded ? "▴" : "▾"}</span></button>
                      <button type="button" ref={(element) => { if (element) maximizeButtons.current.set(module.moduleId, element); else maximizeButtons.current.delete(module.moduleId); }} onClick={() => { void select(module.moduleId); setMaximizedId(module.moduleId); }}>크게 보기</button>
                    </div>}
                  </div>
                  {module.error && <div className="flow-node-warning" title={module.error}>조건 확인 필요</div>}
                  {menuId === module.moduleId && <div className="flow-node-menu">
                    <button type="button" disabled={busy} aria-pressed={movingId === module.moduleId} onClick={() => { setMovingId(movingId === module.moduleId ? "" : module.moduleId); setInsertAt(null); }}>{movingId === module.moduleId ? "이동 취소" : "위치 이동"}</button>
                    {grouped && <button type="button" disabled={busy} onClick={() => ungroup(module.moduleId)}>그룹 해제</button>}
                    <button type="button" disabled={busy} onClick={() => { setMenuId(""); void apply("duplicateModule", { moduleId: module.moduleId }); }}>복제</button>
                    <button type="button" disabled={busy} className="danger" onClick={() => { if (!window.confirm(`${module.title} 박스를 삭제할까요? 되돌리기로 복구할 수 있습니다.`)) return; setMenuId(""); void apply("removeModule", { moduleId: module.moduleId }); }}>삭제</button>
                  </div>}
                  {expanded && maximizedId !== module.moduleId && <div className="flow-node-contents"><ModuleContents project={project} moduleId={module.moduleId} apply={apply} cRatePresets={views.cRatePresets} busy={busy} /></div>}
                </article>
              </div>;
            })}
            {slot(ids.length)}
            <div className="flow-terminal flow-end"><span>END</span><strong>실험 종료</strong></div>
          </div></div>
          {views.modules.length === 0 && <p className="flow-empty muted">기본 스텝이나 실험 프리셋을 추가하면 START와 END 사이에 연결됩니다.</p>}
          {insertAt !== null && <div className="flow-insert-editor">
            <label htmlFor="flow-insert-type">{insertAt + 1}번째 위치에 삽입</label>
            <select id="flow-insert-type" value={insertKey} onChange={(event) => setInsertKey(event.target.value)}><option value="">모듈 선택</option><optgroup label="Basic steps">{BASIC_STEPS.map((entry) => <option value={entry.key} key={entry.key}>{entry.title}</option>)}</optgroup><optgroup label="Experiment presets">{paletteEntries.filter((entry) => entry.kind === "preset").map((entry) => <option value={entry.key} key={entry.key}>{entry.title} · PRESET</option>)}</optgroup></select>
            <button type="button" className="primary" disabled={busy || !entryByKey.has(insertKey)} onClick={() => { const entry = entryByKey.get(insertKey); if (entry) insert(entry, insertAt); }}>삽입</button><button type="button" onClick={() => setInsertAt(null)}>취소</button>
          </div>}
        </div>
      </div>

      {maximizedModule && <dialog ref={dialogRef} className="flow-max-dialog" aria-labelledby="flow-max-title" onCancel={(event) => { event.preventDefault(); closeMaximized(); }}>
        <div className="flow-max-heading"><div><span>{maximizedModule.moduleType === "sequence" ? "내 모듈" : "MODULE CONTENTS"}</span><h2 id="flow-max-title">{maximizedModule.title}</h2><p>{maximizedModule.steps}스텝 · {maximizedModule.duration}</p></div><button type="button" data-dialog-close onClick={closeMaximized} aria-label="크게 보기 닫기">닫기 ×</button></div>
        <div className="flow-max-body"><ModuleContents project={project} moduleId={maximizedModule.moduleId} apply={apply} cRatePresets={views.cRatePresets} busy={busy} /></div>
      </dialog>}
      {dragPreview && <div className="flow-drag-preview" style={{ left: dragPreview.x + 14, top: dragPreview.y + 14 }} aria-hidden="true">{dragPreview.label} → 연결점</div>}
    </section>
  );
}
