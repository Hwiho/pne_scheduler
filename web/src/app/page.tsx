"use client";

import { useState } from "react";
import { api, type Json } from "@/lib/api";
import { useDocument } from "@/lib/useDocument";
import { ImportTab } from "@/components/ImportTab";
import {
  ExportTab,
  ProcedureTab,
  ProtocolTab,
  SetupTab,
  ValidateTab,
} from "@/components/tabs";

const TABS = ["설정", "프로토콜", "절차", "검증", "내보내기", "기존 SCH"] as const;

export default function Workspace() {
  const doc = useDocument();
  const [tab, setTab] = useState(0);
  const [methodName, setMethodName] = useState("");

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
    return <main className="workspace muted">불러오는 중…</main>;
  }

  const plan = <T,>(action: string, args: Json = {}) =>
    api.plan<T>(action, doc.project as Json, args);

  const props = {
    views: doc.views,
    project: doc.project,
    apply: doc.apply,
    select: doc.select,
    plan,
    openImport: () => setTab(5),
  };

  return (
    <main className="workspace">
      <header className="workspace-header">
        <div className="workspace-identity">
          <span className="eyebrow">PNE · PROTOCOL WORKSPACE</span>
          <div className="workspace-title-row">
            <h1>{doc.views.title}</h1>
            <span className="stage-pill">{doc.views.release.stageLabel}</span>
          </div>
          <p>{doc.views.summary.headline}</p>
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
            if (!methodName.trim()) return;
            try {
              await api.saveMethod(doc.project as Json, methodName.trim());
              setMethodName("");
            } catch (err) {
              doc.setError(err instanceof Error ? err.message : String(err));
            }
          }}>
            <input aria-label="방법 이름" placeholder="방법 이름" value={methodName} onChange={(e) => setMethodName(e.target.value)} />
            <button type="submit" disabled={!methodName.trim()}>라이브러리에 저장</button>
          </form>
        </div>
      </header>

      <nav className="workspace-nav" aria-label="작업 단계">
        {TABS.map((name, index) => (
          <button
            key={name}
            className={index === tab ? "primary" : ""}
            aria-current={index === tab ? "page" : undefined}
            onClick={() => setTab(index)}
          >
            <span className="nav-number">{String(index + 1).padStart(2, "0")}</span>
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

      {tab === 0 && <SetupTab {...props} />}
      {tab === 1 && <ProtocolTab {...props} />}
      {tab === 2 && <ProcedureTab {...props} />}
      {tab === 3 && <ValidateTab {...props} />}
      {tab === 4 && <ExportTab {...props} />}
      {tab === 5 && <ImportTab />}

      <footer className="workspace-footer">
        {doc.views.summary.totalSteps} 스텝 · {doc.views.summary.durationText} ·{" "}
        {doc.views.release.stageLabel}
        {doc.notice && ` · ${doc.notice}`}
      </footer>
    </main>
  );
}
