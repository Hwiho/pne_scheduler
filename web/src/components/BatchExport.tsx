"use client";

import { useState } from "react";
import { api, type CellBatchPlan, type Json } from "@/lib/api";

function parseCells(text: string): Json[] {
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).filter((line, index) => {
    if (index > 0) return true;
    const first = line.split(/[,\t]/)[0].trim().toLowerCase().replace(/\s/g, "");
    return !["cellid", "cell_id", "셀id", "셀아이디"].includes(first);
  }).map((line) => {
    const columns = line.split(/[,\t]/).map((part) => part.trim());
    const [cellId = "", referenceCapacityMah = ""] = columns;
    return columns.length > 2
      ? { cellId, referenceCapacityMah, extraColumns: columns.length - 2 }
      : { cellId, referenceCapacityMah };
  });
}

export function BatchExport({ project }: { project: Json }) {
  const [phase, setPhase] = useState("formation");
  const [kind, setKind] = useState("preview");
  const [cellsText, setCellsText] = useState("");
  const [outDir, setOutDir] = useState("");
  const [preview, setPreview] = useState<CellBatchPlan | null>(null);
  const [paths, setPaths] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const args = (): Json => ({ phase, basis: "manual_reference", kind, rows: parseCells(cellsText) });

  async function plan() {
    setBusy(true);
    setError("");
    setPaths([]);
    try { setPreview(await api.planCellBatch(project, args())); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }

  async function generate() {
    if (!preview?.ok) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.exportCellBatch(project, args(), preview.token, outDir.trim());
      setPaths(result.paths);
      setPreview(null);
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }

  return <section className="card batch-export" aria-label="셀별 배치 생성">
    <span className="eyebrow">CELL BATCH</span>
    <h2>셀별 파일 일괄 생성</h2>
    <p className="muted">셀마다 사용할 기준용량(mAh)을 직접 입력하세요. 1C는 그 값과 같은 mA이며, 레시피의 C-rate 전류는 셀별로 다시 계산됩니다. 입력값은 수동·미검증으로 기록됩니다.</p>
    <div className="batch-controls">
      <label>실험 단계<select value={phase} onChange={(event) => { setPhase(event.target.value); setPreview(null); }}>
        <option value="formation">Formation</option><option value="derating">Derating</option><option value="cycle">Cycle / RPT</option>
      </select></label>
      <label>파일 종류<select value={kind} onChange={(event) => { setKind(event.target.value); setPreview(null); }}>
        <option value="preview">스텝 표·프로젝트 (장비 파일 아님)</option>
        <option value="review_candidate">PNE02 재열기 전용 SCH (실행 금지)</option>
      </select></label>
    </div>
    <label className="batch-data-label" htmlFor="batch-cells">셀 목록 · 한 줄에 한 셀</label>
    <p className="muted">한 줄에 셀 ID와 기준용량(mAh)을 입력하세요. 쉼표 또는 탭으로 구분합니다. 예: A01,80 → 1C = 80 mA</p>
    <textarea id="batch-cells" rows={5} value={cellsText} onChange={(event) => { setCellsText(event.target.value); setPreview(null); }} placeholder={"A01,80\nA02,82\nA03,79.5"} spellCheck={false} />
    <div className="batch-controls batch-output">
      <label>새 출력 폴더의 절대 경로<input value={outDir} onChange={(event) => setOutDir(event.target.value)} placeholder="예: C:\\PNE\\batch-01 또는 /tmp/pne-batch-01" /></label>
      <button type="button" disabled={busy || !cellsText.trim()} onClick={() => void plan()}>셀별 전류 미리보기</button>
      <button type="button" className="primary" disabled={busy || !preview?.ok || !outDir.trim()} onClick={() => void generate()}>일괄 생성</button>
    </div>
    {kind === "review_candidate" && <p className="warn">SCH 파일은 PNE02 재열기 확인용 후보만 생성합니다. 장비에 바로 실행하지 마세요.</p>}
    {error && <p className="danger" role="alert">{error}</p>}
    {preview && <div role="status" className="batch-preview">
      <strong>{preview.ok ? `${preview.rows.length}셀 생성 가능` : "입력 또는 레시피 확인 필요"}</strong>
      <p className="muted">{preview.note}</p>
      {preview.warnings.map((warning) => <p className="warn" key={warning}>{warning}</p>)}
      {preview.errors.map((issue) => <p className="danger" key={issue}>{issue}</p>)}
      <div className="batch-table-wrap"><table><thead><tr><th>셀</th><th>기준용량</th><th>1C</th><th>최대 전류</th><th>상태</th></tr></thead><tbody>
        {preview.rows.map((row, index) => <tr key={`${row.cellId}-${index}`}><td>{row.cellId || "—"}</td><td>{row.selectedCapacityMah ?? "—"} mAh</td><td>{row.oneCmA ?? "—"} mA</td><td>{row.maxCurrentmA} mA</td><td className={row.allowed ? "" : "danger"}>{row.allowed ? "준비됨" : row.blockers.join("; ")}</td></tr>)}
      </tbody></table></div>
    </div>}
    {paths.length > 0 && <p role="status" className="batch-success">{paths.length}개 파일을 새 폴더에 생성했습니다. 각 셀의 출처·해시는 batch-manifest.json에 기록했습니다.</p>}
  </section>;
}
