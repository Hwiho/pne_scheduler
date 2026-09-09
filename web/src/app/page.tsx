"use client";

import { useState } from "react";
import { api, type Json } from "@/lib/api";
import { useDocument } from "@/lib/useDocument";
import {
  ExportTab,
  ProcedureTab,
  ProtocolTab,
  SetupTab,
  ValidateTab,
} from "@/components/tabs";

const TABS = ["1. 설정", "2. 프로토콜", "3. 절차", "4. 검증", "5. 내보내기"] as const;

export default function Workspace() {
  const doc = useDocument();
  const [tab, setTab] = useState(0);
  const [methodName, setMethodName] = useState("");

  if (doc.error && !doc.views) {
    return (
      <main style={{ padding: 40 }}>
        <div className="card">
          <h2>연결할 수 없습니다</h2>
          <div className="muted">{doc.error}</div>
        </div>
      </main>
    );
  }
  if (!doc.views || !doc.project) {
    return <main style={{ padding: 40 }} className="muted">불러오는 중…</main>;
  }

  const plan = <T,>(action: string, args: Json = {}) =>
    api.plan<T>(action, doc.project as Json, args);

  const props = {
    views: doc.views,
    project: doc.project,
    apply: doc.apply,
    select: doc.select,
    plan,
  };

  return (
    <main style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
      <header className="row" style={{ flexWrap: "wrap" }}>
        <strong style={{ fontSize: 16 }}>{doc.views.title}</strong>
        <span className="muted grow">{doc.views.summary.headline}</span>
        <button disabled={!doc.canUndo || doc.busy} onClick={doc.undo}>
          ↶ 되돌리기{doc.undoLabel ? ` (${doc.undoLabel})` : ""}
        </button>
        <button disabled={!doc.canRedo || doc.busy} onClick={doc.redo}>↷ 다시</button>
        <input
          style={{ width: 140 }}
          placeholder="방법 이름"
          value={methodName}
          onChange={(e) => setMethodName(e.target.value)}
        />
        <button
          disabled={!methodName.trim()}
          onClick={async () => {
            await api.saveMethod(doc.project as Json, methodName.trim());
            setMethodName("");
          }}
        >
          라이브러리에 저장
        </button>
      </header>

      <nav className="row">
        {TABS.map((name, index) => (
          <button
            key={name}
            className={index === tab ? "primary" : ""}
            onClick={() => setTab(index)}
          >
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

      <footer className="muted">
        {doc.views.summary.totalSteps} 스텝 · {doc.views.summary.durationText} ·{" "}
        {doc.views.release.stageLabel}
        {doc.notice && ` · ${doc.notice}`}
      </footer>
    </main>
  );
}
