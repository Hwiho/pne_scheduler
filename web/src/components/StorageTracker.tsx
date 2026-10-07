"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type StorageRecord, type StorageResponse } from "@/lib/api";

const LEGACY_KEY = "pne_scheduler.storage_tracker.v1";

function localDateTime(timestamp = Date.now()): string {
  const date = new Date(timestamp);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function duration(milliseconds: number): string {
  const total = Math.floor(Math.max(0, milliseconds) / 60_000);
  const days = Math.floor(total / 1440);
  const hours = Math.floor((total % 1440) / 60);
  const minutes = total % 60;
  return [days && `${days}일`, hours && `${hours}시간`, (minutes || (!days && !hours)) && `${minutes}분`].filter(Boolean).join(" ");
}

function parseLegacy(): { records: StorageRecord[]; error: string } {
  let raw: string | null;
  try { raw = localStorage.getItem(LEGACY_KEY); }
  catch { return { records: [], error: "예전 브라우저 기록에 접근할 수 없습니다. 원본은 변경하지 않았습니다." }; }
  if (!raw) return { records: [], error: "" };
  try {
    const rows: unknown = JSON.parse(raw);
    if (!Array.isArray(rows) || rows.length > 1000) throw new Error();
    const parsed = rows as StorageRecord[];
    if (parsed.some((row) => !row || typeof row.id !== "string" || typeof row.sample !== "string" ||
      !Number.isFinite(Date.parse(row.startedAt)) || !Number.isFinite(row.temperatureC) ||
      !Number.isFinite(row.targetDays) || row.targetDays <= 0)) throw new Error();
    return { records: parsed, error: "" };
  } catch { return { records: [], error: "예전 브라우저 기록이 손상되어 가져오지 않았습니다. 원본은 보존했습니다." }; }
}

export function StorageTracker() {
  const [data, setData] = useState<StorageResponse | null>(null);
  const [legacy, setLegacy] = useState<StorageRecord[]>([]);
  const [sample, setSample] = useState("");
  const [temperatureC, setTemperatureC] = useState("45");
  const [startedAt, setStartedAt] = useState("");
  const [targetDays, setTargetDays] = useState("30");
  const [checkpointDays, setCheckpointDays] = useState("");
  const [notifyEnabled, setNotifyEnabled] = useState(false);
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    try { setData(await api.storage()); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }, []);

  useEffect(() => {
    const time = Date.now();
    setNow(time); setStartedAt(localDateTime(time));
    const previous = parseLegacy();
    setLegacy(previous.records);
    if (previous.error) setError(previous.error);
    void refresh();
    const timer = window.setInterval(() => { setNow(Date.now()); void refresh(); }, 60_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); await refresh(); setMessage(success); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }

  function addRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const start = new Date(startedAt);
    const temperature = Number(temperatureC);
    const days = Number(targetDays);
    const checkpoints = checkpointDays.trim() ? checkpointDays.split(",").map((value) => Number(value.trim())) : [];
    if (!sample.trim() || !Number.isFinite(start.getTime()) || start.getTime() > Date.now() ||
      !Number.isFinite(temperature) || !Number.isFinite(days) || days <= 0 ||
      checkpoints.some((day) => !Number.isFinite(day) || day <= 0 || day >= days) ||
      new Set(checkpoints).size !== checkpoints.length) {
      setError("시료명·시작 시각·온도·목표 기간·중간 확인일을 확인하세요. 확인일은 중복 없이 최종 목표일 전이어야 합니다.");
      return;
    }
    void run(async () => {
      await api.addStorage({ sample: sample.trim(), startedAt: start.toISOString(), temperatureC: temperature, targetDays: days, checkpointDays: checkpoints, notifyEnabled });
      setSample(""); setStartedAt(localDateTime()); setCheckpointDays("");
    }, "보관 기록을 이 컴퓨터에 저장했습니다.");
  }

  const importedIds = new Set(data?.records.map((row) => row.id) ?? []);
  const pendingLegacy = legacy.filter((row) => !importedIds.has(row.id));

  return <div className="col storage-tracker">
    <div className="card">
      <div className="resource-heading">
        <div>
          <span className="eyebrow">STORAGE TIMER</span>
          <h2>고온저장 경과시간</h2>
          <p className="resource-description">시료별 저장 시작 시각과 확인 일정을 기록합니다. 이 타이머는 장비 온도·로그를 읽지 않으므로 실제 챔버 상태는 별도로 확인하세요.</p>
        </div>
      </div>
      <div className={`storage-companion ${data?.companion.active ? "online" : "offline"}`} role="status"><span className="status-dot" aria-hidden="true" />{data?.companion.active ? "Windows 알림 실행기 연결됨 · 실제 표시 여부는 시스템 설정에 따름" : "Windows 알림 실행기 미연결 · 브라우저를 닫으면 화면 알림 없음"}</div>
      <form className="storage-form" onSubmit={addRecord}>
        <label htmlFor="storage-sample">시료명<input id="storage-sample" value={sample} onChange={(event) => setSample(event.target.value)} placeholder="예: Cell A-01" maxLength={120} disabled={busy || !data} required /></label>
        <label htmlFor="storage-temperature">저장 온도 (°C)<input id="storage-temperature" type="number" step="0.1" min="-100" max="300" value={temperatureC} onChange={(event) => setTemperatureC(event.target.value)} disabled={busy || !data} required /></label>
        <label htmlFor="storage-started-at">저장 시작 시각<input id="storage-started-at" type="datetime-local" max={localDateTime(now || Date.now())} value={startedAt} onChange={(event) => setStartedAt(event.target.value)} disabled={busy || !data} required /></label>
        <label htmlFor="storage-target-days">목표 기간 (일)<input id="storage-target-days" type="number" min="0.01" max="3650" step="0.01" value={targetDays} onChange={(event) => setTargetDays(event.target.value)} disabled={busy || !data} required /></label>
        <label htmlFor="storage-checkpoints">중간 확인일 (선택)<input id="storage-checkpoints" value={checkpointDays} onChange={(event) => setCheckpointDays(event.target.value)} placeholder="예: 7, 14" disabled={busy || !data} /></label>
        <label className="storage-notify"><input type="checkbox" checked={notifyEnabled} onChange={(event) => setNotifyEnabled(event.target.checked)} disabled={busy || !data} /> 중간 확인일과 최종 목표일에 Windows 알림 받기 (실행기 필요)</label>
        <div className="action-row"><button className="primary" type="submit" disabled={busy || !data}>기록 추가</button></div>
      </form>
      {pendingLegacy.length > 0 && <div className="storage-migration"><strong>예전 브라우저 기록 {pendingLegacy.length}개</strong><p className="muted">현재 브라우저에만 남아 있습니다. 가져오기는 중복을 확인하며 원본을 삭제하지 않습니다. 기존 기록의 알림은 꺼진 상태로 이전됩니다.</p><button type="button" disabled={busy || !data} onClick={() => void run(() => api.importStorage(legacy), "예전 기록을 가져왔습니다. 브라우저 원본은 그대로 남겨 두었습니다.")}>로컬 DB로 가져오기</button></div>}
      {error && <p className="danger" role="alert">{error}</p>}
      {message && <div className="status-note status-note-success" role="status"><span aria-hidden="true">✓</span><p>{message}</p></div>}
    </div>
    <div className="card" aria-busy={!data}>
      <div className="resource-heading">
        <div>
          <span className="eyebrow">STORAGE LOG</span>
          <h2>보관 기록 · {data ? `${data.records.filter((row) => !row.completedAt).length}개 진행 중` : "불러오는 중"}</h2>
          <p className="resource-description">목표 시각과 중간 확인 일정을 시료별로 검토하고, 확인 이력을 남깁니다.</p>
        </div>
      </div>
      {!data && <p className="muted" role="status">로컬 기록을 불러오는 중입니다.</p>}
      {data?.records.length === 0 && <div className="empty-state"><span aria-hidden="true">◷</span><h3>등록된 보관 시료가 없습니다</h3><p>위 입력란에서 첫 시료의 시작 시각, 온도, 목표 기간을 기록하세요.</p></div>}
      <div className="storage-records">{data?.records.map((record) => {
        const start = Date.parse(record.startedAt);
        const finish = Date.parse(record.dueAt) || start + record.targetDays * 86_400_000;
        const due = now >= finish;
        const elapsedUntil = record.completedAt ? Date.parse(record.completedAt) : now;
        return <article className={`storage-record${record.completedAt ? " completed" : ""}`} key={record.id} aria-labelledby={`storage-record-${record.id}`}>
          <div className="row storage-record-title"><strong id={`storage-record-${record.id}`}>{record.sample}</strong><span className={record.completedAt ? "stage-pill" : due ? "badge" : "stage-pill"}>{record.completedAt ? "완료" : due ? "목표 도달" : "보관 중"}</span></div>
          <div className="storage-elapsed">{record.completedAt ? "완료 시 경과" : "경과"} {duration(elapsedUntil - start)}</div>
          <p className="muted">{record.temperatureC}°C · {record.notifyEnabled ? "Windows 알림 요청" : "알림 끔"}{record.notifiedAt ? " · 알림 전송됨" : ""}</p>
          <p className="muted">시작: <time dateTime={record.startedAt}>{new Date(start).toLocaleString("ko-KR")}</time></p>
          <p className="muted">목표: <time dateTime={record.dueAt}>{new Date(finish).toLocaleString("ko-KR")}</time> ({record.targetDays}일)</p>
          {record.completedAt ? <p className="muted">완료: <time dateTime={record.completedAt}>{new Date(elapsedUntil).toLocaleString("ko-KR")}</time> · 완료 기록은 알림을 보내지 않습니다.</p> : <p className="muted">{due ? `목표보다 ${duration(now - finish)} 지남` : `목표까지 ${duration(finish - now)} 남음`}</p>}
          <div aria-label="알림 일정">{record.alerts.map((alert) => {
            const effectiveDue = Date.parse(alert.snoozedUntil ?? alert.dueAt);
            const alertDue = now >= effectiveDue;
            const label = alert.kind === "final" ? `최종 목표 ${record.targetDays}일` : `중간 확인 ${alert.checkpointDay}일`;
            const state = alert.acknowledgedAt ? "확인됨" : record.completedAt ? "보관 완료 · 알림 중지" : alert.snoozedUntil && !alertDue ? "다시 알림 대기" : alert.notifiedAt ? "알림 전송됨" : alertDue ? "확인 필요" : "예정";
            return <div className="storage-migration" key={alert.id}>
              <strong>{label} · {state}</strong>
              <p className="muted"><time dateTime={alert.snoozedUntil ?? alert.dueAt}>{new Date(effectiveDue).toLocaleString("ko-KR")}</time>{alert.snoozedUntil ? " (다시 알림)" : ""}</p>
              {!record.completedAt && alertDue && !alert.acknowledgedAt && <div className="action-row">
                <button type="button" className="chip" disabled={busy} onClick={() => void run(() => api.acknowledgeStorageAlert(record.id, alert.id), `${label} 알림을 확인했습니다.`)}>확인</button>
                <button type="button" className="chip" disabled={busy} onClick={() => void run(() => api.snoozeStorageAlert(record.id, alert.id, new Date(Date.now() + 86_400_000).toISOString()), `${label} 알림을 1일 미뤘습니다.`)}>1일 후 다시 알림</button>
              </div>}
            </div>;
          })}</div>
          <div className="action-row">
            <button type="button" className="chip" disabled={busy} onClick={() => void run(() => api.completeStorage(record.id, !record.completedAt), record.completedAt ? "보관 기록을 다시 진행 중으로 표시했습니다." : "보관 기록을 완료로 표시했습니다.")}>{record.completedAt ? "완료 취소" : "완료 표시"}</button>
            <button type="button" className="chip" disabled={busy || !!record.completedAt} title={record.completedAt ? "완료 취소 후 알림을 설정할 수 있습니다." : undefined} onClick={() => void run(() => api.storageNotifications(record.id, !record.notifyEnabled), record.notifyEnabled ? "Windows 알림을 껐습니다. 일정과 확인 이력은 보존했습니다." : "Windows 알림을 켰습니다. 실행 중인 Windows 알림 프로그램이 확인 전 알림을 처리합니다.")}>{record.notifyEnabled ? "Windows 알림 끄기" : "Windows 알림 켜기"}</button>
          </div>
        </article>;
      })}</div>
    </div>
  </div>;
}
