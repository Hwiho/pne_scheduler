/* ============================================================
   app.js  —  Battery Scheduler frontend logic
   ============================================================ */

mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "loose" });

// ── Block metadata ────────────────────────────────────────────────────────
const BLOCK_META = {
  rest: {
    label: "REST",
    icon:  "bi-pause-circle",
    iconClass: "icon-rest",
    summary: p => `${p.duration_min}분  |  기록 ${p.record_time_s}s / ΔV ${p.voltage_change_mV}mV`,
    defaults: { duration_min: 30, record_time_s: 30, voltage_change_mV: 10.0 },
    fields: [
      { key:"duration_min",       label:"휴지 시간 (분)",        type:"number", min:0,   step:1 },
      { key:"record_time_s",      label:"기록 주기 (초)",        type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV",  label:"전압 변화 기록 (mV)",   type:"number", min:0,   step:1 },
    ]
  },

  capacity_check: {
    label: "Capacity Check",
    icon:  "bi-rulers",
    iconClass: "icon-capacity_check",
    summary: p => `${p.charge_c_rate}C 충 / ${p.discharge_c_rate}C 방`,
    defaults: {
      charge_c_rate: 0.1, charge_voltage_V: 4.2,
      cv_cutoff_c: 0.05,  time_limit_h: 48,
      discharge_c_rate: 0.1, discharge_voltage_V: 2.5,
      rest_after_charge_min: 30, rest_after_discharge_min: 30,
      record_time_s: 30, voltage_change_mV: 10.0
    },
    fields: [
      { section: "충전 (CCCV)" },
      { key:"charge_c_rate",    label:"충전 C-rate",            type:"number", min:0,   step:0.01 },
      { key:"charge_voltage_V", label:"충전 전압 (V)",           type:"number", min:0,   step:0.1 },
      { key:"cv_cutoff_c",      label:"CV 컷오프 C-rate",        type:"number", min:0,   step:0.01 },
      { key:"time_limit_h",     label:"최대 충전 시간 (h)",       type:"number", min:0,   step:1 },
      { key:"rest_after_charge_min",    label:"충전 후 Rest (분)", type:"number", min:0, step:1 },
      { section: "방전 (CC)" },
      { key:"discharge_c_rate",     label:"방전 C-rate",         type:"number", min:0,   step:0.01 },
      { key:"discharge_voltage_V",  label:"방전 컷오프 (V)",      type:"number", min:0,   step:0.1 },
      { key:"rest_after_discharge_min", label:"방전 후 Rest (분)", type:"number", min:0, step:1 },
      { section: "공통" },
      { key:"record_time_s",     label:"기록 주기 (초)",          type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV", label:"전압 변화 기록 (mV)",     type:"number", min:0,   step:1 },
    ]
  },

  soc_setting: {
    label: "SOC Setting",
    icon:  "bi-percent",
    iconClass: "icon-soc_setting",
    summary: p => `SOC ${p.target_soc_percent}%`,
    defaults: {
      target_soc_percent: 50,
      c_rate: 0.2, charge_voltage_V: 4.2,
      cv_cutoff_c: 0.05, discharge_voltage_V: 2.5,
      time_limit_h: 48, rest_min: 30,
      record_time_s: 30, voltage_change_mV: 10.0,
      capacity_ref_block_id: ""
    },
    fields: [
      { key:"capacity_ref_block_id", label:"용량 기준 Capacity Check", type:"block_ref", filter_type:"capacity_check" },
      { key:"target_soc_percent", label:"목표 SOC (%)",          type:"number", min:1, max:99, step:1 },
      { key:"c_rate",             label:"충·방전 C-rate",         type:"number", min:0, step:0.01 },
      { key:"charge_voltage_V",   label:"충전 전압 (V)",          type:"number", min:0, step:0.1 },
      { key:"cv_cutoff_c",        label:"CV 컷오프 C-rate",       type:"number", min:0, step:0.01 },
      { key:"discharge_voltage_V",label:"방전 컷오프 (V)",         type:"number", min:0, step:0.1 },
      { key:"time_limit_h",       label:"최대 시간 제한 (h)",      type:"number", min:0, step:1 },
      { key:"rest_min",           label:"안정화 Rest (분)",        type:"number", min:0, step:1 },
      { key:"record_time_s",      label:"기록 주기 (초)",          type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV",  label:"전압 변화 기록 (mV)",     type:"number", min:0, step:1 },
    ]
  },

  charge: {
    label: "Charge",
    icon:  "bi-battery-charging",
    iconClass: "icon-charge",
    summary: p => `${p.charge_mode==="cc"?"CC":"CCCV"} ${p.charge_c_rate}C × ${p.count}회`,
    defaults: {
      count: 1,
      charge_mode: "cccv",
      charge_c_rate: 0.5, charge_voltage_V: 4.2,
      cv_cutoff_c: 0.05, time_limit_h: 48,
      rest_min: 30,
      record_time_s: 30, voltage_change_mV: 10.0
    },
    fields: [
      { key:"count",          label:"반복 횟수",              type:"number", min:1, step:1 },
      { section:"충전 조건" },
      { key:"charge_mode",    label:"충전 방식",
        type:"select",
        options:[
          { value:"cccv", label:"CCCV (CC 후 CV 보충)" },
          { value:"cc",   label:"CC만 (CV 없음)" }
        ]
      },
      { key:"charge_c_rate",    label:"충전 C-rate",           type:"number", min:0, step:0.01 },
      { key:"charge_voltage_V", label:"충전 전압 (V)",          type:"number", min:0, step:0.1 },
      { key:"cv_cutoff_c",      label:"CV 컷오프 C-rate",       type:"number", min:0, step:0.01,
        showIf:{key:"charge_mode",val:"cccv"} },
      { key:"time_limit_h",     label:"최대 충전 시간 (h)",      type:"number", min:0, step:1 },
      { key:"rest_min",         label:"충전 후 Rest (분)",       type:"number", min:0, step:1 },
      { section:"공통" },
      { key:"record_time_s",    label:"기록 주기 (초)",          type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV",label:"전압 변화 기록 (mV)",     type:"number", min:0, step:1 },
    ]
  },

  discharge: {
    label: "Discharge",
    icon:  "bi-battery",
    iconClass: "icon-discharge",
    summary: p => `CC ${p.discharge_c_rate}C → ${p.discharge_voltage_V}V × ${p.count}회`,
    defaults: {
      count: 1,
      discharge_c_rate: 0.5, discharge_voltage_V: 2.5,
      rest_min: 30,
      record_time_s: 30, voltage_change_mV: 10.0
    },
    fields: [
      { key:"count",              label:"반복 횟수",              type:"number", min:1, step:1 },
      { section:"방전 조건 (CC)" },
      { key:"discharge_c_rate",   label:"방전 C-rate",            type:"number", min:0, step:0.01 },
      { key:"discharge_voltage_V",label:"방전 컷오프 (V)",         type:"number", min:0, step:0.1 },
      { key:"rest_min",           label:"방전 후 Rest (분)",       type:"number", min:0, step:1 },
      { section:"공통" },
      { key:"record_time_s",      label:"기록 주기 (초)",          type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV",  label:"전압 변화 기록 (mV)",     type:"number", min:0, step:1 },
    ]
  },

  cycle: {
    label: "Cycle",
    icon:  "bi-arrow-repeat",
    iconClass: "icon-cycle",
    summary: p => `${p.count}사이클  |  ${p.charge_mode==="cc"?"CC":"CCCV"} ${p.charge_c_rate}C 충 / CC ${p.discharge_c_rate}C 방`,
    defaults: {
      count: 50,
      charge_mode: "cccv",
      charge_c_rate: 0.5, charge_voltage_V: 4.2,
      cv_cutoff_c: 0.05,  time_limit_h: 48,
      discharge_c_rate: 0.5, discharge_voltage_V: 2.5,
      rest_after_charge_min: 30, rest_after_discharge_min: 30,
      record_time_s: 30, voltage_change_mV: 10.0
    },
    fields: [
      { key:"count", label:"사이클 수", type:"number", min:1, step:1 },
      { section:"충전" },
      { key:"charge_mode", label:"충전 방식",
        type:"select",
        options:[
          { value:"cccv", label:"CCCV (CC 후 CV 보충)" },
          { value:"cc",   label:"CC만 (CV 없음)" }
        ]
      },
      { key:"charge_c_rate",    label:"충전 C-rate",              type:"number", min:0, step:0.01 },
      { key:"charge_voltage_V", label:"충전 전압 (V)",             type:"number", min:0, step:0.1 },
      { key:"cv_cutoff_c",      label:"CV 컷오프 C-rate",          type:"number", min:0, step:0.01, showIf:{key:"charge_mode",val:"cccv"} },
      { key:"time_limit_h",     label:"최대 충전 시간 (h)",         type:"number", min:0, step:1 },
      { key:"rest_after_charge_min",    label:"충전 후 Rest (분)",  type:"number", min:0, step:1 },
      { section:"방전 (CC)" },
      { key:"discharge_c_rate",         label:"방전 C-rate",       type:"number", min:0, step:0.01 },
      { key:"discharge_voltage_V",      label:"방전 컷오프 (V)",    type:"number", min:0, step:0.1 },
      { key:"rest_after_discharge_min", label:"방전 후 Rest (분)",  type:"number", min:0, step:1 },
      { section:"공통" },
      { key:"record_time_s",      label:"기록 주기 (초)",           type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV",  label:"전압 변화 기록 (mV)",      type:"number", min:0, step:1 },
    ]
  },

  rate_test: {
    label: "Rate Test",
    icon:  "bi-speedometer2",
    iconClass: "icon-rate_test",
    summary: p => `CC 충전 / ${(p.c_rates||[]).map(g=>g.c_rate+"C").join(" → ")} 방전`,
    defaults: {
      charge_voltage_V: 4.2, time_limit_h: 48,
      discharge_voltage_V: 2.5,
      rest_after_charge_min: 30, rest_after_discharge_min: 30,
      record_time_s: 30, voltage_change_mV: 10.0,
      c_rates: [
        { c_rate: 0.1, count: 2 },
        { c_rate: 0.2, count: 1 },
        { c_rate: 0.5, count: 1 },
        { c_rate: 1.0, count: 1 },
      ]
    },
    fields: [
      // c_rates handled via renderCRateTable
      { section:"충방전 조건 (CC 충전 / CC 방전)" },
      { key:"charge_voltage_V",         label:"충전 전압 (V)",         type:"number", min:0, step:0.1 },
      { key:"time_limit_h",             label:"최대 충전 시간 (h)",     type:"number", min:0, step:1 },
      { key:"discharge_voltage_V",      label:"방전 컷오프 (V)",        type:"number", min:0, step:0.1 },
      { key:"rest_after_charge_min",    label:"충전 후 Rest (분)",      type:"number", min:0, step:1 },
      { key:"rest_after_discharge_min", label:"방전 후 Rest (분)",      type:"number", min:0, step:1 },
      { section:"공통" },
      { key:"record_time_s",     label:"기록 주기 (초)",                type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV", label:"전압 변화 기록 (mV)",           type:"number", min:0,   step:1 },
    ]
  },

  pulse_test: {
    label: "Pulse Test (HPPC)",
    icon:  "bi-activity",
    iconClass: "icon-pulse_test",
    summary: p => {
      const socStr = p.soc_mode==="interval"
        ? `SOC ${p.soc_interval_percent}%마다`
        : `SOC [${(p.soc_points||[]).join(",")}]%`;
      return `${socStr}  |  ${p.pulse_c_rate}C × ${p.pulse_duration_s}s`;
    },
    defaults: {
      soc_mode: "interval",
      soc_interval_percent: 10,
      soc_points: [80, 60, 40, 20],
      pulse_c_rate: 1.5,
      pulse_duration_s: 30,
      return_pulse: true,
      return_c_rate: 0.1,
      stabilization_min: 60,
      recovery_min: 30,
      record_time_pulse_s: 1,
      record_time_rest_s: 30,
      voltage_change_mV: 10.0,
      charge_c_rate: 0.2,
      charge_voltage_V: 4.2,
      cv_cutoff_c: 0.05,
      discharge_voltage_V: 2.5,
      soc_step_c_rate: 0.1,
      time_limit_h: 48,
      rest_min: 30,
      capacity_ref_block_id: ""
    },
    fields: [
      { section:"SOC 조정 기준" },
      { key:"capacity_ref_block_id", label:"SOC 조정 기준 Capacity Check", type:"block_ref", filter_type:"capacity_check" },
      { section:"SOC 설정" },
      { key:"soc_mode", label:"SOC 선택 방식",
        type:"select",
        options:[
          { value:"interval", label:"일정 간격 (예: 10%마다)" },
          { value:"specific", label:"특정 SOC 지점 지정" }
        ]
      },
      { key:"soc_interval_percent", label:"SOC 간격 (%)", type:"number", min:1, max:50, step:1,
        showIf:{key:"soc_mode",val:"interval"} },
      { key:"soc_points_str", label:"SOC 지점 (쉼표 구분, 내림차순)", type:"text",
        showIf:{key:"soc_mode",val:"specific"} },
      { section:"펄스 조건" },
      { key:"pulse_c_rate",     label:"펄스 C-rate (방전)",       type:"number", min:0,   step:0.1 },
      { key:"pulse_duration_s", label:"펄스 시간 (초)",           type:"number", min:1,   step:1 },
      { key:"return_pulse",     label:"복귀 충전 포함",           type:"checkbox" },
      { key:"return_c_rate",    label:"복귀 충전 C-rate",         type:"number", min:0,   step:0.01,
        showIf:{key:"return_pulse",val:true} },
      { key:"stabilization_min",label:"측정 전 안정화 Rest (분)", type:"number", min:0,   step:1 },
      { key:"recovery_min",     label:"측정 후 회복 Rest (분)",   type:"number", min:0,   step:1 },
      { key:"record_time_pulse_s", label:"펄스 기록 주기 (초)",  type:"number", min:0.1, step:0.1 },
      { key:"record_time_rest_s",  label:"Rest 기록 주기 (초)",  type:"number", min:0.1, step:1 },
      { key:"voltage_change_mV",   label:"전압 변화 기록 (mV)",  type:"number", min:0,   step:1 },
      { section:"SOC 이동 / 초기 충전" },
      { key:"soc_step_c_rate",     label:"SOC 이동 C-rate (방전)", type:"number", min:0, step:0.01 },
      { key:"charge_c_rate",       label:"충전 C-rate",           type:"number", min:0,   step:0.01 },
      { key:"charge_voltage_V",    label:"충전 전압 (V)",          type:"number", min:0,   step:0.1 },
      { key:"cv_cutoff_c",         label:"CV 컷오프 C-rate",       type:"number", min:0,   step:0.01 },
      { key:"discharge_voltage_V", label:"방전 컷오프 (V)",         type:"number", min:0,   step:0.1 },
      { key:"rest_min",            label:"충방전 후 Rest (분)",     type:"number", min:0,   step:1 },
      { key:"time_limit_h",        label:"충전 시간 제한 (h)",      type:"number", min:0,   step:1 },
    ]
  }
};

// ── State ─────────────────────────────────────────────────────────────────
let blocks       = [];
let selectedId   = null;
let blockCounter = 0;

// ── Sortable ──────────────────────────────────────────────────────────────
const canvas = document.getElementById("blockCanvas");
Sortable.create(canvas, {
  animation: 150,
  handle: ".block-drag-handle",
  ghostClass: "sortable-ghost",
  chosenClass: "sortable-chosen",
  onEnd(evt) {
    const moved = blocks.splice(evt.oldIndex - 1, 1)[0];
    blocks.splice(evt.newIndex - 1, 0, moved);
  }
});

// ── Block management ───────────────────────────────────────────────────────
function addBlock(type) {
  const meta = BLOCK_META[type];
  if (!meta) return;
  blockCounter++;
  const id = "blk_" + blockCounter;
  const params = JSON.parse(JSON.stringify(meta.defaults));
  blocks.push({ id, type, params });
  renderBlock({ id, type, params });
  document.getElementById("emptyHint").style.display = "none";
  selectBlock(id);
}

function renderBlock(block) {
  const meta = BLOCK_META[block.type];
  const div  = document.createElement("div");
  div.className = "block-card";
  div.dataset.id = block.id;
  div.innerHTML = `
    <span class="block-drag-handle"><i class="bi bi-grip-vertical"></i></span>
    <div class="block-icon ${meta.iconClass}"><i class="bi ${meta.icon}"></i></div>
    <div class="block-info">
      <div class="block-type-label">${meta.label}</div>
      <div class="block-summary" id="sum_${block.id}">${meta.summary(block.params)}</div>
    </div>
    <button class="btn-block-delete" onclick="deleteBlock('${block.id}', event)">
      <i class="bi bi-x-lg"></i>
    </button>
  `;
  div.addEventListener("click", () => selectBlock(block.id));
  canvas.appendChild(div);
}

function deleteBlock(id, evt) {
  evt.stopPropagation();
  blocks = blocks.filter(b => b.id !== id);
  document.querySelector(`.block-card[data-id="${id}"]`)?.remove();
  if (selectedId === id) { selectedId = null; hideParamEditor(); }
  if (blocks.length === 0) document.getElementById("emptyHint").style.display = "";
}

function selectBlock(id) {
  document.querySelectorAll(".block-card").forEach(el => el.classList.remove("selected"));
  document.querySelector(`.block-card[data-id="${id}"]`)?.classList.add("selected");
  selectedId = id;
  const block = blocks.find(b => b.id === id);
  if (block) renderParamEditor(block);
}

function hideParamEditor() {
  document.getElementById("paramEditor").style.display = "none";
  document.getElementById("paramPlaceholder").style.display = "";
}

// ── Parameter editor ───────────────────────────────────────────────────────
function renderParamEditor(block) {
  const meta = BLOCK_META[block.type];
  document.getElementById("paramPlaceholder").style.display = "none";
  document.getElementById("paramEditor").style.display      = "";
  document.getElementById("paramTitle").textContent         = meta.label;

  const container = document.getElementById("paramFields");
  container.innerHTML = "";

  if (block.type === "rate_test") {
    container.appendChild(buildCRateSection(block.params));
  }

  meta.fields.forEach(f => {
    if (f.section) {
      const h = document.createElement("div");
      h.className = "param-section-title";
      h.textContent = f.section;
      container.appendChild(h);
      return;
    }

    // Conditional show
    if (f.showIf) {
      const depVal = block.params[f.showIf.key];
      // Support boolean showIf (e.g. return_pulse: true)
      if (f.showIf.val === true || f.showIf.val === false) {
        if (depVal !== f.showIf.val) return;
      } else {
        if (depVal !== f.showIf.val) return;
      }
    }

    const row = document.createElement("div");
    row.className = "param-row";

    if (f.type === "checkbox") {
      row.innerHTML = `
        <div class="form-check">
          <input class="form-check-input" type="checkbox" id="pf_${f.key}"
                 ${block.params[f.key] ? "checked" : ""}>
          <label class="form-check-label" for="pf_${f.key}">${f.label}</label>
        </div>`;
    } else if (f.type === "select") {
      const opts = f.options.map(o =>
        `<option value="${o.value}" ${block.params[f.key]===o.value?"selected":""}>${o.label}</option>`
      ).join("");
      row.innerHTML = `
        <label>${f.label}</label>
        <select class="form-select" id="pf_${f.key}">${opts}</select>`;
    } else if (f.type === "block_ref") {
      // Dynamic options: "auto" + every earlier block of filter_type
      const curIdx = blocks.findIndex(b => b.id === block.id);
      const candidates = blocks.filter((b, i) =>
        b.type === f.filter_type && i < curIdx
      );
      let opts = `<option value="" ${!block.params[f.key]?"selected":""}>직전 ${f.filter_type} 자동 (기본)</option>`;
      candidates.forEach((b, i) => {
        const label = `${b.type} #${i+1} (${b.id})`;
        opts += `<option value="${b.id}" ${block.params[f.key]===b.id?"selected":""}>${label}</option>`;
      });
      const note = candidates.length === 0
        ? '<small class="text-muted">상위에 Capacity Check 블록이 없어 자동 참조됩니다.</small>'
        : '';
      row.innerHTML = `
        <label>${f.label}</label>
        <select class="form-select" id="pf_${f.key}">${opts}</select>
        ${note}`;
    } else {
      const val = f.key === "soc_points_str"
        ? (block.params.soc_points || []).join(", ")
        : (block.params[f.key] ?? "");
      row.innerHTML = `
        <label>${f.label}</label>
        <input class="form-control" type="${f.type}" id="pf_${f.key}"
               value="${val}"
               ${f.min !== undefined ? 'min="' + f.min + '"' : ""}
               ${f.max !== undefined ? 'max="' + f.max + '"' : ""}
               step="${f.step || 1}">`;
    }
    container.appendChild(row);
  });

  // Dynamic re-render on select/checkbox change so showIf fields update live
  container.querySelectorAll("select, input[type=checkbox]").forEach(el => {
    el.addEventListener("change", () => {
      // Capture current inputs before re-rendering (to keep already-typed numbers)
      captureInputsToParams(block);
      renderParamEditor(block);
    });
  });
}

// Capture current DOM values into block.params without triggering re-render
function captureInputsToParams(block) {
  const meta = BLOCK_META[block.type];
  meta.fields.forEach(f => {
    if (f.section) return;
    const el = document.getElementById("pf_" + f.key);
    if (!el) return;
    if (f.type === "checkbox")      block.params[f.key] = el.checked;
    else if (f.type === "number")   block.params[f.key] = parseFloat(el.value) || 0;
    else if (f.key === "soc_points_str")
      block.params.soc_points = el.value.split(",").map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
    else                            block.params[f.key] = el.value;
  });
}

// ── C-rate table (Rate Test) ───────────────────────────────────────────────
function buildCRateSection(params) {
  const wrap = document.createElement("div");
  wrap.innerHTML = '<div class="param-section-title">C-rate 목록 (방전 기준)</div>';
  const list = document.createElement("div");
  list.id = "crateList";
  (params.c_rates || []).forEach((g, i) => list.appendChild(buildCRateRow(g, i)));
  wrap.appendChild(list);
  const addBtn = document.createElement("button");
  addBtn.className = "btn btn-outline-secondary btn-sm w-100 mt-1 mb-2";
  addBtn.innerHTML = '<i class="bi bi-plus"></i> C-rate 추가';
  addBtn.onclick = () => {
    const newIdx = list.querySelectorAll(".crate-row").length;
    list.appendChild(buildCRateRow({ c_rate: 0.5, count: 1 }, newIdx));
  };
  wrap.appendChild(addBtn);
  return wrap;
}

function buildCRateRow(g, i) {
  const row = document.createElement("div");
  row.className = "crate-row";
  row.innerHTML = `
    <span class="text-muted small" style="width:24px">${String.fromCharCode(65+i)}</span>
    <input type="number" class="form-control form-control-sm crate-val"
           placeholder="방전 C-rate" value="${g.c_rate}" min="0" step="0.01">
    <span class="text-muted small">C  ×</span>
    <input type="number" class="form-control form-control-sm crate-cnt"
           placeholder="횟수" value="${g.count}" min="1" step="1">
    <span class="text-muted small">회</span>
    <button class="btn-crate-del" onclick="this.parentElement.remove()">
      <i class="bi bi-x"></i>
    </button>`;
  return row;
}

function readCRates() {
  const rows = document.querySelectorAll("#crateList .crate-row");
  return Array.from(rows).map(r => ({
    c_rate: parseFloat(r.querySelector(".crate-val").value) || 0.1,
    count:  parseInt(r.querySelector(".crate-cnt").value)   || 1
  }));
}

// ── Apply parameters ───────────────────────────────────────────────────────
function applyParams() {
  const block = blocks.find(b => b.id === selectedId);
  if (!block) return;
  const meta  = BLOCK_META[block.type];

  if (block.type === "rate_test") {
    block.params.c_rates = readCRates();
  }

  meta.fields.forEach(f => {
    if (f.section) return;
    // Skip hidden fields
    if (f.showIf) {
      const depEl = document.getElementById("pf_" + f.showIf.key);
      if (depEl) {
        const depVal = (depEl.type === "checkbox") ? depEl.checked : depEl.value;
        if (f.showIf.val === true || f.showIf.val === false) {
          if (depVal !== f.showIf.val) return;
        } else {
          if (depVal !== f.showIf.val) return;
        }
      } else {
        // dep element missing — check current params
        const curVal = block.params[f.showIf.key];
        if (curVal !== f.showIf.val) return;
      }
    }

    const el = document.getElementById("pf_" + f.key);
    if (!el) return;

    if (f.type === "checkbox") {
      block.params[f.key] = el.checked;
    } else if (f.type === "number") {
      block.params[f.key] = parseFloat(el.value) ?? 0;
    } else if (f.key === "soc_points_str") {
      block.params.soc_points = el.value.split(",")
        .map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
    } else {
      block.params[f.key] = el.value;
    }
  });

  document.getElementById("sum_" + block.id).textContent = meta.summary(block.params);
  showToast("파라미터가 적용되었습니다.", "success");
  renderParamEditor(block);
}

// ── Build schedule JSON ────────────────────────────────────────────────────
function buildScheduleJSON() {
  const cap = parseFloat(document.getElementById("cellCapacity").value) || 100;
  return {
    schedule_name:     document.getElementById("scheduleName").value || "schedule",
    cell_capacity_mAh: cap,
    author: "user",
    safety: {
      max_voltage_V:    parseFloat(document.getElementById("safeMaxV").value)  || 4.3,
      min_voltage_V:    parseFloat(document.getElementById("safeMinV").value)  || 0.0,
      max_current_mA:   parseFloat(document.getElementById("safeMaxI").value)  || 0.0,
      min_current_mA:   parseFloat(document.getElementById("safeMinI").value)  || 0.0,
      max_capacity_mAh: parseFloat(document.getElementById("safeMaxCap").value) || (cap * 2),
      max_temp_C:       parseFloat(document.getElementById("safeMaxT").value)  || 70.0,
    },
    blocks: blocks.map(b => ({ id: b.id, type: b.type, params: JSON.parse(JSON.stringify(b.params)) }))
  };
}

// ── Preview ────────────────────────────────────────────────────────────────
async function showPreview() {
  if (blocks.length === 0) { showToast("블록을 먼저 추가하세요.", "warning"); return; }
  const modal = new bootstrap.Modal(document.getElementById("previewModal"));
  modal.show();

  document.getElementById("previewLoading").style.display = "";
  document.getElementById("previewDiagram").style.display = "none";
  document.getElementById("previewError").style.display   = "none";

  try {
    const res  = await fetch("/api/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildScheduleJSON())
    });
    const json = await res.json();
    if (!json.ok) throw new Error(json.error);

    document.getElementById("previewLoading").style.display  = "none";
    document.getElementById("previewDiagram").style.display  = "";
    document.getElementById("previewDiagram").innerHTML =
      `<div class="mermaid">${json.mermaid}</div>`;
    await mermaid.run({ nodes: document.querySelectorAll(".mermaid") });
  } catch (e) {
    document.getElementById("previewLoading").style.display = "none";
    document.getElementById("previewError").style.display   = "";
    document.getElementById("previewError").textContent     = "오류: " + e.message;
  }
}

// ── Export .sch ────────────────────────────────────────────────────────────
async function exportSch() {
  if (blocks.length === 0) { showToast("블록을 먼저 추가하세요.", "warning"); return; }
  try {
    const res = await fetch("/api/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildScheduleJSON())
    });
    if (!res.ok) { const j = await res.json(); throw new Error(j.error); }
    const blob = await res.blob();
    const name = document.getElementById("scheduleName").value || "schedule";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name + ".sch";
    a.click();
    showToast(".sch 파일이 생성되었습니다.", "success");
  } catch (e) {
    showToast("내보내기 오류: " + e.message, "danger");
  }
}

// ── Save / Load ────────────────────────────────────────────────────────────
async function saveSchedule() {
  try {
    const res  = await fetch("/api/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildScheduleJSON())
    });
    const json = await res.json();
    if (!json.ok) throw new Error(json.error);
    showToast(`저장 완료: ${json.filename}`, "success");
  } catch (e) {
    showToast("저장 오류: " + e.message, "danger");
  }
}

async function showLoadModal() {
  const res  = await fetch("/api/list_saved");
  const json = await res.json();
  const list = document.getElementById("savedFileList");
  list.innerHTML = "";
  if (!json.files.length) {
    list.innerHTML = '<p class="text-muted text-center">저장된 파일이 없습니다.</p>';
  } else {
    json.files.forEach(f => {
      const btn = document.createElement("button");
      btn.className = "btn btn-outline-primary w-100 mb-2 text-start";
      btn.innerHTML = `<i class="bi bi-file-earmark-code"></i> ${f}`;
      btn.onclick   = () => loadSchedule(f);
      list.appendChild(btn);
    });
  }
  new bootstrap.Modal(document.getElementById("loadModal")).show();
}

function applyScheduleData(data) {
  document.getElementById("scheduleName").value  = data.schedule_name      || "";
  document.getElementById("cellCapacity").value  = data.cell_capacity_mAh  || 100;
  if (data.safety) {
    document.getElementById("safeMaxV").value   = data.safety.max_voltage_V    ?? 4.3;
    document.getElementById("safeMinV").value   = data.safety.min_voltage_V    ?? 0.0;
    document.getElementById("safeMaxI").value   = data.safety.max_current_mA   ?? 0.0;
    document.getElementById("safeMinI").value   = data.safety.min_current_mA   ?? 0.0;
    document.getElementById("safeMaxCap").value = data.safety.max_capacity_mAh ?? 200;
    document.getElementById("safeMaxT").value   = data.safety.max_temp_C       ?? 70;
  }

  blocks = [];
  selectedId = null;
  blockCounter = 0;
  hideParamEditor();
  canvas.querySelectorAll(".block-card").forEach(el => el.remove());
  document.getElementById("emptyHint").style.display = "";

  (data.blocks || []).forEach(b => {
    if (!BLOCK_META[b.type]) return;
    blockCounter++;
    const id = "blk_" + blockCounter;
    const params = JSON.parse(JSON.stringify(b.params || {}));
    blocks.push({ id, type: b.type, params });
    renderBlock({ id, type: b.type, params });
    document.getElementById("emptyHint").style.display = "none";
  });

  if (blocks.length) selectBlock(blocks[0].id);
}

async function loadSchedule(filename) {
  try {
    const res  = await fetch("/api/load", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename })
    });
    const json = await res.json();
    if (!json.ok) throw new Error(json.error);
    const data = json.data;

    applyScheduleData(data);

    bootstrap.Modal.getInstance(document.getElementById("loadModal")).hide();
    showToast(`불러오기 완료: ${filename}`, "success");
  } catch (e) {
    showToast("불러오기 오류: " + e.message, "danger");
  }
}

async function importSchFile() {
  const input = document.getElementById("schImportFile");
  const file = input.files && input.files[0];
  if (!file) {
    showToast(".sch 파일을 선택하세요.", "warning");
    return;
  }

  try {
    const form = new FormData();
    form.append("file", file);
    form.append("cell_capacity_mAh", document.getElementById("cellCapacity").value || "100");

    const res = await fetch("/api/import_sch", { method: "POST", body: form });
    const json = await res.json();
    if (!json.ok) throw new Error(json.error);

    applyScheduleData(json.data);

    const modal = bootstrap.Modal.getInstance(document.getElementById("loadModal"));
    if (modal) modal.hide();

    const warnings = json.data._import?.warnings || [];
    if (warnings.length) {
      showToast(`.sch 불러오기 완료: ${warnings.length}개 경고`, "warning");
    } else {
      showToast(".sch 불러오기 완료", "success");
    }
    input.value = "";
  } catch (e) {
    showToast(".sch 불러오기 오류: " + e.message, "danger");
  }
}

// ── Toast helper ───────────────────────────────────────────────────────────
function showToast(msg, type = "success") {
  const colors = {
    success: "bg-success",
    danger:  "bg-danger",
    warning: "bg-warning text-dark",
    info:    "bg-info text-dark"
  };
  const el = document.getElementById("appToast");
  el.className = `toast align-items-center text-white border-0 ${colors[type] || "bg-secondary"}`;
  document.getElementById("toastBody").textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 2500 }).show();
}
