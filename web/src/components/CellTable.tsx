"use client";

import { useEffect, useRef, useState } from "react";
import { api, type CellTableCheck, type Json } from "@/lib/api";

export function focusCell(row: number, field: string) {
  const target = document.getElementById(`batch-row-${row}-${field}`);
  target?.scrollIntoView({ block: "center", behavior: "smooth" });
  target?.focus({ preventScroll: true });
}

export function CellTable({ project, rows, onChange, disabled = false }: {
  project: Json; rows: Json[]; onChange: (rows: Json[]) => void; disabled?: boolean;
}) {
  const [paste, setPaste] = useState("");
  const [prefix, setPrefix] = useState("A");
  const [selected, setSelected] = useState<number[]>([]);
  const [check, setCheck] = useState<CellTableCheck | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const epoch = useRef(0);
  const context = useRef({ rows, project });
  context.current = { rows, project };
  useEffect(() => {
    const ticket = ++epoch.current;
    setCheck(null);
    const timer = setTimeout(() => {
      api.plan<CellTableCheck>("cellTable", project, { rows }).then((result) => {
        if (ticket === epoch.current) { setCheck(result); setError(""); }
      }).catch((reason: unknown) => { if (ticket === epoch.current) setError(String(reason)); });
    }, 180);
    return () => { clearTimeout(timer); ++epoch.current; };
  }, [rows, project]);
  const locked = disabled || working;
  async function action(name: string) {
    if (locked) return;
    const snapshot = context.current;
    ++epoch.current;
    setWorking(true); setError("");
    try {
      const result = await api.plan<CellTableCheck>("cellTable", project, { rows, action: name, text: paste, selected, prefix });
      if (snapshot.rows !== context.current.rows || snapshot.project !== context.current.project) return;
      onChange(result.inputRows); setSelected([]);
      if (name === "paste") setPaste("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setWorking(false); }
  }
  function update(index: number, key: string, value: string) {
    ++epoch.current;
    onChange(rows.map((row, i) => i === index ? { ...row, [key]: value } : row));
  }
  return <section className="cell-table-editor" aria-label="셀 목록 편집">
    <h3>셀 목록 표</h3>
    <p className="muted">기준용량은 직접 입력합니다. 1C 값은 입력 확인용이며 실제 최대 전류는 아래 미리보기에서 검토하세요.</p>
    <div className="action-row">
      <label>연번 접두어<input className="cell-prefix" aria-label="연번 접두어" value={prefix} disabled={locked} onChange={(e) => setPrefix(e.target.value)} /></label>
      <button type="button" disabled={locked || rows.length >= 100} onClick={() => void action("add")}>셀 추가</button>
      <button type="button" disabled={locked || !selected.length} onClick={() => void action("duplicate")}>선택 행 복사</button>
      <button type="button" disabled={locked || !selected.length} onClick={() => void action("number")}>선택 셀 연번</button>
      <button type="button" disabled={locked || !selected.length} onClick={() => void action("remove")}>선택 행 삭제</button>
    </div>
    <div className="batch-table-wrap"><table className="cell-input-table"><caption>셀 {rows.length}개 · 최대 100개</caption>
      <thead><tr><th><input type="checkbox" aria-label="모든 셀 선택" disabled={locked || !rows.length} checked={rows.length > 0 && selected.length === rows.length} onChange={(e) => setSelected(e.target.checked ? rows.map((_, i) => i) : [])} /></th><th>셀 ID</th><th>기준용량 (mAh)</th><th>1C (mA)</th><th>입력 확인</th></tr></thead>
      <tbody>{rows.map((row, index) => {
        const issues = check?.issues.filter((item) => item.row === index) ?? [];
        return <tr key={index}><td><input type="checkbox" aria-label={`${index + 1}행 선택`} disabled={locked} checked={selected.includes(index)} onChange={(e) => setSelected(e.target.checked ? [...selected, index] : selected.filter((i) => i !== index))} /></td>
          {["cellId", "referenceCapacityMah"].map((key) => <td key={key}><input id={`batch-row-${index}-${key}`} aria-label={`${index + 1}행 ${key === "cellId" ? "셀 ID" : "기준용량"}`} inputMode={key === "cellId" ? "text" : "decimal"} value={String(row[key] ?? "")} disabled={locked} aria-invalid={issues.some((issue) => issue.field === key) || undefined} aria-describedby={issues.length ? `cell-errors-${index}` : undefined} onChange={(e) => update(index, key, e.target.value)} /></td>)}
          <td>{check?.rows[index]?.oneCmA ?? "—"}</td><td id={`cell-errors-${index}`} className="cell-row-issues">{issues.map((issue) => issue.field === "extraColumns"
            ? <button id={`batch-row-${index}-extraColumns`} type="button" key={issue.field} disabled={locked} onClick={() => onChange(rows.map((item, i) => i === index ? { cellId: item.cellId, referenceCapacityMah: item.referenceCapacityMah } : item))}>{issue.message} · 추가 열 제거</button>
            : <button type="button" key={issue.field} className="issue-link" onClick={() => focusCell(index, issue.field)}>{issue.message} · 수정</button>)}</td></tr>;
      })}</tbody></table></div>
    {check?.issues.filter((issue) => issue.row === null).map((issue) => <p className="warn" key={issue.message}>{issue.message}</p>)}
    <details className="cell-paste"><summary>엑셀·텍스트에서 여러 셀 추가</summary>
      <label htmlFor="batch-cells">셀 목록 · 한 줄에 한 셀</label>
      <p className="muted">셀 ID와 기준용량 두 열을 복사하세요. 쉼표/탭 구분, 첫 헤더 행 지원. 기존 표 뒤에 추가합니다.</p>
      <textarea id="batch-cells" rows={4} value={paste} disabled={locked} onChange={(e) => setPaste(e.target.value)} placeholder={"A01\t80\nA02\t90"} />
      <button type="button" disabled={locked || !paste.trim()} onClick={() => void action("paste")}>표에 추가</button>
    </details>
    {error && <p role="alert" className="danger">{error}</p>}
  </section>;
}
