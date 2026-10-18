"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type BackupPlan, type DataStatus, type Json, type RestoreInspection } from "@/lib/api";

export function CompanionControls() {
  const [status, setStatus] = useState<DataStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const epoch = useRef(0);
  const refresh = useCallback(async () => {
    const ticket = ++epoch.current;
    try {
      const result = await api.dataAction<DataStatus>("status");
      if (ticket === epoch.current) { setStatus(result); setError(""); }
    } catch (err) { if (ticket === epoch.current) setError(String(err)); }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => { clearInterval(timer); epoch.current++; };
  }, [refresh]);
  async function act(action: string) {
    setBusy(true); setError(""); ++epoch.current;
    try {
      const result = await api.dataAction<DataStatus>(action, { runId: status?.companion.runId, confirmed });
      ++epoch.current; setStatus(result); setConfirmed(false);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }
  const c = status?.companion;
  return <section className="data-companion" aria-label="알림 실행기 관리">
    <div className="resource-heading"><div><span className="eyebrow">NOTIFICATION RUNNER</span><h3>알림 실행기</h3></div>
      <span className="stage-pill" role="status">{c?.label ?? "상태 확인 중"}</span></div>
    <p className="muted">버전 {c?.version ?? "—"} · 최근 확인 {c?.lastHeartbeatAt ? new Date(c.lastHeartbeatAt).toLocaleString("ko-KR") : "없음"}</p>
    <div className="action-row">
      <button disabled={busy || !c?.canStart} onClick={() => void act("companionStart")}>Windows 알림 시작</button>
      <button disabled={busy || !c?.canStop || c?.state === "stopping"} onClick={() => void act("companionStop")}>안전 종료 요청</button>
      <button disabled={busy} onClick={() => void refresh()}>실행기 상태 새로고침</button>
    </div>
    <p className="muted">안전 종료는 진행 중인 알림 처리를 마친 뒤 잠금 해제를 확인합니다. 창을 닫아도 실행기는 계속 동작합니다. 시작은 Windows에서만 가능합니다.</p>
    {c?.lastError && <p className="danger">마지막 실행 오류: {c.lastError}</p>}
    {c?.restorePaused && <div className="storage-migration">
      <strong>복원된 알림은 일시 정지 중입니다</strong>
      <p>재개 시 발송 대상인 지연 알림 {c.pendingCount}개. 고온저장 목록에서 확인·미루기를 먼저 할 수 있습니다.</p>
      <label className="data-check"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />복원 일정과 지연 알림을 검토했습니다</label>
      <button disabled={busy || !confirmed} onClick={() => void act("resumeNotifications")}>기존 알림 설정 재개</button>
      <p className="muted">설정만 복구하며 실행기를 자동으로 시작하지 않습니다.</p>
    </div>}
    <p className="muted">{c?.deliveryMeaning}</p>
    {error && <p role="alert" className="danger">{error}</p>}
  </section>;
}

export function DataSafety({ project }: { project: Json }) {
  const [status, setStatus] = useState<DataStatus | null>(null);
  const [includeCurrent, setIncludeCurrent] = useState(true);
  const [paths, setPaths] = useState("");
  const [output, setOutput] = useState("");
  const [externalStopped, setExternalStopped] = useState(false);
  const [plan, setPlan] = useState<BackupPlan | null>(null);
  const [archive, setArchive] = useState("");
  const [destination, setDestination] = useState("");
  const [inspection, setInspection] = useState<RestoreInspection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const revision = useRef(0);
  useEffect(() => { void api.dataAction<DataStatus>("status").then(setStatus).catch((e) => setError(String(e))); }, []);
  useEffect(() => { revision.current++; setPlan(null); }, [project, includeCurrent, paths]);
  useEffect(() => { revision.current++; setInspection(null); }, [archive]);
  const args = { includeCurrent, project, projectPaths: paths.split(/\r?\n/).map((p) => p.trim()).filter(Boolean) };
  async function run<T>(action: string, body: Json, accept: (result: T) => void) {
    const ticket = revision.current;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api.dataAction<T>(action, body);
      if (ticket === revision.current) accept(result);
      else setMessage("입력이 변경되었습니다. 다시 미리보기 하세요.");
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }
  return <div className="col data-safety">
    <div className="card"><span className="eyebrow">DATA CARE</span><h2>데이터 관리</h2>
      <p className="resource-description">백업 내용을 먼저 확인하고, 복원은 새 폴더에서 검증합니다. 현재 사용 중인 원본을 덮어쓰거나 자동으로 전환하지 않습니다.</p>
      <details><summary>현재 데이터 위치 · 이 컴퓨터 기준</summary><dl className="data-paths">
        <dt>보관 DB</dt><dd>{status?.database ?? "확인 중"}</dd><dt>방법 라이브러리</dt><dd>{status?.library}</dd><dt>자동 복구본</dt><dd>{status?.recovery}</dd>
      </dl></details>
      <CompanionControls />
    </div>
    <div className="data-columns">
      <section className="card"><span className="eyebrow">01 / BACKUP</span><h2>검증 백업 만들기</h2>
        <p className="muted">보관 기록·확인 이력, 방법 라이브러리, Tk 자동 복구본을 포함합니다. 실행 중인 알림은 먼저 안전 종료하세요.</p>
        <fieldset disabled={busy} className="data-fields">
          <label className="data-check"><input type="checkbox" checked={includeCurrent} onChange={(e) => setIncludeCurrent(e.target.checked)} />현재 웹 프로젝트 포함 (미저장 변경 포함)</label>
          <label>추가 프로젝트 절대 경로 (한 줄에 하나)<textarea value={paths} rows={3} onChange={(e) => setPaths(e.target.value)} placeholder="C:\실험\프로젝트.schproj" /></label>
          <button onClick={() => void run<BackupPlan>("backupPreview", args, setPlan)}>백업 내용 미리보기</button>
          {plan && <div className="data-preview" aria-label="백업 미리보기"><strong>{plan.files.length}개 파일 · {(plan.totalBytes / 1024).toFixed(1)} KiB</strong>
            <ul>{plan.files.map((file) => <li key={file.path}>{file.path}</li>)}</ul>
            <p className="muted">제외: {plan.excluded.join(" / ")}</p></div>}
          <label>새 백업 ZIP 절대 경로<input value={output} onChange={(e) => setOutput(e.target.value)} placeholder="C:\백업\실험-2026-10-18.zip" /></label>
          <label className="data-check"><input type="checkbox" checked={externalStopped} onChange={(e) => setExternalStopped(e.target.checked)} />다른 구버전 앱·외부 편집기의 데이터 쓰기를 중지했습니다</label>
          <button className="primary" disabled={!plan || !output.trim() || !externalStopped} onClick={() => void run<{ path: string; sha256: string }>("backupCreate", { ...args, outputPath: output, token: plan?.token, externalWritesStopped: externalStopped }, (r) => { setPlan(null); setArchive(r.path); setMessage(`백업 생성·검증 완료: ${r.path} · SHA-256 ${r.sha256}`); })}>검증 백업 저장</button>
        </fieldset>
        <p className="muted">선택하지 않은 외부 파일과 다른 브라우저 초안은 포함하지 않습니다. 암호화되지 않은 로컬 ZIP이며 외부로 전송하지 않습니다.</p>
      </section>
      <section className="card"><span className="eyebrow">02 / RESTORE</span><h2>새 폴더로 복원</h2>
        <p className="muted">파일 목록·해시·DB 무결성을 검사한 뒤 복원합니다. 기존 파일과 폴더는 덮어쓰지 않습니다.</p>
        <fieldset disabled={busy} className="data-fields">
          <label>백업 ZIP 절대 경로<input value={archive} onChange={(e) => setArchive(e.target.value)} placeholder="검사할 백업 ZIP" /></label>
          <button disabled={!archive.trim()} onClick={() => void run<RestoreInspection>("restoreInspect", { archivePath: archive }, setInspection)}>복원 전 검사</button>
          {inspection && <div className="data-preview" aria-label="복원 검사 결과"><strong>검사 통과 · {inspection.files.length}개 파일</strong>
            <p>보관 기록 {inspection.counts.storage_records}개 · 알림 {inspection.counts.storage_alerts}개</p>
            <p className="muted">앱 {inspection.appVersion} · {new Date(inspection.createdAt).toLocaleString("ko-KR")}</p>
            <details><summary>복원 파일 목록</summary><ul>{inspection.files.map((f) => <li key={f.path}>{f.path}</li>)}</ul></details>
            <p>{inspection.note}</p></div>}
          <label>새 복원 폴더 절대 경로<input value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="기존 폴더 안의 아직 없는 새 폴더" /></label>
          <button className="primary" disabled={!inspection || !destination.trim()} onClick={() => void run<{ path: string; note: string }>("restoreApply", { archivePath: archive, destination, token: inspection?.token }, (r) => { setInspection(null); setMessage(`복원 완료: ${r.path} · ${r.note}`); })}>원본 보존 · 새 폴더 복원</button>
        </fieldset>
        <p className="muted">복원 후 해당 폴더를 --data-dir로 지정하여 다시 실행하세요. 알림 설정 재개와 실행기 시작은 별도 확인이 필요합니다.</p>
      </section>
    </div>
    {busy && <p role="status">검사·처리 중입니다. 완료될 때까지 이 화면을 유지하세요.</p>}
    {error && <div className="card danger" role="alert">{error}</div>}
    {message && <div className="card data-result" role="status">{message}</div>}
  </div>;
}
