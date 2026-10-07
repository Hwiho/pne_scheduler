"use client";

// The workspace screens are pure views over the
// payload the API returned — no screen recomputes a gate or a validation result.

import { useEffect, useRef, useState } from "react";
import { api, type Json, type MethodSummary, type Views } from "@/lib/api";
import { isRepeatedUnitDetail, parsePositiveRateList, supportsUnitInput } from "@/lib/unitInput";
import { Field } from "./Field";
import { ModuleFlow } from "./ModuleFlow";
import { BatchExport } from "./BatchExport";
import { UnitInput } from "./UnitInput";
import { QpeedVoltageImport } from "./QpeedVoltageImport";

interface TabProps {
  views: Views;
  project: Json;
  apply: (action: string, args?: Json) => Promise<void>;
  select: (moduleId: string) => Promise<void>;
  plan: <T>(action: string, args?: Json) => Promise<T>;
  openImport?: () => void;
  busy?: boolean;
  libraryRevision?: number;
}

// --- 1. 설정 ---------------------------------------------------------------

export function SetupTab({ views, apply, busy }: TabProps) {
  return (
    <div className="card setup-card">
      <h2>셀과 장비</h2>
      {views.setupFields.map((field) => (
        <div className="setup-field" key={field.key}>
          <label htmlFor={`setup-${field.key}`}>{field.label}</label>
          {field.choices.length > 0 ? (
            <select
              id={`setup-${field.key}`}
              disabled={busy}
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
              key={field.value}
              disabled={busy}
              readOnly={field.readOnly}
              onBlur={(e) =>
                !field.readOnly &&
                e.target.value !== field.value &&
                (field.key === "name"
                  ? apply("setProjectName", { name: e.target.value })
                  : apply("setCellValue", { key: field.key, text: e.target.value }))
              }
              onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); event.currentTarget.blur(); } }}
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

export function ProtocolTab({ views, project, apply, select, plan, busy, libraryRevision = 0 }: TabProps) {
  const [goalsOpen, setGoalsOpen] = useState(false);
  const [days, setDays] = useState("14");
  const [step, setStep] = useState("50");
  const [budget, setBudget] = useState<{ ok?: boolean; totalCycles?: number; text?: string; source: Json } | null>(null);
  const [campaign, setCampaign] = useState({
    totalCycles: "200",
    rptEvery: "50",
    chargeCRate: "0.5",
    dischargeCRate: "0.5",
    dcirRates: "1.5",
    referenceCRate: "0.3333333333",
    startSoc: "100",
    preparationPolicy: "unconfirmed_entry",
  });
  const [preview, setPreview] = useState<{ ok?: boolean; blocks?: { title: string }[]; warnings?: string[]; errors?: string[] } | null>(null);
  const [qcRates, setQcRates] = useState("");
  const [qcPreview, setQcPreview] = useState<{ ok?: boolean; notes?: string[]; warnings?: string[]; times?: number[]; rates?: number[] } | null>(null);
  const [qcError, setQcError] = useState("");
  const qcRequest = useRef(0);
  const [budgetError, setBudgetError] = useState("");
  const [blockName, setBlockName] = useState("");
  const [blockMessage, setBlockMessage] = useState("");
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState("");
  const [methods, setMethods] = useState<MethodSummary[]>([]);
  const [methodId, setMethodId] = useState("");
  const [savedBlockRevision, setSavedBlockRevision] = useState(0);
  useEffect(() => {
    let cancelled = false;
    api.library().then((result) => {
      if (cancelled) return;
      setMethods(result.methods);
      setMethodId((previous) => result.methods.some((method) => method.methodId === previous) ? previous : result.methods[0]?.methodId ?? "");
    }).catch((error) => { if (!cancelled) setPlanError(error instanceof Error ? error.message : String(error)); });
    return () => { cancelled = true; };
  }, [libraryRevision, savedBlockRevision]);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const inspectorRef = useRef<HTMLDivElement>(null);
  const selectedRow = views.modules.find((module) => module.moduleId === views.selectedModule);
  async function editModule(moduleId: string) {
    await select(moduleId);
    setInspectorOpen(true);
    requestAnimationFrame(() => inspectorRef.current?.focus({ preventScroll: true }));
  }
  useEffect(() => {
    if (!inspectorOpen) return;
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setInspectorOpen(false); };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [inspectorOpen]);
  useEffect(() => { qcRequest.current += 1; setPreview(null); setQcPreview(null); setQcError(""); setBlockMessage(""); }, [project, views.selectedModule]);
  const cycleTarget = views.modules.find((m) => m.moduleId === views.selectedModule && ["cycle_life", "insitu_cycle"].includes(m.moduleType))
    ?? views.modules.find((m) => ["cycle_life", "insitu_cycle"].includes(m.moduleType));

  const options = () => ({
    totalCycles: Number(campaign.totalCycles) || 0,
    rptEvery: Number(campaign.rptEvery) || 0,
    chargeCRate: Number(campaign.chargeCRate) || 0,
    dischargeCRate: Number(campaign.dischargeCRate) || 0,
    dcirRates: [Number(campaign.dcirRates)],
    referenceCRate: Number(campaign.referenceCRate),
    startSoc: Number(campaign.startSoc) / 100,
    preparationPolicy: campaign.preparationPolicy,
  });

  return (
    <div className="col">
    <div className="protocol-overview">
      <div>
        <span className="eyebrow">BUILD YOUR TEST</span>
        <h2>프로토콜 설계</h2>
        <p>목적으로 시작하거나 프로토콜을 직접 추가한 뒤, 구간별 조건과 실행 순서를 한 화면에서 조정하세요.</p>
      </div>
      <div className="protocol-stats" aria-label="현재 일정 요약">
        <div><strong>{views.modules.length}</strong><span>구간</span></div>
        <div><strong>{views.summary.totalSteps}</strong><span>스텝</span></div>
        <div><strong className="duration-stat" title={views.summary.durationText}>{views.summary.durationText.replace(/\s*\(근사\)/, "")}</strong><span>예상 시간 · 근사</span></div>
      </div>
    </div>
    <div className="protocol-editor">
    <ModuleFlow views={views} project={project} apply={apply} select={select} onEdit={editModule} busy={busy} />
    <div className="protocol-grid">
      <div className="col protocol-tools">
        <div className="card">
          <h2>내 블록 · 저장된 방법</h2>
          <p className="muted">저장된 블록을 현재 실험 끝에 추가합니다. 장비가 다르면 경고되므로 설정·전류 한계를 다시 확인하세요.</p>
          <button disabled={busy || planning} onClick={async () => {
            setPlanning(true); setPlanError("");
            try { const result = await api.library(); setMethods(result.methods); setMethodId(result.methods[0]?.methodId ?? ""); }
            catch (error) { setPlanError(error instanceof Error ? error.message : String(error)); }
            finally { setPlanning(false); }
          }}>저장 목록 새로고침</button>
          {methods.length > 0 && <div className="col" style={{ marginTop: 10 }}>
            <select aria-label="저장된 블록 선택" value={methodId} onChange={(event) => setMethodId(event.target.value)} disabled={busy || planning}>
              {methods.map((method) => <option key={method.methodId} value={method.methodId}>{method.label} · {method.moduleCount}개 구간</option>)}
            </select>
            <button className="primary" disabled={busy || planning || !methodId} onClick={() => { void apply("loadMethod", { methodId }); }}>현재 실험에 추가</button>
          </div>}
        </div>
        <div className="card">
          <h2>사이클 + RPT 캠페인</h2>
          {(
            [
              ["총 사이클", "totalCycles"],
              ["RPT 주기", "rptEvery"],
              ["충전율", "chargeCRate"],
              ["방전율", "dischargeCRate"],
              ["DC-IR 전류", "dcirRates"],
              ["RPT 기준 방전율", "referenceCRate"],
              ["RPT 시작 SOC", "startSoc"],
            ] as const
          ).map(([label, key]) => (
            <div className="row campaign-row" key={key}>
              <label className="muted" htmlFor={`campaign-${key}`}>{label}</label>
              <input
                id={`campaign-${key}`}
                disabled={busy || planning}
                className="grow"
                value={campaign[key]}
                onChange={(e) => { setCampaign({ ...campaign, [key]: e.target.value }); setPreview(null); }}
              />
              {key === "startSoc" && <span className="muted">%</span>}
            </div>
          ))}
          <label className="muted" htmlFor="campaign-preparation">RPT 진입 상태</label>
          <select id="campaign-preparation" value={campaign.preparationPolicy} disabled={busy || planning} onChange={(event) => { setCampaign({ ...campaign, preparationPolicy: event.target.value }); setPreview(null); }}>
            <option value="unconfirmed_entry">아직 확인하지 않음</option>
            <option value="user_confirmed_start_soc">입력한 시작 SOC를 직접 확인함</option>
            <option value="charge_to_full">각 RPT 앞에 완충·휴지 준비 구간 추가</option>
          </select>
          <p className="muted">DC-IR은 전류 하나를 사용합니다. ‘준비 구간 추가’를 선택한 경우에만 RPT 앞에 기준율 CCCV 충전·휴지를 넣습니다. 이때 시작 SOC는 100%입니다.</p>
          <div className="row" style={{ marginTop: 8 }}>
            <button disabled={busy || planning} onClick={async () => {
              setPlanning(true); setPlanError("");
              try { setPreview(await plan("campaign", options())); }
              catch (error) { setPlanError(error instanceof Error ? error.message : String(error)); }
              finally { setPlanning(false); }
            }}>
              미리보기
            </button>
            <button
              className="primary"
              disabled={busy || planning || !preview?.ok || !preview.blocks?.length}
              onClick={async () => {
                await apply("addCampaign", options());
                setPreview(null);
              }}
            >
              추가
            </button>
          </div>
          {planError && <p role="alert" className="danger">{planError}</p>}
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
          {preview?.errors && preview.errors.length > 0 && (
            <div className="danger" role="alert" style={{ fontSize: 12, marginTop: 6, whiteSpace: "pre-line" }}>
              {preview.errors.join("\n")}
            </div>
          )}
        </div>

        <div className="card">
          <button
            type="button"
            className="picker-toggle"
            aria-expanded={goalsOpen}
            aria-controls="goal-options"
            onClick={() => setGoalsOpen((open) => !open)}
          >
            <span>무엇을 알고 싶으신가요?</span>
            <span aria-hidden="true">{goalsOpen ? "▴" : "▾"}</span>
          </button>
          {goalsOpen && <div id="goal-options" className="goal-list" role="group" aria-label="실험 목적 목록">
          {views.goals.map((goal) => (
            <button
              key={goal.goalId}
              type="button"
              className="goal-button"
              disabled={busy}
              onClick={async () => {
                await apply("addGoal", { goalId: goal.goalId });
                setGoalsOpen(false);
              }}
            >
              <div style={{ fontWeight: 600 }}>{goal.title}</div>
              <div className="muted">{goal.question}</div>
              <div className="muted">→ {goal.outcome} · {goal.trust}</div>
            </button>
          ))}
          </div>}
        </div>

        <div className="card">
          <h2>기간 기준 사이클 계산</h2>
          <p className="muted">현재 프로토콜의 예상 시간을 기준으로 가능한 사이클 수를 계산합니다. 근사치이므로 실제 장비 시간과 다를 수 있습니다.</p>
          <div className="row budget-controls">
            <label htmlFor="budget-days">기간 (일)</label>
            <input id="budget-days" type="number" min="1" value={days} onChange={(e) => { setDays(e.target.value); setBudget(null); }} />
            <label htmlFor="budget-step">사이클 간격</label>
            <input id="budget-step" type="number" min="1" value={step} onChange={(e) => { setStep(e.target.value); setBudget(null); }} />
            <button disabled={busy || planning || !cycleTarget || !Number.isFinite(Number(days)) || Number(days) <= 0 || !Number.isInteger(Number(step)) || Number(step) <= 0} onClick={async () => {
              if (!cycleTarget) return;
              setPlanning(true); setBudgetError(""); setBudget(null);
              try {
                const result = await plan<{ ok?: boolean; totalCycles?: number; text?: string }>("cycleBudget", { days: Number(days), step: Number(step), moduleId: cycleTarget.moduleId });
                setBudget({ ...result, source: project });
              } catch (error) { setBudgetError(error instanceof Error ? error.message : String(error)); }
              finally { setPlanning(false); }
            }}>계산</button>
          </div>
          {budgetError && <p className="danger" role="alert">{budgetError}</p>}
          {budget?.source === project && budget.text && <p className="muted" role="status">{budget.text}</p>}
          {budget?.source === project && budget.ok && budget.totalCycles && cycleTarget && (
            <button className="primary" onClick={async () => {
              await apply("setCycleCount", { moduleId: cycleTarget.moduleId, count: budget.totalCycles });
              setBudget(null);
            }}>{budget.totalCycles} 사이클로 맞추기</button>
          )}
          {!cycleTarget && <p className="muted">먼저 수명 사이클 프로토콜을 추가하세요.</p>}
        </div>
      </div>

      <div className="col protocol-inspector" data-open={inspectorOpen} ref={inspectorRef} tabIndex={-1} role="region" aria-label="선택한 모듈 조건 편집">
        <div className="card">
          <div className="inspector-heading">
            <div><span className="eyebrow">MODULE SETTINGS</span><h2>{selectedRow?.title || views.form.title || "구간을 고르세요"}</h2></div>
            <button type="button" className="inspector-close" onClick={() => setInspectorOpen(false)} aria-label="조건 편집 닫기">×</button>
          </div>
          <details className="parameter-help">
          <summary>검증 상태·제한 사항</summary><div className="muted" style={{ marginBottom: 8 }}>
            {[views.form.trust && `검증 상태: ${views.form.trust}`, ...views.form.limitations]
              .filter(Boolean)
              .join("  |  ")}
          </div>
          </details>
          <p className="muted inspector-hint">값을 입력한 뒤 Enter 또는 다른 항목을 누르면 반영됩니다. 박스에서도 변경된 조건을 확인하세요.</p>
          {views.form.moduleId && <details className="preset-save">
            <summary>선택한 모듈을 내 프리셋으로 저장</summary>
            <p className="muted">선택한 박스와 내부 구성을 저장합니다. 원본 실험 프리셋은 바뀌지 않습니다.</p>
            <div className="row" style={{ flexWrap: "wrap" }}>
              <input aria-label="저장할 블록 이름" className="grow" value={blockName} onChange={(event) => setBlockName(event.target.value)} placeholder="예: 내 Derating 레시피" maxLength={120} disabled={busy || planning} />
              <button disabled={busy || planning || !blockName.trim()} onClick={async () => {
                setPlanning(true); setBlockMessage("");
                try { await api.saveMethod(project, blockName.trim(), "사용자 실험 프리셋", [views.form.moduleId]); setBlockMessage("선택한 모듈을 내 프리셋에 저장했습니다."); setSavedBlockRevision((revision) => revision + 1); }
                catch (error) { setBlockMessage(error instanceof Error ? error.message : String(error)); }
                finally { setPlanning(false); }
              }}>이 블록 저장</button>
            </div>
            {blockMessage && <p role="status">{blockMessage}</p>}
          </details>}

          {views.form.moduleType === "qc" && (
            <div className="card" style={{ marginBottom: 10, background: "var(--panel-alt)" }}>
              <h2>급속충전 전류 (한 번에 계산)</h2>
              <div className="muted">
                전류만 입력하면 전압·시간을 함께 맞춥니다. 쉼표로 구분하세요 (예: 4, 3, 2).
              </div>
              <div className="row" style={{ marginTop: 6 }}>
                <input
                  className="grow"
                  aria-label="QC 단계별 충전율"
                  placeholder="4, 3, 2"
                  disabled={busy || planning}
                  value={qcRates}
                  onChange={(e) => { qcRequest.current += 1; setQcRates(e.target.value); setQcPreview(null); setQcError(""); }}
                />
                <button
                  disabled={busy || planning || !qcRates.trim()}
                  onClick={async () => {
                    const ticket = ++qcRequest.current;
                    setPlanning(true); setQcError(""); setQcPreview(null);
                    try {
                      const rates = parsePositiveRateList(qcRates);
                      const result = await plan<{ ok?: boolean; notes?: string[]; warnings?: string[]; times?: number[] }>("qcFastCharge", { moduleId: views.form.moduleId, rates });
                      if (ticket === qcRequest.current) setQcPreview({ ...result, rates });
                    } catch (error) { if (ticket === qcRequest.current) setQcError(error instanceof Error ? error.message : String(error)); }
                    finally { setPlanning(false); }
                  }}
                >
                  미리보기
                </button>
                <button
                  className="primary"
                  disabled={busy || planning || !qcPreview?.ok || !qcPreview.rates?.length}
                  onClick={async () => {
                    await apply("applyQcFastCharge", {
                      moduleId: views.form.moduleId,
                      rates: qcPreview?.rates,
                    });
                    setQcPreview(null);
                    setQcRates("");
                  }}
                >
                  적용
                </button>
              </div>
              {qcError && <p className="danger" role="alert">{qcError}</p>}
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

          {views.form.moduleType === "qpeed" && <QpeedVoltageImport key={views.form.moduleId} project={project} moduleId={views.form.moduleId} disabled={busy} apply={apply} plan={plan} />}
          {views.form.derived.length > 0 && (
            <div className="card" style={{ marginBottom: 10, background: "var(--panel-alt)" }}>
              <h2>자동 계산</h2>
              {views.form.derived.map((value) => (
                <div key={value.label} className={value.severity === "error" ? "danger" : ""}>
                  {value.label}: {value.text}
                  {value.help && <div className="muted" style={{fontSize:11, marginBottom:6}}>{value.help}</div>}
                </div>
              ))}
            </div>
          )}

          {views.form.sections.map((section) => (
            <div key={section.title} style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 700, color: "var(--accent)" }}>{section.title}</div>
              {section.fields.map((field) => (
                <Field
                  key={`${views.form.moduleId}-${field.key}`}
                  field={field}
                  disabled={busy}
                  compact
                  presets={views.cRatePresets}
                  siblingCount={views.form.moduleType === "primitive" ? 1 : views.form.siblingCount}
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
          {(views.groupChildren ?? []).map(({ index, form }) => <details key={`${views.form.moduleId}-${index}`} className="card" style={{ marginTop: 10 }}>
            <summary>{index + 1}. {form.title} · 내부 조건 편집</summary>
            {form.sections.map((section) => <div key={section.title}>
              <h3>{section.title}</h3>
              {section.fields.map((field) => <Field key={field.key} field={field} compact disabled={busy} presets={views.cRatePresets} onCommit={(key, text) => { void apply("setGroupChildParam", { moduleId: views.form.moduleId, index, key, text }); }} />)}
            </div>)}
          </details>)}
        </div>
      </div>
    </div>
    </div>
    <ProcedureTab views={views} project={project} apply={apply} select={select} plan={plan} />
    </div>
  );
}

// --- 3. 절차 ---------------------------------------------------------------

export function ProcedureTab({ views, project, apply, select }: TabProps) {
  const [steps, setSteps] = useState<Record<string, string>[]>([]);
  const [stepsShown, setStepsShown] = useState(false);
  const [stepsError, setStepsError] = useState("");
  const [kind, setKind] = useState("rest");

  useEffect(() => {
    if (!stepsShown) return;
    let cancelled = false;
    api.steps(project).then((result) => {
      if (!cancelled) { setSteps(result.steps); setStepsError(""); }
    }).catch((error: unknown) => {
      if (!cancelled) setStepsError(error instanceof Error ? error.message : String(error));
    });
    return () => { cancelled = true; };
  }, [project, stepsShown]);

  return (
    <div className="col">
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
                    {supportsUnitInput(field.kind) && field.numericValue !== undefined ? (
                      <UnitInput
                        kind={field.kind}
                        value={field.text}
                        numericValue={field.numericValue}
                        inputLabel={field.label}
                        onApply={(value) => void apply("setStepField", {
                          moduleId: views.selectedModule,
                          index: step.index,
                          key: field.key,
                          text: value,
                        })}
                      />
                    ) : (
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
                    )}
                    {!isRepeatedUnitDetail(field.kind, field.text, field.detail) && <span className="muted">{field.detail}</span>}
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
          <button onClick={() => setStepsShown((shown) => !shown)}>
            {stepsShown ? "접기" : "펼치기"}
          </button>
        </div>
        {stepsError && <p className="danger" role="alert">{stepsError}</p>}
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

// --- 내보내기 ---------------------------------------------------------------

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
      <details className="card">
        <summary>실험 요약 · 전류·순서·예상 시간</summary>
        <p className="muted" style={{ whiteSpace: "pre-line" }}>{views.summary.text}</p>
        <p className="muted">기준용량 {String((project.cell_profile as Json)?.nominal_capacity_mAh ?? "—")} mAh · 예상 시간은 CV 구간과 장비 지연을 완전히 예측하지 못합니다.</p>
      </details>
      {(views.validation.length > 0 || views.unverified.length > 0) && (
        <details className="card export-checks" open={views.validation.some((row) => row.severity === "error")}>
          <summary>내보내기 전 확인 · 오류 {views.validation.filter((row) => row.severity === "error").length}건 · 경고 {views.validation.filter((row) => row.severity !== "error").length}건</summary>
          {views.validation.map((row, index) => (
            <p key={index} className={row.severity === "error" ? "danger" : "warn"}>
              [{row.severityLabel}] {row.location} — {row.message}
              {row.remediation && <span className="muted"> · {row.remediation}</span>}
            </p>
          ))}
          {views.unverified.length > 0 && <p className="muted">미확인 근거: {views.unverified.join(" · ")}</p>}
        </details>
      )}
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
        <p className="muted">API가 실행 중인 PC의 새 폴더 또는 빈 폴더에 저장합니다. 새 폴더는 자동으로 만들며 기존 파일은 덮어쓰지 않습니다. 프로젝트만 보관하려면 위의 ‘프로젝트 다운로드’를 사용할 수 있습니다.</p>
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
      <BatchExport project={project} />
    </div>
  );
}
