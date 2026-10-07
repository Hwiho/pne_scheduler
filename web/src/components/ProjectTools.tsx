"use client";

import { useRef, useState } from "react";
import { api, type Json } from "@/lib/api";
import { emptyProject } from "@/lib/useDocument";

export function ProjectTools({ project, busy, replace }: {
  project: Json; busy: boolean; replace: (next: Json, label?: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [newProject, setNewProject] = useState(false);
  const [reading, setReading] = useState(false);
  const [error, setError] = useState("");
  const [candidate, setCandidate] = useState<{ project: Json; repairs: string[]; file: string } | null>(null);
  const request = useRef(0);
  const locked = busy || reading;
  function download() {
    const name = String(project.name || "프로젝트").replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").slice(0, 80);
    const url = URL.createObjectURL(new Blob([JSON.stringify(project, null, 2) + "\n"], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = name + ".schproj";
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className="project-tools" aria-label="프로젝트 파일 관리">
    <div className="resource-heading">
      <div>
        <h2>프로젝트 파일</h2>
        <p className="resource-description">설계본 .schproj · 장비 실행 파일이 아닙니다.</p>
      </div>
      <div className="action-row">
        <button aria-label="프로젝트 열기" disabled={locked} onClick={() => { setOpen(!open); setNewProject(false); }}>열기</button>
        <button aria-label="프로젝트 다운로드" disabled={locked} onClick={download}>다운로드</button>
        <button disabled={locked} onClick={() => { setNewProject(!newProject); setOpen(false); }}>새 프로젝트</button>
      </div>
    </div>
    {open && <div className="card project-open">
      <label>저장한 프로젝트 파일
        <input type="file" accept=".schproj,.json" aria-label="프로젝트 파일" disabled={locked} onChange={async (event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          const ticket = ++request.current;
          setCandidate(null); setError("");
          if (file.size > 2 * 1024 * 1024) { setError("2 MB 이하의 프로젝트 파일을 선택하세요."); return; }
          setReading(true);
          try {
            const data: unknown = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
            if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error(".schproj 프로젝트 파일의 최상위는 객체여야 합니다.");
            const result = await api.openProject(data as Json);
            if (ticket === request.current) setCandidate({ ...result, file: file.name });
          } catch (reason) {
            if (ticket === request.current) setError(reason instanceof SyntaxError ? "JSON 형식이 아닙니다. .schproj 파일을 선택하세요." : reason instanceof Error ? reason.message : String(reason));
          } finally { if (ticket === request.current) setReading(false); }
        }} />
      </label>
      {candidate && <>
        <p>{candidate.file} · {String(candidate.project.name)} · {Array.isArray(candidate.project.modules) ? candidate.project.modules.length : 0}개 모듈</p>
        {candidate.repairs.map((repair) => <p className="warn" key={repair}>{repair}</p>)}
        <p className="muted">현재 작업을 바꾸지만, 한 번의 되돌리기로 이전 작업을 복원할 수 있습니다.</p>
        <div className="action-row"><button disabled={locked} onClick={async () => { await replace(candidate.project, "프로젝트 열기: " + candidate.file); setOpen(false); setCandidate(null); }}>이 프로젝트 열기</button></div>
      </>}
      {error && <p className="danger" role="alert">{error}</p>}
    </div>}
    {newProject && <div className="card">
      <p>빈 프로젝트로 시작합니다. 현재 작업은 되돌리기로 복원할 수 있습니다. 별도 보관은 먼저 ‘프로젝트 다운로드’를 사용하세요.</p>
      <div className="action-row">
        <button disabled={locked} onClick={async () => { await replace(emptyProject(), "새 프로젝트 시작"); setNewProject(false); }}>새 프로젝트로 시작</button>
        <button onClick={() => setNewProject(false)}>취소</button>
      </div>
    </div>}
  </section>;
}
