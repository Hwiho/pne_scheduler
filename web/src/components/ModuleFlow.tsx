"use client";

import { useRef, useState, type PointerEvent } from "react";
import type { Json, Views } from "@/lib/api";

interface ModuleFlowProps {
  views: Views;
  apply: (action: string, args?: Json) => Promise<void>;
  select: (moduleId: string) => Promise<void>;
  busy?: boolean;
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

/** The canvas edits the existing linear module order, which the server rewires. */
export function ModuleFlow({ views, apply, select, busy = false }: ModuleFlowProps) {
  const [insertAt, setInsertAt] = useState<number | null>(null);
  const [insertType, setInsertType] = useState("");
  const [dragging, setDragging] = useState("");
  const [dropAt, setDropAt] = useState<number | null>(null);
  const [dragPreview, setDragPreview] = useState<{ x: number; y: number; label: string } | null>(null);
  const [movingId, setMovingId] = useState("");
  const [menuId, setMenuId] = useState("");
  const canvasRef = useRef<HTMLDivElement>(null);
  const pointerDrag = useRef<FlowDrag | null>(null);
  const pointerTarget = useRef<number | null>(null);
  const suppressClick = useRef(false);
  const ids = views.modules.map((module) => module.moduleId);

  function nearestSlot(x: number, y: number): number | null {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const bounds = canvas.getBoundingClientRect();
    if (x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom) return null;
    let nearest: number | null = null;
    let distance = Infinity;
    for (const slot of canvas.querySelectorAll<HTMLElement>("[data-flow-slot]")) {
      const rect = slot.getBoundingClientRect();
      const next = Math.abs(x - (rect.left + rect.width / 2));
      if (next < distance) {
        distance = next;
        nearest = Number(slot.dataset.flowSlot);
      }
    }
    return nearest;
  }

  function startPointerDrag(
    event: PointerEvent<HTMLElement>, kind: FlowDrag["kind"], value: string, label: string,
  ) {
    if (busy || event.button !== 0) return;
    pointerDrag.current = {
      pointerId: event.pointerId, kind, value, label,
      startX: event.clientX, startY: event.clientY, active: false,
    };
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
      if (event.clientY >= bounds.top && event.clientY <= bounds.bottom) {
        if (event.clientX > bounds.right - 32) canvas.scrollLeft += 16;
        else if (event.clientX < bounds.left + 32) canvas.scrollLeft -= 16;
      }
    }
    pointerTarget.current = nearestSlot(event.clientX, event.clientY);
    setDropAt(pointerTarget.current);
  }

  function endPointerDrag(event: PointerEvent<HTMLElement>, cancelled = false) {
    const drag = pointerDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
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
    if (drag.kind === "palette") insert(drag.value, target);
    else moveTo(drag.value, target);
  }

  function insert(moduleType: string, index: number) {
    if (!moduleType || busy) return;
    setInsertAt(null);
    setInsertType("");
    setMovingId("");
    void apply("addModule", { moduleType, index });
  }

  function moveTo(moduleId: string, index: number) {
    if (busy) return;
    setMovingId("");
    const from = ids.indexOf(moduleId);
    if (from < 0) return;
    const order = [...ids];
    order.splice(from, 1);
    order.splice(index > from ? index - 1 : index, 0, moduleId);
    if (order.some((id, position) => id !== ids[position])) {
      void apply("reorder", { order });
    }
  }

  function slot(index: number) {
    return (
      <div
        key={`slot-${index}`}
        data-flow-slot={index}
        className={`flow-slot${dropAt === index ? " flow-slot-active" : ""}${movingId || dragging ? " flow-slot-ready" : ""}`}
      >
        <span className="flow-connector" aria-hidden="true" />
        <button
          type="button"
          className="flow-insert-trigger"
          aria-label={movingId ? `선택한 모듈을 ${index + 1}번째 위치로 연결` : `${index + 1}번째 위치에 모듈 삽입`}
          aria-expanded={!movingId && insertAt === index}
          disabled={busy}
          onClick={() => {
            if (movingId) moveTo(movingId, index);
            else { setInsertAt(index); setInsertType(""); }
          }}
          title={movingId ? "여기로 연결" : "이 위치에 모듈 삽입"}
        >{movingId ? "↳" : "+"}
        </button>
      </div>
    );
  }

  return (
    <section className="card flow-builder" aria-label="모듈 연결 편집기">
      <div className="flow-heading">
        <div>
          <span className="eyebrow">METHOD FLOW</span>
          <h2>모듈 연결</h2>
          <p className="muted">팔레트 모듈을 끌어 놓거나 연결점의 +로 사이에 삽입하세요. 박스 윗부분을 끌거나 ‘연결’ 버튼으로 순서를 바꿀 수 있습니다.</p>
        </div>
        <span className="flow-count">{views.modules.length}개 모듈 · {views.procedure.stepCount}스텝</span>
      </div>

      <div className="flow-workspace">
        <aside className="flow-palette" aria-label="추가할 모듈">
          <h3>모듈 팔레트</h3>
          <div className="flow-palette-list">
            {views.palette.map((item) => (
              <button
                key={item.moduleType}
                type="button"
                className="flow-palette-item"
                disabled={busy}
                onPointerDown={(event) => startPointerDrag(event, "palette", item.moduleType, item.title)}
                onPointerMove={movePointerDrag}
                onPointerUp={endPointerDrag}
                onPointerCancel={(event) => endPointerDrag(event, true)}
                onClick={() => {
                  if (suppressClick.current) { suppressClick.current = false; return; }
                  insert(item.moduleType, ids.length);
                }}
                title={`${item.title} — 클릭: 끝에 추가 / 끌기: 원하는 위치에 삽입`}
              >
                <span>{item.title}</span>
                <small>{item.category || "실험 모듈"}</small>
              </button>
            ))}
          </div>
        </aside>

        <div className="flow-lane">
          <div className="flow-lane-label">{movingId || dragging ? "연결할 위치를 선택하세요" : "실행 순서"} <span>← 좌우로 스크롤 →</span></div>
          <div ref={canvasRef} className="flow-canvas" role="group" aria-label="모듈 실행 흐름">
            <div className="flow-track">
              <div className="flow-terminal flow-start"><span>START</span><strong>실험 시작</strong></div>
              {views.modules.map((module, index) => (
                <div className="flow-segment" key={module.moduleId}>
                  {slot(index)}
                  <article
                    className={`flow-node${module.moduleId === views.selectedModule ? " flow-node-selected" : ""}${module.error ? " flow-node-error" : ""}`}
                  >
                    <div
                      className="flow-node-top"
                      title="끌어서 실행 순서 변경"
                      onPointerDown={(event) => startPointerDrag(event, "module", module.moduleId, module.title)}
                      onPointerMove={movePointerDrag}
                      onPointerUp={endPointerDrag}
                      onPointerCancel={(event) => endPointerDrag(event, true)}
                    ><span>STEP {String(module.position).padStart(2, "0")}</span><span className="flow-node-grip" aria-hidden="true">끌기 <b>⠿</b></span></div>
                    <button
                      type="button"
                      className="flow-node-select"
                      aria-pressed={module.moduleId === views.selectedModule}
                      disabled={busy}
                      onClick={() => void select(module.moduleId)}
                    >
                      <strong>{module.title}</strong>
                      <span>{module.subtitle || module.moduleType}</span>
                    </button>
                    <div className="flow-node-meta"><span>{module.steps}스텝</span><span>{module.duration}</span></div>
                    {module.error && <div className="flow-node-warning" title={module.error}>조건 확인 필요</div>}
                    <div className="flow-node-actions">
                      <button type="button" disabled={busy || index === 0} aria-label={`${module.title} 앞으로 이동`} onClick={() => void apply("move", { moduleId: module.moduleId, delta: -1 })}>←</button>
                      <button type="button" disabled={busy || index === ids.length - 1} aria-label={`${module.title} 뒤로 이동`} onClick={() => void apply("move", { moduleId: module.moduleId, delta: 1 })}>→</button>
                      <button type="button" disabled={busy} aria-pressed={movingId === module.moduleId} onClick={() => { setMovingId(movingId === module.moduleId ? "" : module.moduleId); setInsertAt(null); }}>{movingId === module.moduleId ? "취소" : "연결"}</button>
                      <button type="button" disabled={busy} onClick={() => void select(module.moduleId)}>조건 편집</button>
                      <button type="button" disabled={busy} aria-label={`${module.title} 추가 작업`} aria-expanded={menuId === module.moduleId} onClick={() => setMenuId(menuId === module.moduleId ? "" : module.moduleId)}>⋯</button>
                    </div>
                    {menuId === module.moduleId && <div className="flow-node-menu">
                      <button type="button" disabled={busy} onClick={() => { setMenuId(""); void apply("duplicateModule", { moduleId: module.moduleId }); }}>이 박스 복제</button>
                      <button type="button" disabled={busy} className="danger" onClick={() => {
                        if (!window.confirm(`${module.title} 박스를 삭제할까요? 되돌리기로 복구할 수 있습니다.`)) return;
                        setMenuId("");
                        void apply("removeModule", { moduleId: module.moduleId });
                      }}>이 박스 삭제</button>
                    </div>}
                  </article>
                </div>
              ))}
              {slot(ids.length)}
              <div className="flow-terminal flow-end"><span>END</span><strong>실험 종료</strong></div>
            </div>
          </div>
          {views.modules.length === 0 && <p className="flow-empty muted">모듈을 추가하면 START와 END 사이에 연결됩니다.</p>}
          {insertAt !== null && (
            <div className="flow-insert-editor">
              <label htmlFor="flow-insert-type">{insertAt + 1}번째 위치에 삽입</label>
              <select id="flow-insert-type" value={insertType} onChange={(event) => setInsertType(event.target.value)}>
                <option value="">모듈 선택</option>
                {views.palette.map((item) => <option value={item.moduleType} key={item.moduleType}>{item.title}</option>)}
              </select>
              <button type="button" className="primary" disabled={busy || !insertType} onClick={() => insert(insertType, insertAt)}>삽입</button>
              <button type="button" onClick={() => setInsertAt(null)}>취소</button>
            </div>
          )}
        </div>
      </div>
      {dragPreview && <div className="flow-drag-preview" style={{ left: dragPreview.x + 14, top: dragPreview.y + 14 }} aria-hidden="true">{dragPreview.label} → 연결점</div>}
    </section>
  );
}
