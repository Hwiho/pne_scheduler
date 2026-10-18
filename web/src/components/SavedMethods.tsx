"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Json, type MethodImpact, type MethodPreview, type MethodSummary } from "@/lib/api";

function Impact({ title, impact }: { title: string; impact: MethodImpact }) {
  return <section className="method-impact" aria-label={title}>
    <h3>{title}</h3><p>{impact.headline}</p>
    {impact.note && <p className="warn">{impact.note}</p>}
    {impact.lines.length > 0 && <details><summary>스텝 변경 상세</summary><ul>{impact.lines.map((line, index) => <li key={index}>{line}</li>)}</ul></details>}
  </section>;
}

export function SavedMethods({ project, busy, revision, apply }: {
  project: Json; busy?: boolean; revision: string;
  apply: (action: string, args?: Json) => Promise<void>;
}) {
  const [methods, setMethods] = useState<MethodSummary[]>([]);
  const [methodId, setMethodId] = useState("");
  const [versions, setVersions] = useState<MethodSummary[]>([]);
  const [version, setVersion] = useState("");
  const [compareVersion, setCompareVersion] = useState("");
  const [replace, setReplace] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listing, setListing] = useState(true);
  const [previewing, setPreviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{ source: Json; selection: string; result: MethodPreview } | null>(null);
  const request = useRef(0);
  const selection = `${methodId}:${version}:${compareVersion}:${replace}:${revision}:${refresh}`;
  const current = useRef({ project, selection });
  current.current = { project, selection };
  const active = preview?.source === project && preview.selection === selection ? preview.result : null;
  const chosen = versions.find((item) => item.methodId === methodId && item.version === Number(version));
  const locked = !!busy || applying;

  useEffect(() => {
    let cancelled = false;
    setListing(true); setError("");
    api.library().then((result) => {
      if (cancelled) return;
      setMethods(result.methods);
      setMethodId((previous) => result.methods.some((item) => item.methodId === previous) ? previous : result.methods[0]?.methodId ?? "");
    }).catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason)); })
      .finally(() => { if (!cancelled) setListing(false); });
    return () => { cancelled = true; };
  }, [revision, refresh]);

  useEffect(() => {
    let cancelled = false;
    setVersions([]); setVersion(""); setCompareVersion(""); setLoading(true);
    if (!methodId) { setLoading(false); return; }
    api.libraryVersions(methodId).then((result) => {
      if (cancelled) return;
      const ordered = [...result.versions].sort((a, b) => b.version - a.version);
      setVersions(ordered); setVersion(ordered[0] ? String(ordered[0].version) : "");
    }).catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [methodId, revision, refresh]);

  useEffect(() => {
    request.current += 1; setPreview(null); setPreviewing(false);
    return () => { request.current += 1; };
  }, [project, selection]);

  async function inspect() {
    const ticket = ++request.current;
    const source = project;
    setPreviewing(true); setError(""); setPreview(null);
    try {
      const result = await api.previewMethod(source, methodId, Number(version), replace, compareVersion ? Number(compareVersion) : undefined);
      if (ticket === request.current && current.current.project === source && current.current.selection === selection) {
        setPreview({ source, selection, result });
      }
    } catch (reason) { if (ticket === request.current) setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { if (ticket === request.current) setPreviewing(false); }
  }

  return <section className="card saved-methods" aria-label="저장된 방법 버전 관리">
    <h2>내 블록 · 저장된 방법</h2>
    <p className="muted">과거 버전과 변경 내용을 확인한 뒤 적용하세요. 현재 셀 용량·장비는 유지되며, 적용 전체를 한 번에 되돌릴 수 있습니다.</p>
    <button disabled={locked || listing} onClick={() => setRefresh((value) => value + 1)}>저장 목록 새로고침</button>
    {listing && <p className="muted" role="status">저장된 방법을 불러오는 중…</p>}
    {!listing && methods.length === 0 && !error && <div className="empty-state"><h3>아직 저장한 방법이 없습니다</h3><p>박스의 조건 편집에서 ‘내 프리셋으로 저장’을 사용하거나 현재 실험을 라이브러리에 저장하세요.</p></div>}
    {methods.length > 0 && <>
      <div className="method-browser-controls">
        <label>저장된 블록 선택<select aria-label="저장된 블록 선택" value={methodId} onChange={(event) => { setMethodId(event.target.value); setError(""); }} disabled={locked || listing}>
          {methods.map((method) => <option key={method.methodId} value={method.methodId}>{method.name} · 최신 v{method.version}</option>)}
        </select></label>
        <label>불러올 버전<select value={version} onChange={(event) => {
          const next = event.target.value;
          setVersion(next); if (compareVersion === next) setCompareVersion(""); setError("");
        }} disabled={locked || loading || listing}>
          {versions.map((item) => <option key={item.version} value={item.version}>v{item.version} · {item.moduleCount}개 구간</option>)}
        </select></label>
        <label>비교 기준 버전<select value={compareVersion} onChange={(event) => setCompareVersion(event.target.value)} disabled={locked || loading || listing}>
          <option value="">이전 버전 자동</option>
          {versions.filter((item) => item.version !== Number(version)).map((item) => <option key={item.version} value={item.version}>v{item.version}</option>)}
        </select></label>
        <label>적용 방식<select value={replace ? "replace" : "append"} onChange={(event) => setReplace(event.target.value === "replace")} disabled={locked}>
          <option value="append">현재 실험 끝에 추가</option><option value="replace">현재 구간 전체를 교체</option>
        </select></label>
      </div>
      {chosen && <p className="muted">v{chosen.version} · 저장 {chosen.savedAt.replace("T", " ")} · 장비 {chosen.equipmentUnit || "미지정"}{chosen.description && ` · ${chosen.description}`}</p>}
      {replace && <p className="warn">현재 구간 전체가 선택한 방법으로 바뀝니다. 필요하면 먼저 프로젝트를 다운로드하세요. 적용 후 되돌리기로 복원할 수 있습니다.</p>}
      <div className="action-row">
        <button disabled={locked || loading || listing || previewing || !chosen} onClick={() => void inspect()}>{previewing ? "비교 중…" : "방법 변경 미리보기"}</button>
        <button className="primary" disabled={locked || loading || listing || previewing || !active?.ok} onClick={async () => {
          if (!active?.ok) return;
          setApplying(true);
          try { await apply("loadMethod", { methodId, version: Number(version), replace, previewToken: active.token }); }
          finally { setApplying(false); setPreview(null); }
        }}>{replace ? "선택한 버전으로 교체" : "현재 실험에 추가"}</button>
      </div>
      {active && <div className="method-preview" role="status">
        {active.notes.map((line) => <p key={line}>{line}</p>)}
        {active.warnings.map((line) => <p className="warn" key={line}>{line}</p>)}
        {active.errors.map((line) => <p className="danger" key={line}>{line}</p>)}
        {active.impact && <Impact title="현재 실험에 적용하면" impact={active.impact} />}
        {active.versionDiff ? <>
          <Impact title={`저장 버전 비교 · v${active.versionDiff.baseVersion} → v${active.versionDiff.headVersion}`} impact={active.versionDiff} />
          {active.versionDiff.metadataChanges.map((line) => <p key={line}>{line}</p>)}
        </> : <p className="muted">비교할 이전 저장 버전이 없습니다.</p>}
        <p className="muted">비교는 같은 입력 기준용량에서 계산한 스텝 조건을 기준으로 합니다. 실제 장비 시간·측정 결과의 비교가 아닙니다.</p>
      </div>}
    </>}
    {error && <p className="danger" role="alert">{error}</p>}
  </section>;
}
