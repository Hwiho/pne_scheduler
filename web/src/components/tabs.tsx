"use client";

// The workspace screens are pure views over the
// payload the API returned — no screen recomputes a gate or a validation result.

import { useState } from "react";
import { api, type Json, type Views } from "@/lib/api";
import { Field } from "./Field";

interface TabProps {
  views: Views;
  project: Json;
  apply: (action: string, args?: Json) => Promise<void>;
  select: (moduleId: string) => Promise<void>;
  plan: <T>(action: string, args?: Json) => Promise<T>;
  openImport?: () => void;
}

// --- 1. 설정 ---------------------------------------------------------------

export function SetupTab({ views, apply }: TabProps) {
  return (
    <div className="card setup-card">
      <h2>셀과 장비</h2>
      {views.setupFields.map((field) => (
        <div className="setup-field" key={field.key}>
          <label htmlFor={`setup-${field.key}`}>{field.label}</label>
          {field.choices.length > 0 ? (
            <select
              id={`setup-${field.key}`}
              value={field.value}
              onChange={(e) => apply("setEquipmentUnit", { unit: e.target.value })}
            >
              {field.choices.map((choice) => (
                <option key={choice} value={choice}>
                  {choice || "(지정 안 함)"}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={`setup-${field.key}`}
              defaultValue={field.value}
              readOnly={field.readOnly}
              onBlur={(e) =>
                !field.readOnly &&
                e.target.value !== field.value &&
                apply("setCellValue", { key: field.key, text: e.target.value })
              }
            />
          )}
          <div className="setup-detail">
            <span className="muted">{field.detail}</span>
            {field.issue && <span className="danger">{field.issue}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- 2. 프로토콜 -----------------------------------------------------------

export function ProtocolTab({ views, apply, select, plan }: TabProps) {
  const [campaign, setCampaign] = useState({
    totalCycles: "200",
    rptEvery: "50",
    chargeCRate: "0.5",
    dischargeCRate: "0.5",
    dcirRates: "1, 1.5, 2",
  });
  const [preview, setPreview] = useState<{ blocks?: { title: string }[]; warnings?: string[]; errors?: string[] } | null>(null);
  const [qcRates, setQcRates] = useState("");
  const [qcPreview, setQcPreview] = useState<{ ok?: boolean; notes?: string[]; warnings?: string[]; times?: number[] } | null>(null);

  const options = () => ({
    totalCycles: Number(campaign.totalCycles) || 0,
    rptEvery: Number(campaign.rptEvery) || 0,
    chargeCRate: Number(campaign.chargeCRate) || 0,
    dischargeCRate: Number(campaign.dischargeCRate) || 0,
    dcirRates: campaign.dcirRates.split(",").map(Number).filter((n) => !Number.isNaN(n)),
  });

  return (
    <div className="protocol-grid">
      <div className="col">
        <div className="card">
          <h2>사이클 + RPT 캠페인</h2>
          {(
            [
              ["총 사이클", "totalCycles"],
              ["RPT 주기", "rptEvery"],
              ["충전율", "chargeCRate"],
              ["방전율", "dischargeCRate"],
              ["DC-IR 전류", "dcirRates"],
            ] as const
          ).map(([label, key]) => (
            <div className="row" key={key} style={{ padding: "2px 0" }}>
              <label className="muted" style={{ width: 90 }}>{label}</label>
              <input
                className="grow"
                value={campaign[key]}
                onChange={(e) => setCampaign({ ...campaign, [key]: e.target.value })}
              />
            </div>
          ))}
          <div className="row" style={{ marginTop: 8 }}>
            <button onClick={async () => setPreview(await plan("campaign", options()))}>
              미리보기
            </button>
            <button
              className="primary"
              disabled={!preview?.blocks?.length}
              onClick={async () => {
                await apply("addCampaign", options());
                setPreview(null);
              }}
            >
              추가
            </button>
          </div>
          {preview?.blocks && (
            <div className="muted" style={{ marginTop: 8, whiteSpace: "pre-line" }}>
              {preview.blocks.map((b) => `· ${b.title}`).join("\n")}
            </div>
          )}
          {preview?.warnings && (
            <div className="warn" style={{ fontSize: 11, marginTop: 6, whiteSpace: "pre-line" }}>
              {preview.warnings.join("\n\n")}
            </div>
          )}
        </div>

        <div className="card">
          <h2>무엇을 알고 싶으신가요?</h2>
          {views.goals.map((goal) => (
            <button
              key={goal.goalId}
              type="button"
              className="goal-button"
              onClick={() => apply("addGoal", { goalId: goal.goalId })}
            >
              <div style={{ fontWeight: 600 }}>{goal.title}</div>
              <div className="muted">{goal.question}</div>
              <div className="muted">→ {goal.outcome} · {goal.trust}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="col">
        <div className="card">
          <h2>{views.form.title || "구간을 고르세요"}</h2>
          <div className="muted" style={{ marginBottom: 8 }}>
            {[views.form.trust && `검증 상태: ${views.form.trust}`, ...views.form.limitations]
              .filter(Boolean)
              .join("  |  ")}
          </div>
          <div className="row" style={{ flexWrap: "wrap", marginBottom: 8 }}>
            {views.modules.map((module) => (
              <button
                key={module.moduleId}
                className={module.moduleId === views.selectedModule ? "primary chip" : "chip"}
                onClick={() => select(module.moduleId)}
              >
                {module.position}. {module.title}
              </button>
            ))}
          </div>

          {views.form.moduleType === "qc" && (
            <div className="card" style={{ marginBottom: 10, background: "var(--panel-alt)" }}>
              <h2>급속충전 전류 (한 번에 계산)</h2>
              <div className="muted">
                전류만 입력하면 전압·시간을 함께 맞춥니다. 쉼표로 구분하세요 (예: 4, 3, 2).
              </div>
              <div className="row" style={{ marginTop: 6 }}>
                <input
                  className="grow"
                  placeholder="4, 3, 2"
                  value={qcRates}
                  onChange={(e) => setQcRates(e.target.value)}
                />
                <button
                  onClick={async () =>
                    setQcPreview(
                      await plan("qcFastCharge", {
                        moduleId: views.form.moduleId,
                        rates: qcRates.split(",").map(Number).filter((n) => !Number.isNaN(n)),
                      }),
                    )
                  }
                >
                  미리보기
                </button>
                <button
                  className="primary"
                  disabled={!qcPreview?.ok}
                  onClick={async () => {
                    await apply("applyQcFastCharge", {
                      moduleId: views.form.moduleId,
                      rates: qcRates.split(",").map(Number).filter((n) => !Number.isNaN(n)),
                    });
                    setQcPreview(null);
                    setQcRates("");
                  }}
                >
                  적용
                </button>
              </div>
              {qcPreview?.notes && (
                <div className="muted" style={{ marginTop: 6, whiteSpace: "pre-line" }}>
                  {qcPreview.notes.join("\n")}
                  {qcPreview.times ? `\n시간: ${qcPreview.times.join(" · ")} 초` : ""}
                </div>
              )}
              {qcPreview?.warnings && (
                <div className="warn" style={{ fontSize: 11, marginTop: 6, whiteSpace: "pre-line" }}>
                  {qcPreview.warnings.join("\n\n")}
                </div>
              )}
            </div>
          )}

          {views.form.derived.length > 0 && (
            <div className="card" style={{ marginBottom: 10, background: "var(--panel-alt)" }}>
              <h2>자동 계산</h2>
              {views.form.derived.map((value) => (
                <div key={value.label} className={value.severity === "error" ? "danger" : ""}>
                  {value.label}: {value.text}
                </div>
              ))}
            </div>
          )}

          {views.form.sections.map((section) => (
            <div key={section.title} style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 700, color: "var(--accent)" }}>{section.title}</div>
              {section.fields.map((field) => (
                <Field
                  key={field.key}
                  field={field}
                  presets={views.cRatePresets}
                  siblingCount={views.form.siblingCount}
                  onCommit={(key, text) =>
                    apply("setParam", { moduleId: views.form.moduleId, key, text })
                  }
                  onApplyAll={(key, text) =>
                    apply("applyToAllOfType", {
                      moduleType: views.form.moduleType,
                      key,
                      text,
                    })
                  }
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// --- 3. 절차 ---------------------------------------------------------------

export function ProcedureTab({ views, project, apply, select, plan }: TabProps) {
  const [days, setDays] = useState("14");
  const [steps, setSteps] = useState<Record<string, string>[]>([]);
  const [stepsShown, setStepsShown] = useState(false);
  const [step, setStep] = useState("50");
  const [budget, setBudget] = useState<{ ok?: boolean; totalCycles?: number; text?: string } | null>(null);
  const [kind, setKind] = useState("rest");

  return (
    <div className="col">
      <div className="card">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <strong>기간으로 정하기</strong>
          <input style={{ width: 60 }} value={days} onChange={(e) => setDays(e.target.value)} />
          <span className="muted">일 안에</span>
          <input style={{ width: 55 }} value={step} onChange={(e) => setStep(e.target.value)} />
          <span className="muted">사이클 단위로</span>
          <button
            onClick={async () =>
              setBudget(await plan("cycleBudget", { days: Number(days), step: Number(step) }))
            }
          >
            계산
          </button>
          <button
            className="primary"
            disabled={!budget?.ok}
            onClick={async () => {
              const target = views.modules.find((m) =>
                ["cycle_life", "insitu_cycle"].includes(m.moduleType),
              );
              if (target && budget?.totalCycles)
                await apply("setCycleCount", {
                  moduleId: target.moduleId,
                  count: budget.totalCycles,
                });
              setBudget(null);
            }}
          >
            {budget?.totalCycles ? `${budget.totalCycles} 사이클로 맞추기` : "맞추기"}
          </button>
          <span className="muted grow">{budget?.text ?? ""}</span>
        </div>
      </div>

      <div className="card">
        <h2>실행 순서 · {views.procedure.stepCount} 스텝</h2>
        <div className="table-scroll"><table>
          <thead>
            <tr><th>#</th><th>구간</th><th>스텝</th><th>범위</th><th>예상</th><th>검증</th><th /></tr>
          </thead>
          <tbody>
            {views.modules.map((module) => (
              <tr
                key={module.moduleId}
                style={{
                  background:
                    module.moduleId === views.selectedModule ? "var(--accent-soft)" : undefined,
                  cursor: "pointer",
                }}
                onClick={() => select(module.moduleId)}
              >
                <td>{module.position}</td>
                <td>{module.title}<div className="muted">{module.subtitle}</div></td>
                <td>{module.steps}</td>
                <td>{module.range}</td>
                <td>{module.duration}</td>
                <td className="muted">{module.trust}</td>
                <td>
                  <div className="row">
                    <button className="chip" onClick={(e) => { e.stopPropagation(); apply("move", { moduleId: module.moduleId, delta: -1 }); }}>▲</button>
                    <button className="chip" onClick={(e) => { e.stopPropagation(); apply("move", { moduleId: module.moduleId, delta: 1 }); }}>▼</button>
                    <button className="chip" onClick={(e) => { e.stopPropagation(); apply("detach", { moduleId: module.moduleId }); }}>분리</button>
                    <button className="chip" onClick={(e) => { e.stopPropagation(); apply("removeModule", { moduleId: module.moduleId }); }}>삭제</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>

      {views.canEditSteps && (
        <div className="card">
          <h2>개별 스텝 편집 · {views.customSteps.length}개</h2>
          <div className="row" style={{ marginBottom: 8 }}>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {["rest", "ocv", "cc_charge", "cccv_charge", "cv_charge", "cc_discharge"].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
            <button
              onClick={() =>
                apply("insertStep", {
                  moduleId: views.selectedModule,
                  index: views.customSteps.length,
                  kind,
                })
              }
            >
              맨 뒤에 추가
            </button>
            <span className="muted">END 는 항상 마지막이며 구간을 비울 수 없습니다.</span>
          </div>
          {views.customSteps.map((step) => (
            <div key={step.index} style={{ padding: 8, marginBottom: 6, background: "var(--panel-alt)", borderRadius: 6 }}>
              <div className="row">
                <strong>{step.number}. {step.stepType}{step.mode ? ` · ${step.mode}` : ""}</strong>
                <span className="muted grow">{step.label}</span>
                <button className="chip" onClick={() => apply("moveStep", { moduleId: views.selectedModule, index: step.index, delta: -1 })}>▲</button>
                <button className="chip" onClick={() => apply("moveStep", { moduleId: views.selectedModule, index: step.index, delta: 1 })}>▼</button>
                <button className="chip" onClick={() => apply("removeStep", { moduleId: views.selectedModule, index: step.index })}>삭제</button>
              </div>
              <div className="row" style={{ flexWrap: "wrap", marginTop: 4 }}>
                {step.fields.map((field) => (
                  <span key={field.key} className="row" style={{ gap: 3 }}>
                    <span className="muted">{field.label}</span>
                    <input
                      style={{ width: 96 }}
                      defaultValue={field.text}
                      onBlur={(e) =>
                        e.target.value !== field.text &&
                        apply("setStepField", {
                          moduleId: views.selectedModule,
                          index: step.index,
                          key: field.key,
                          text: e.target.value,
                        })
                      }
                    />
                    <span className="muted">{field.detail}</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div className="row">
          <h2 style={{ margin: 0 }}>장비 상세 보기 (읽기 전용)</h2>
          <span className="muted grow">{views.procedure.stepCount} 스텝</span>
          <button
            onClick={async () => {
              if (stepsShown) {
                setStepsShown(false);
                return;
              }
              setSteps((await api.steps(project)).steps);
              setStepsShown(true);
            }}
          >
            {stepsShown ? "접기" : "펼치기"}
          </button>
        </div>
        <div className="table-scroll" style={{ maxHeight: 320, display: stepsShown ? undefined : "none" }}>
          <table>
            <thead>
              <tr>{["number", "phase", "type", "mode", "current", "voltage", "end", "loop"].map((c) => (
                <th key={c}>{c}</th>
              ))}</tr>
            </thead>
            <tbody>
              {steps.map((row, index) => (
                <tr key={index}>
                  {["number", "phase", "type", "mode", "current", "voltage", "end", "loop"].map((c) => (
                    <td key={c}>{row[c]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// --- 4. 검증 ---------------------------------------------------------------

export function ValidateTab({ views, select }: TabProps) {
  const errors = views.validation.filter((row) => row.severity === "error");
  const warnings = views.validation.filter((row) => row.severity !== "error");

  return (
    <div className="col">
      <div className="card">
        <h2>오류 {errors.length}건 · 경고 {warnings.length}건</h2>
        {views.validation.length === 0 && <div className="muted">문제가 없습니다.</div>}
        {views.validation.map((row, index) => (
          <div
            key={index}
            style={{ padding: "6px 0", borderBottom: "1px solid var(--line)", cursor: row.moduleId ? "pointer" : undefined }}
            onClick={() => row.moduleId && select(row.moduleId)}
          >
            <div className={row.severity === "error" ? "danger" : "warn"}>
              [{row.severityLabel}] {row.location} — {row.message}
            </div>
            {row.remediation && <div className="muted">{row.remediation}</div>}
          </div>
        ))}
      </div>

      {views.unverified.length > 0 && (
        <div className="card">
          <h2>검증되지 않은 근거</h2>
          <div className="muted" style={{ whiteSpace: "pre-line" }}>
            {views.unverified.join("\n")}
          </div>
        </div>
      )}
    </div>
  );
}

// --- 5. 내보내기 -----------------------------------------------------------

export function ExportTab({ views, project, openImport }: TabProps) {
  const label = views.release.label;
  const [outDir, setOutDir] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<string[]>([]);

  async function runExport(kind: "draft_save" | "preview" | "review_candidate") {
    setBusy(true);
    setError("");
    setSaved([]);
    try {
      const result = await api.exportProject(project, kind, outDir.trim());
      setSaved(result.paths);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="col">
      <div className="card">
        <h2>진행 상태: {views.release.stageLabel}</h2>
        {label && (
          <div>
            <div>
              <strong>{label.label}</strong> ({label.labelKo})
              {label.equipmentExecutable && <span className="badge" style={{ marginLeft: 6 }}>장비 실행 가능</span>}
            </div>
            <div className="muted">{label.meaning}</div>
            {label.reasons.length > 0 && (
              <div className="muted" style={{ whiteSpace: "pre-line", marginTop: 4 }}>
                {label.reasons.map((r) => `· ${r}`).join("\n")}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h2>파일 저장 위치</h2>
        <p className="muted">초안, 미리보기와 검토용 SCH는 API가 실행 중인 PC의 비어 있는 폴더에 저장합니다.</p>
        <input className="import-path" aria-label="내보내기 폴더" placeholder="/path/to/empty-output-folder" value={outDir} onChange={(event) => setOutDir(event.target.value)} />
        {error && <p className="danger" role="alert">{error}</p>}
        {saved.length > 0 && <div className="import-note import-file" role="status">저장된 파일:<ul>{saved.map((path) => <li key={path}>{path}</li>)}</ul></div>}
      </div>

      {views.release.options.map((option) => (
        <div key={option.kind} className={option.recommended ? "card accent" : "card"}>
          <div className="row">
            <span className={option.allowed ? "status-dot available" : "status-dot"} aria-label={option.allowed ? "가능" : "잠김"} />
            <div className="grow">
              <div className="row">
                <strong className={option.danger && option.allowed ? "warn" : ""}>{option.title}</strong>
                {option.recommended && <span className="badge">권장</span>}
              </div>
              <div className="muted">{option.description}</div>
            </div>
            <button
              className={option.recommended ? "primary" : ""}
              disabled={!option.allowed || busy || (option.kind === "equipment_export") ||
                ((option.kind === "draft_save" || option.kind === "preview" || option.kind === "review_candidate") && !outDir.trim())}
              onClick={() => {
                if (option.kind === "template_patch") openImport?.();
                if (option.kind === "draft_save" || option.kind === "preview" || option.kind === "review_candidate") void runExport(option.kind);
              }}
            >
              {option.kind === "equipment_export" ? "별도 승인 절차" : option.kind === "template_patch" ? "기존 SCH 열기" : option.allowed ? "파일 생성" : "잠김"}
            </button>
          </div>
          {option.blockers.map((blocker, index) => (
            <div key={index} className="danger" style={{ fontSize: 11, marginTop: 4 }}>· {blocker}</div>
          ))}
          {!option.allowed && option.nextAction && (
            <div className="muted" style={{ marginTop: 4 }}>다음 단계: {option.nextAction}</div>
          )}
        </div>
      ))}
    </div>
  );
}
