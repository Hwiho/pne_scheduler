"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Json, type ModuleContent, type Views } from "@/lib/api";
import { isRepeatedUnitDetail, supportsUnitInput } from "@/lib/unitInput";
import { Field } from "./Field";
import { UnitInput } from "./UnitInput";

interface ModuleContentsProps {
  project: Json;
  moduleId: string;
  apply: (action: string, args?: Json) => Promise<void>;
  cRatePresets?: Views["cRatePresets"];
  busy?: boolean;
  childIndex?: number;
}

interface LoadedContentProps extends ModuleContentsProps {
  content: ModuleContent;
}

interface LoadedModuleContent {
  content: ModuleContent;
  sourceProject: Json;
  moduleId: string;
  childIndex?: number;
}

function useModuleContent(project: Json, moduleId: string, childIndex?: number) {
  const [loaded, setLoaded] = useState<LoadedModuleContent | null>(null);
  const [error, setError] = useState("");
  const epoch = useRef(0);

  useEffect(() => {
    const requestEpoch = ++epoch.current;
    let cancelled = false;
    setLoaded((current) => current?.moduleId === moduleId && current.childIndex === childIndex ? current : null);
    setError("");

    void api.moduleContent(project, moduleId, childIndex).then((result) => {
      if (!cancelled && requestEpoch === epoch.current) {
        setLoaded({ content: result, sourceProject: project, moduleId, childIndex });
      }
    }).catch((reason: unknown) => {
      if (!cancelled && requestEpoch === epoch.current) {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    });

    return () => {
      cancelled = true;
      epoch.current += 1;
    };
  }, [project, moduleId, childIndex]);

  const sameTarget = loaded?.moduleId === moduleId && loaded.childIndex === childIndex;
  const content = sameTarget && loaded ? loaded.content : null;
  const pending = !sameTarget || loaded?.sourceProject !== project;
  return { content, error, pending };
}

function isControlStep(step: ModuleContent["steps"][number]) {
  return /loop|cycle|repeat|end_loop|루프|반복/i.test(`${step.stepType} ${step.mode} ${step.title}`);
}

function StepField({
  field,
  disabled,
  onCommit,
}: {
  field: ModuleContent["steps"][number]["fields"][number];
  disabled: boolean;
  onCommit: (key: string, text: string) => void;
}) {
  const [draft, setDraft] = useState(field.text);
  const suppressNextBlur = useRef(false);

  useEffect(() => {
    setDraft(field.text);
    suppressNextBlur.current = false;
  }, [field.text]);

  const commit = () => {
    if (suppressNextBlur.current) {
      suppressNextBlur.current = false;
      return;
    }
    if (!disabled && draft !== field.text) onCommit(field.key, draft);
  };
  const showDetail = Boolean(field.detail && !isRepeatedUnitDetail(field.kind, field.text, field.detail));

  if (field.kind === "bool") {
    const checked = ["true", "yes", "예", "1"].includes(field.text.toLocaleLowerCase("ko"));
    return (
      <label className="module-contents-field module-contents-field-check">
        <span>{field.label}</span>
        <input
          type="checkbox"
          aria-label={field.label}
          checked={checked}
          disabled={disabled}
          onChange={(event) => onCommit(field.key, event.target.checked ? "예" : "아니오")}
        />
        {showDetail && <small>{field.detail}</small>}
      </label>
    );
  }

  return (
    <label className="module-contents-field">
      <span>{field.label}</span>
      {supportsUnitInput(field.kind) && field.numericValue !== undefined ? (
        <UnitInput
          kind={field.kind}
          value={field.text}
          numericValue={field.numericValue}
          disabled={disabled}
          inputLabel={field.label}
          onApply={(value) => onCommit(field.key, value)}
        />
      ) : (
        <input
          aria-label={field.label}
          value={draft}
          disabled={disabled}
          inputMode={field.kind === "number" ? "decimal" : undefined}
          onChange={(event) => {
            suppressNextBlur.current = false;
            setDraft(event.target.value);
          }}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              if (event.repeat) return;
              if (!disabled && draft !== field.text) onCommit(field.key, draft);
              suppressNextBlur.current = true;
              event.currentTarget.blur();
            }
            if (event.key === "Escape") {
              suppressNextBlur.current = true;
              setDraft(field.text);
              event.currentTarget.blur();
            }
          }}
        />
      )}
      {showDetail && <small>{field.detail}</small>}
    </label>
  );
}

function StepCards({ content, moduleId, childIndex, apply, busy = false }: LoadedContentProps) {
  const editable = content.customized;

  const commit = (stepIndex: number, key: string, text: string) => {
    if (childIndex === undefined) {
      void apply("setStepField", { moduleId, index: stepIndex, key, text });
    } else {
      void apply("setGroupChildStepField", { moduleId, childIndex, index: stepIndex, key, text });
    }
  };

  return (
    <div className="module-contents-steps" aria-label={`${content.title} 내부 스텝`}>
      {!editable && content.steps.length > 0 && (
        <div className="module-contents-readonly">
          <span>프리셋 원본 · 읽기 전용</span>
          <button
            type="button"
            disabled={busy}
            onClick={() => void apply(
              childIndex === undefined ? "detach" : "detachGroupChild",
              childIndex === undefined ? { moduleId } : { moduleId, index: childIndex },
            )}
          >개별 스텝 수정으로 전환</button>
        </div>
      )}
      {content.steps.map((step) => {
        const control = isControlStep(step);
        return (
          <section className={`module-contents-step${control ? " module-contents-control" : ""}`} key={`${step.index}-${step.number}`}>
            <div className="module-contents-step-heading">
              <span>{control ? "CONTROL" : `STEP ${step.number}`}</span>
              <strong>{step.title}</strong>
              <small>{step.mode || step.stepType}</small>
            </div>
            {step.summary && <p>{step.summary}</p>}
            {control ? (
              <div className="module-contents-control-note">LOOP / cycle 제어 스텝 · 순서와 경계는 프리셋 구조에서 관리됩니다.</div>
            ) : step.fields.length > 0 ? (
              <StepFields
                step={step}
                editable={editable}
                busy={busy}
                onCommit={(key, text) => commit(step.index, key, text)}
              />
            ) : null}
          </section>
        );
      })}
      {content.steps.length === 0 && <p className="module-contents-empty">표시할 내부 스텝이 없습니다.</p>}
    </div>
  );
}

function StepFields({
  step,
  editable,
  busy,
  onCommit,
}: {
  step: ModuleContent["steps"][number];
  editable: boolean;
  busy: boolean;
  onCommit: (key: string, text: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <details className="module-contents-field-details" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{editable ? "조건 편집" : "조건 보기"}<span>{step.fields.length}개 항목</span></summary>
      {open && (
        <div className="module-contents-fields">
          {step.fields.map((field) => (
            <StepField key={field.key} field={field} disabled={busy || !editable} onCommit={onCommit} />
          ))}
        </div>
      )}
    </details>
  );
}

function ChildCard({
  child,
  project,
  moduleId,
  apply,
  cRatePresets = [],
  busy = false,
}: LoadedContentProps & { child: ModuleContent["children"][number] }) {
  const [stepsOpen, setStepsOpen] = useState(false);
  const [paramsOpen, setParamsOpen] = useState(false);
  const canExpand = child.stepCount > 1 || ["sequence", "custom_steps"].includes(child.moduleType);

  return (
    <section className="module-contents-child">
      <div className="module-contents-child-heading">
        <span>{child.index + 1}</span>
        <div>
          <strong>{child.title}</strong>
          <small>{child.summary}</small>
        </div>
        <div className="module-contents-child-meta">
          {child.repeatCount > 1 && <b>×{child.repeatCount}</b>}
          <span>{child.stepCount}스텝</span>
        </div>
      </div>

      {child.form.sections.length > 0 && (
        <details className="module-contents-param-details" open={paramsOpen} onToggle={(event) => setParamsOpen(event.currentTarget.open)}>
          <summary>모듈 조건 편집<span>{child.form.sections.reduce((count, section) => count + section.fields.length, 0)}개 항목</span></summary>
          {paramsOpen && child.form.sections.map((section) => (
            <fieldset className="module-contents-params" key={section.title} disabled={busy}>
              <legend>{section.title}</legend>
              {section.fields.map((field) => (
                <Field
                  key={field.key}
                  field={field}
                  compact
                  disabled={busy}
                  presets={cRatePresets}
                  siblingCount={child.form.siblingCount}
                  onCommit={(key, text) => void apply("setGroupChildParam", { moduleId, index: child.index, key, text })}
                />
              ))}
            </fieldset>
          ))}
        </details>
      )}

      {canExpand && (
        <button
          type="button"
          className="module-contents-child-toggle"
          aria-expanded={stepsOpen}
          onClick={() => setStepsOpen((open) => !open)}
        >{stepsOpen ? "내부 스텝 접기" : "내부 스텝 보기"}<span aria-hidden="true">{stepsOpen ? "▴" : "▾"}</span></button>
      )}
      {stepsOpen && (
        <ModuleContents
          project={project}
          moduleId={moduleId}
          childIndex={child.index}
          apply={apply}
          cRatePresets={cRatePresets}
          busy={busy}
        />
      )}
    </section>
  );
}

function LoadedContents(props: LoadedContentProps) {
  const { content } = props;

  if (content.children.length > 0) {
    return (
      <div className="module-contents-children">
        {content.children.map((child) => <ChildCard key={`${child.index}-${child.moduleId}`} {...props} child={child} />)}
      </div>
    );
  }

  return <StepCards {...props} />;
}

/** Mounted only for an expanded module, so composition payloads remain lazy. */
export function ModuleContents(props: ModuleContentsProps) {
  const { content, error, pending } = useModuleContent(props.project, props.moduleId, props.childIndex);

  if (!content) {
    if (error) return <div className="module-contents-error" role="alert">구성을 불러오지 못했습니다: {error}</div>;
    return <div className="module-contents-loading" role="status">구성을 불러오는 중…</div>;
  }

  return (
    <>
      {pending && <div className="module-contents-refresh" role="status">최신 값 확인 중…</div>}
      {error && <div className="module-contents-error" role="alert">새 구성을 불러오지 못했습니다: {error}</div>}
      <LoadedContents {...props} busy={Boolean(props.busy || pending)} content={content} />
    </>
  );
}
