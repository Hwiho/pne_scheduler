"use client";

import { useEffect, useRef, useState } from "react";
import { api, type CellBatchPlan, type Json } from "@/lib/api";

const MAX_MATRIX_VARIANTS = 25;

type MatrixPreviewRow = CellBatchPlan["rows"][number] & {
  variantId?: string | null;
  chargeRate?: number | null;
  dischargeRate?: number | null;
  chargeCurrentmA?: number | null;
  dischargeCurrentmA?: number | null;
};

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

function parseRates(text: string, label: string): number[] {
  const normalized = text.trim();
  if (!normalized) throw new Error(`${label}을(를) 하나 이상 입력하세요.`);
  const groups = normalized.split(/[,;\r\n]/);
  if (groups.some((group) => !group.trim())) {
    throw new Error(`${label}에 비어 있는 값이 있습니다. 일부 값만 사용하지 않습니다.`);
  }
  const tokens = groups.flatMap((group) => group.trim().split(/\s+/));
  const rates = tokens.map((token) => Number(token));
  if (rates.some((rate) => !Number.isFinite(rate) || rate <= 0)) {
    throw new Error(`${label}은(는) 유한한 양수만 입력하세요. 일부 값만 사용하지 않습니다.`);
  }
  if (new Set(rates).size !== rates.length) throw new Error(`${label}에 중복 값이 있습니다.`);
  return rates;
}

export function BatchExport({ project }: { project: Json }) {
  const [phase, setPhase] = useState("formation");
  const [kind, setKind] = useState("preview");
  const [cellsText, setCellsText] = useState("");
  const [matrixEnabled, setMatrixEnabled] = useState(false);
  const [chargeRatesText, setChargeRatesText] = useState("0.5");
  const [dischargeRatesText, setDischargeRatesText] = useState("0.5");
  const [outDir, setOutDir] = useState("");
  const [preview, setPreview] = useState<CellBatchPlan | null>(null);
  const [paths, setPaths] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requestVersion = useRef(0);
  useEffect(() => {
    requestVersion.current += 1;
    setPreview(null);
    setPaths([]);
    setError("");
    setBusy(false);
  }, [project, phase, kind, cellsText, matrixEnabled, chargeRatesText, dischargeRatesText]);
  const args = (): Json => {
    const base: Json = { phase, basis: "manual_reference", kind, rows: parseCells(cellsText) };
    if (!matrixEnabled) return base;
    const chargeRates = parseRates(chargeRatesText, "충전 C-rate");
    const dischargeRates = parseRates(dischargeRatesText, "방전 C-rate");
    if (chargeRates.length * dischargeRates.length > MAX_MATRIX_VARIANTS) {
      throw new Error(`충전율×방전율 조합은 ${MAX_MATRIX_VARIANTS}개 이하여야 합니다.`);
    }
    return {
      ...base,
      matrix: chargeRates.flatMap((chargeRate) =>
        dischargeRates.map((dischargeRate) => ({ chargeRate, dischargeRate }))),
    };
  };

  async function plan() {
    const version = ++requestVersion.current;
    setBusy(true);
    setError("");
    setPaths([]);
    try {
      const result = await api.planCellBatch(project, args());
      if (version === requestVersion.current) setPreview(result);
    } catch (err) {
      if (version === requestVersion.current) setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (version === requestVersion.current) setBusy(false);
    }
  }

  async function generate() {
    if (!preview?.ok) return;
    const version = ++requestVersion.current;
    setBusy(true);
    setError("");
    try {
      const result = await api.exportCellBatch(project, args(), preview.token, outDir.trim());
      if (version === requestVersion.current) {
        setPaths(result.paths);
        setPreview(null);
      }
    } catch (err) {
      if (version === requestVersion.current) setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (version === requestVersion.current) setBusy(false);
    }
  }

  const hasMatrixPreview = Boolean(preview?.rows.some(
    (row) => (row as MatrixPreviewRow).variantId,
  ));
  const previewCells = new Set(preview?.rows.map((row) => row.cellId)).size;
  const previewVariants = new Set(preview?.rows.map((row) => (row as MatrixPreviewRow).variantId)).size;

  return <section className="card batch-export" aria-label="셀별 배치 생성">
    <div className="resource-heading">
      <div>
        <span className="eyebrow">CELL BATCH</span>
        <h2>셀별 파일 일괄 생성</h2>
        <p className="resource-description">셀별 기준용량으로 C-rate 전류를 다시 계산하고, 생성 전에 각 전류와 차단 사유를 검토합니다. 입력값은 수동·미검증으로 기록됩니다.</p>
      </div>
    </div>
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
    <div className="action-row"><button type="button" aria-expanded={matrixEnabled} onClick={() => { setMatrixEnabled((enabled) => !enabled); setPreview(null); setError(""); }}>
      {matrixEnabled ? "C-rate 조합 닫기" : "고급: C-rate 조합"}
    </button></div>
    {matrixEnabled && <div className="batch-controls">
      <label>충전 C-rate 목록<input value={chargeRatesText} onChange={(event) => { setChargeRatesText(event.target.value); setPreview(null); }} placeholder="예: 0.2, 0.5, 1" /></label>
      <label>방전 C-rate 목록<input value={dischargeRatesText} onChange={(event) => { setDischargeRatesText(event.target.value); setPreview(null); }} placeholder="예: 0.5, 1" /></label>
      <p className="muted">두 목록의 모든 조합을 셀마다 생성합니다. Formation, Cycle, In-situ의 선언된 충·방전율만 바뀌며 절대 전류(mA)는 그대로 유지됩니다.</p>
    </div>}
    <div className="batch-controls batch-output">
      <label>새 출력 폴더의 절대 경로<input value={outDir} onChange={(event) => setOutDir(event.target.value)} placeholder="예: C:\\PNE\\batch-01 또는 /tmp/pne-batch-01" /></label>
      <div className="action-row">
        <button type="button" disabled={busy || !cellsText.trim()} onClick={() => void plan()}>셀별 전류 미리보기</button>
        <button type="button" className="primary" disabled={busy || !preview?.ok || !outDir.trim()} onClick={() => void generate()}>일괄 생성</button>
      </div>
    </div>
    {kind === "review_candidate" && <p className="warn">SCH 파일은 PNE02 재열기 확인용 후보만 생성합니다. 장비에 바로 실행하지 마세요.</p>}
    {error && <p className="danger" role="alert">{error}</p>}
    {preview && <div role="status" className="batch-preview">
      <strong>{preview.ok ? hasMatrixPreview
        ? `${previewCells}셀 × ${previewVariants}조합 = ${preview.rows.length}개 파일 세트`
        : `${preview.rows.length}셀 생성 가능` : "입력 또는 레시피 확인 필요"}</strong>
      <p className="muted">{preview.note}</p>
      {preview.warnings.map((warning) => <p className="warn" key={warning}>{warning}</p>)}
      {preview.errors.map((issue) => <p className="danger" key={issue}>{issue}</p>)}
      <div className="batch-table-wrap"><table><thead><tr><th>셀</th>{hasMatrixPreview && <><th>조합</th><th>충전율 / 전류</th><th>방전율 / 전류</th></>}<th>기준용량</th><th>1C</th><th>실제 최대 전류</th><th>상태</th></tr></thead><tbody>
        {preview.rows.map((baseRow, index) => {
          const row = baseRow as MatrixPreviewRow;
          return <tr key={`${row.cellId}-${row.variantId ?? "default"}-${index}`}><td>{row.cellId || "—"}</td>{hasMatrixPreview && <><td>{row.variantId ?? "—"}</td><td>{row.chargeRate ?? "—"}C / {row.chargeCurrentmA ?? "—"} mA</td><td>{row.dischargeRate ?? "—"}C / {row.dischargeCurrentmA ?? "—"} mA</td></>}<td>{row.selectedCapacityMah ?? "—"} mAh</td><td>{row.oneCmA ?? "—"} mA</td><td>{row.maxCurrentmA ?? "—"} mA</td><td className={row.allowed ? "" : "danger"}>{row.allowed ? "준비됨" : row.blockers.join("; ")}</td></tr>;
        })}
      </tbody></table></div>
    </div>}
    {paths.length > 0 && <div role="status" className="batch-success status-note status-note-success"><span aria-hidden="true">✓</span><div><p>{paths.length}개 파일을 새 폴더에 생성했습니다. 각 셀의 출처·해시는 batch-manifest.json에 기록했습니다.</p><details><summary>생성된 파일 경로 보기</summary><ul className="file-output-list">{paths.map((path) => <li key={path}>{path}</li>)}</ul></details></div></div>}
  </section>;
}
