"use client";

import { useEffect, useState } from "react";
import { api, type Json } from "@/lib/api";
import { useDocument } from "@/lib/useDocument";
import { ImportTab } from "@/components/ImportTab";
import { StorageTracker } from "@/components/StorageTracker";
import { ProjectTools } from "@/components/ProjectTools";
import { WorkspaceIcon, type WorkspaceIconName } from "@/components/WorkspaceIcon";
import {
  ExportTab,
  ProtocolTab,
  SetupTab,
} from "@/components/tabs";

const TABS = ["설정", "프로토콜", "내보내기", "기존 SCH", "고온저장"] as const;
const TAB_ICONS: WorkspaceIconName[] = ["settings", "flow", "export", "import", "clock"];

export default function Workspace() {
  const doc = useDocument();
  const [tab, setTab] = useState(0);
  const [methodName, setMethodName] = useState("");
  const [methodStatus, setMethodStatus] = useState("");
  const [savingMethod, setSavingMethod] = useState(false);
  const [libraryRevision, setLibraryRevision] = useState(0);
  useEffect(() => { setMethodStatus(""); }, [doc.project]);

  if (doc.error && !doc.views) {
    return (
      <main className="workspace">
        <div className="card">
          <h2>연결할 수 없습니다</h2>
          <div className="muted">{doc.error}</div>
        </div>
      </main>
    );
  }
  if (!doc.views || !doc.project) {
    return <main className="workspace"><div className="workspace-loading" role="status"><span className="brand-mark" aria-hidden="true">P</span><strong>실험 워크스페이스를 준비하고 있습니다</strong><span className="muted">저장된 초안과 프로토콜 정보를 불러오는 중…</span></div></main>;
  }

  const plan = <T,>(action: string, args: Json = {}) =>
    api.plan<T>(action, doc.project as Json, args);

  const props = {
    views: doc.views,
    project: doc.project,
    apply: doc.apply,
    select: doc.select,
    busy: doc.busy,
    libraryRevision,
    plan,
    openImport: () => setTab(3),
  };

  return (
    <main className="workspace">
      <header className="workspace-header">
        <div className="workspace-identity">
          <div className="workspace-brand"><span className="brand-mark" aria-hidden="true">P</span><span className="eyebrow">PNE SCHEDULER <span className="brand-divider">/</span> PROTOCOL WORKSPACE</span></div>
          <div className="workspace-title-row">
            <h1>{String(doc.project.name || "새 스케줄")}</h1>
            <span className="stage-pill" data-stage={doc.views.release.stage}>{doc.views.release.stageLabel}</span>
          </div>
          <p className="workspace-document-state">{doc.views.title} <span aria-hidden="true">·</span> {doc.views.summary.totalSteps}스텝 <span aria-hidden="true">·</span> {doc.views.summary.durationText}</p>
        </div>
        <div className="workspace-actions">
          <div className="history-actions">
            <button disabled={!doc.canUndo || doc.busy} onClick={doc.undo} title={doc.undoLabel}>
              ↶ 되돌리기
            </button>
            <button disabled={!doc.canRedo || doc.busy} onClick={doc.redo}>↷ 다시</button>
          </div>
          <form className="save-method" onSubmit={async (event) => {
            event.preventDefault();
            if (!methodName.trim() || savingMethod || doc.busy) return;
            setSavingMethod(true);
            setMethodStatus("");
            try {
              const saved = await api.saveMethod(doc.project as Json, methodName.trim());
              setMethodStatus(`${saved.method.name} · v${saved.method.version} 저장 완료`);
              setMethodName("");
              setLibraryRevision((revision) => revision + 1);
            } catch (err) {
              doc.setError(err instanceof Error ? err.message : String(err));
            } finally { setSavingMethod(false); }
          }}>
            <input aria-label="방법 이름" placeholder="방법 이름" value={methodName} disabled={savingMethod} onChange={(e) => setMethodName(e.target.value)} />
            <button type="submit" disabled={!methodName.trim() || savingMethod || doc.busy}>{savingMethod ? "저장 중…" : "라이브러리에 저장"}</button>
            {methodStatus && <span className="muted" role="status">{methodStatus}</span>}
          </form>
        </div>
      </header>

      <ProjectTools project={doc.project} busy={doc.busy} replace={doc.replace} />

      <nav className="workspace-nav" aria-label="작업 단계">
        {TABS.map((name, index) => (
          <button
            key={name}
            className={index === tab ? "primary" : ""}
            aria-current={index === tab ? "page" : undefined}
            onClick={() => setTab(index)}
          >
            <span className="nav-number">{String(index + 1).padStart(2, "0")}</span>
            <WorkspaceIcon name={TAB_ICONS[index]} className="nav-icon" />
            {name}
          </button>
        ))}
      </nav>

      {doc.error && (
        <div className="card" style={{ background: "var(--danger-soft)" }}>
          <span className="danger">{doc.error}</span>
          <button className="chip" style={{ marginLeft: 8 }} onClick={() => doc.setError("")}>
            닫기
          </button>
        </div>
      )}
      {doc.lastDiff && <details className="card">
        <summary>마지막 변경 비교 · {doc.lastDiff.headline}</summary>
        <p className="muted">{doc.lastDiff.beforeCount} → {doc.lastDiff.afterCount} 스텝 · 최근 편집 직전과 비교합니다.</p>
        <div className="table-scroll" style={{ maxHeight: 250 }}><table>
          <thead><tr><th>스텝</th><th>항목</th><th>변경 전</th><th>변경 후</th></tr></thead>
          <tbody>{(doc.lastDiff.changes ?? []).slice(0, 50).flatMap((change, index) => change.fields.map((field, fieldIndex) => <tr key={`${index}-${fieldIndex}`}>
            <td>{change.label}</td><td>{field.field}</td><td>{String(field.before ?? "—")}</td><td>{String(field.after ?? "—")}</td>
          </tr>))}</tbody>
        </table></div>
        {(doc.lastDiff.changes?.length ?? 0) > 50 && <p className="muted">변경 {doc.lastDiff.changes?.length}개 중 처음 50개 스텝을 표시합니다.</p>}
      </details>}

      {tab === 0 && <SetupTab {...props} />}
      {tab === 1 && <ProtocolTab {...props} />}
      {tab === 2 && <ExportTab {...props} />}
      {tab === 3 && <ImportTab />}
      {tab === 4 && <StorageTracker />}

      <footer className="workspace-footer">
        {doc.views.summary.totalSteps} 스텝 · {doc.views.summary.durationText} ·{" "}
        {doc.views.release.stageLabel}
        {doc.notice && ` · ${doc.notice}`}
      </footer>
    </main>
  );
}
