"use client";

import { useState } from "react";
import { api, type ImportInfo, type ImportPatchResult, type ImportProposal } from "@/lib/api";

export function ImportTab() {
  const [path, setPath] = useState("");
  const [info, setInfo] = useState<ImportInfo | null>(null);
  const [proposal, setProposal] = useState<ImportProposal | null>(null);
  const [stepNo, setStepNo] = useState("1");
  const [field, setField] = useState("");
  const [value, setValue] = useState("");
  const [outputPath, setOutputPath] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [result, setResult] = useState<ImportPatchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const explanationParts = info?.explanation.split("\n\n") ?? [];

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="col">
      <div className="card">
        <h2>기존 SCH 열기</h2>
        <p className="muted">API가 실행 중인 PC의 .sch 파일 절대 경로를 입력하세요.</p>
        <form className="row import-path" onSubmit={(event) => {
          event.preventDefault();
          void run(async () => {
            setInfo(null);
            setProposal(null);
            setResult(null);
            setAcknowledged(false);
            const opened = await api.openImport(path.trim());
            setInfo(opened);
            setField(opened.editableFields[0]?.name ?? "");
            setOutputPath(opened.path.replace(/\.sch$/i, "_patched.sch"));
          });
        }}>
          <input className="grow" aria-label="SCH 파일 경로" value={path} onChange={(event) => setPath(event.target.value)} placeholder="/path/to/schedule.sch" />
          <button type="submit" disabled={busy || !path.trim()}>열기</button>
        </form>
        {error && <p className="danger" role="alert">{error}</p>}
      </div>

      {info && <>
        <div className="card">
          <h2 className="import-file">{info.path.split(/[\\/]/).pop()}</h2>
          <p className="muted import-file">{info.path}</p>
          <p className="muted">{info.schVersion} · {info.stepCount}스텝 · SHA-256 {info.sha256.slice(0, 12)}…</p>
          <div className="analysis-overview">
            <span className="stage-pill">분석용 추정</span>
            <p className="analysis-lead">{explanationParts[1] ?? explanationParts[0]}</p>
            <details>
              <summary>단계별 설명과 근거 보기</summary>
              <div className="analysis-copy">{[explanationParts[0], ...explanationParts.slice(2)].join("\n\n")}</div>
            </details>
          </div>
        </div>

        <div className="card">
          <h2>원본 바이트를 보존하는 편집</h2>
          {info.editableFields.length === 0 ? (
            <p className="warn import-note">이 SCH 형식은 쓰기 검증 근거가 없어 편집할 수 없습니다. 설명과 검토는 계속 사용할 수 있습니다.</p>
          ) : <>
            <form className="import-editor" onSubmit={(event) => {
              event.preventDefault();
              const step = Number(stepNo);
              const numericValue = Number(value);
              if (!Number.isInteger(step) || !Number.isFinite(numericValue) || !field || !value.trim()) {
                setError("스텝 번호와 편집 값을 확인하십시오.");
                return;
              }
              void run(async () => {
                setResult(null);
                setProposal(await api.stageImport(info.sessionId, step, field, numericValue));
              });
            }}>
              <label>스텝 <input type="number" min="1" max={info.stepCount} value={stepNo} onChange={(event) => setStepNo(event.target.value)} /></label>
              <label>필드 <select value={field} onChange={(event) => setField(event.target.value)}>
                {info.editableFields.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
              </select></label>
              <label>값 <input type="number" step="any" value={value} onChange={(event) => setValue(event.target.value)} /></label>
              <button type="submit" disabled={busy}>편집 추가</button>
              <button type="button" disabled={busy || !proposal} onClick={() => void run(async () => {
                setProposal(await api.clearImport(info.sessionId));
                setResult(null);
              })}>편집 지우기</button>
            </form>
            <p className="muted">허용된 필드: {info.editableFields.map((item) => item.name).join(", ")}</p>
            {proposal && <>
              <p>적용 예정: {proposal.accepted.map((item) => `${item.stepNo}:${item.field}=${item.value}`).join(", ") || "없음"}</p>
              {proposal.rejected.map((item, index) => <p className="danger" key={index}>{item.stepNo}:{item.field} — {item.reason}</p>)}
              {proposal.warnings.map((warning, index) => <p className="warn import-note" key={index}>{warning}</p>)}
            </>}
            <label className="import-output">출력 파일 절대 경로 <input value={outputPath} onChange={(event) => setOutputPath(event.target.value)} /></label>
            <label className="row" style={{ flexWrap: "wrap" }}><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /> 이 결과물은 분석용이며 장비 실행용이 아님을 확인했습니다.</label>
            <button className="primary" disabled={busy || !acknowledged || !proposal?.ok || !!proposal.rejected.length || !outputPath.trim()} onClick={() => void run(async () => {
              setResult(await api.patchImport(info.sessionId, outputPath.trim()));
            })}>새 SCH 파일 저장</button>
            {result && <p className="import-note import-file" role="status">저장: {result.outputPath}<br />검증 기록: {result.manifestPath}<br />변경된 바이트: {result.changedByteCount} · 장비 실행 불가</p>}
          </>}
        </div>
      </>}
    </div>
  );
}
