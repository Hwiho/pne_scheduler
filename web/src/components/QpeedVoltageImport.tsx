"use client";

import { useEffect, useRef, useState } from "react";
import type { Json } from "@/lib/api";

interface Candidate {
  id: string; row: number; voltageV: number; socPercent: number | null;
  socBasis: string; cellId: string; step: string; cycle: string;
}
interface Preview {
  ok: boolean; token: string; headers: string[]; mapping: Record<string, string>;
  candidates: Candidate[]; warnings: string[]; rowCount: number; invalidRows: number;
}
interface Props {
  project: Json; moduleId: string; disabled?: boolean;
  apply: (action: string, args?: Json) => Promise<void>;
  plan: <T>(action: string, args?: Json) => Promise<T>;
}

export function QpeedVoltageImport({ project, moduleId, disabled, apply, plan }: Props) {
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [useCapacity, setUseCapacity] = useState(false);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const epoch = useRef(0);
  const fileEpoch = useRef(0);
  useEffect(() => { epoch.current += 1; setPreview(null); setSelected(""); }, [project, moduleId]);
  useEffect(() => () => { epoch.current += 1; fileEpoch.current += 1; }, []);

  const args = () => ({ moduleId, text, fileName, mapping, useReferenceCapacity: useCapacity });
  const updateMapping = (key: string, value: string) => {
    epoch.current += 1;
    setMapping((current) => ({ ...current, [key]: value }));
    setPreview(null); setSelected("");
  };
  const readPreview = async () => {
    const request = ++epoch.current;
    setWorking(true); setError("");
    try {
      const result = await plan<Preview>("qpeedVoltage", args());
      if (request !== epoch.current) return;
      setPreview(result); setHeaders(result.headers); setMapping(result.mapping); setSelected("");
    } catch (reason) {
      if (request === epoch.current) setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setWorking(false); }
  };
  const candidate = preview?.candidates.find((row) => row.id === selected);
  const locked = disabled || working;

  return <details className="card qpeed-voltage-import" style={{ marginBottom: 10 }}>
    <summary>SOC setting 결과에서 전압 불러오기</summary>
    <p className="muted">CSV/TSV 파일을 읽고 셀·스텝의 끝 행을 직접 선택합니다. 전압으로 SOC를 자동 추정하지 않습니다. 적용하면 시작 SOC 맞춤 방식이 ‘측정 전압 기준’으로 바뀝니다.</p>
    <label>결과 파일 (CSV/TSV · 최대 2 MB)
      <input type="file" accept=".csv,.tsv,.txt" aria-label="SOC setting 결과 파일" disabled={locked} onChange={async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        const request = ++fileEpoch.current;
        epoch.current += 1;
        setPreview(null); setSelected(""); setError(""); setText(""); setHeaders([]); setMapping({});
        setFileName(file.name);
        if (file.size > 2 * 1024 * 1024) { setError("2 MB 이하로 결과를 내보내 주세요."); return; }
        setWorking(true);
        try {
          const bytes = await file.arrayBuffer();
          let decoded;
          try { decoded = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
          catch { decoded = new TextDecoder("euc-kr", { fatal: true }).decode(bytes); }
          if (request === fileEpoch.current) setText(decoded);
        } catch (reason) {
          if (request === fileEpoch.current) setError(reason instanceof Error ? reason.message : String(reason));
        } finally { if (request === fileEpoch.current) setWorking(false); }
      }} />
    </label>
    {fileName && <p className="muted">읽은 파일: {fileName}</p>}
    {headers.length > 0 && <div className="qpeed-import-mapping">
      {([["voltageColumn", "전압 열"], ["socColumn", "SOC 열 (선택)"], ["stepColumn", "스텝 열 (선택)"],
         ["cellColumn", "셀/채널 열 (선택)"], ["cycleColumn", "사이클 열 (선택)"],
         ["capacityColumn", "충전용량(mAh) 열 (선택)"]] as const).map(([key, label]) =>
        <label key={key}>{label}<select aria-label={label} value={mapping[key] ?? ""} disabled={locked}
          onChange={(event) => updateMapping(key, event.target.value)}>
          <option value="">선택 안 함</option>
          {headers.map((header) => <option key={header} value={header}>{header}</option>)}
        </select></label>)}
      <label>전압 데이터 단위<select aria-label="전압 데이터 단위" value={mapping.voltageUnit ?? ""} disabled={locked}
        onChange={(event) => updateMapping("voltageUnit", event.target.value)}>
        <option value="">단위 확인 필요</option><option value="V">V</option><option value="mV">mV</option>
      </select></label>
      <label>SOC 데이터 단위<select aria-label="SOC 데이터 단위" value={mapping.socUnit ?? ""} disabled={locked}
        onChange={(event) => updateMapping("socUnit", event.target.value)}>
        <option value="">단위 확인 필요</option><option value="%">0–100%</option><option value="fraction">0–1 비율</option>
      </select></label>
      <label className="qpeed-import-capacity"><input type="checkbox" aria-label="입력 기준용량으로 SOC 비율 계산" checked={useCapacity} disabled={locked}
        onChange={(event) => { epoch.current += 1; setUseCapacity(event.target.checked); setPreview(null); setSelected(""); }} />
        SOC 열이 없으면 충전용량(mAh) ÷ 입력 기준용량으로 명목 SOC 계산
      </label>
    </div>}
    <button type="button" disabled={!text || locked} onClick={() => void readPreview()}>전압 데이터 미리보기</button>
    {preview && <>
      <p className="muted">{preview.rowCount}행 · 제외 {preview.invalidRows}행 · 후보 {preview.candidates.length}개</p>
      <div className="warn" style={{ whiteSpace: "pre-line" }}>{preview.warnings.join("\n")}</div>
      {preview.candidates.length > 0 && <label>불러올 전압 행
        <select aria-label="불러올 전압 행" value={selected} disabled={locked} onChange={(event) => setSelected(event.target.value)}>
          <option value="">직접 선택하세요</option>
          {preview.candidates.map((row) => <option key={row.id} value={row.id}>
            {row.cellId || "셀 미지정"}{row.cycle ? " · 사이클 " + row.cycle : ""} · 스텝 {row.step || "미지정"} · {row.row}행 · {row.voltageV.toFixed(4)} V{row.socPercent === null ? "" : " · SOC " + row.socPercent.toFixed(2) + "%"}
          </option>)}
        </select>
      </label>}
      {candidate && <p>{candidate.voltageV.toFixed(4)} V · {candidate.socPercent === null ? "SOC 정보 없음" : candidate.socPercent.toFixed(2) + "% (" + candidate.socBasis + ")"} · 셀 {candidate.cellId || "미지정"}{candidate.cycle ? " / 사이클 " + candidate.cycle : ""} / 스텝 {candidate.step || "미지정"} / {candidate.row}행</p>}
      <button type="button" disabled={!candidate || locked} onClick={async () => {
        if (!candidate) return;
        setWorking(true); setError("");
        try { await apply("applyQpeedVoltage", { ...args(), token: preview.token, candidateId: candidate.id }); }
        catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
        finally { setWorking(false); }
      }}>선택 전압 적용</button>
    </>}
    {error && <p className="danger" role="alert">{error}</p>}
  </details>;
}
