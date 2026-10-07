const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

function loadUnitInputHelpers() {
  const filename = path.join(__dirname, "../src/lib/unitInput.ts");
  const source = fs.readFileSync(filename, "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    fileName: filename,
  }).outputText;
  const module = { exports: {} };
  Function("exports", "require", "module", "__filename", "__dirname", output)(
    module.exports, require, module, filename, path.dirname(filename),
  );
  return module.exports;
}

const {
  commitValue,
  convertDraft,
  defaultUnit,
  displayValue,
  isRepeatedUnitDetail,
  supportsUnitInput,
  inferNumericValue,
  parsePositiveRateList,
} = loadUnitInputHelpers();

test("QC current list rejects the whole malformed list rather than dropping stages", () => {
  assert.deepEqual(parsePositiveRateList("4, 3, 2"), [4, 3, 2]);
  assert.deepEqual(parsePositiveRateList(" 1.5 , 0.5 "), [1.5, 0.5]);
  for (const text of ["", "4,,2", "4, wrong, 2", "4,", "-1,2", "0,2", "Infinity,2", "NaN,2"]) {
    assert.throws(() => parsePositiveRateList(text));
  }
});

test("old API duration strings are interpreted before selecting their display unit", () => {
  assert.equal(inferNumericValue("duration_s", "6시간"), 21600);
  assert.equal(inferNumericValue("duration_s", "30분"), 1800);
  assert.equal(inferNumericValue("duration_s", "1초"), 1);
  assert.equal(inferNumericValue("duration_s", "1시간 30분"), 5400);
  assert.equal(inferNumericValue("duration_s", ""), null);
  assert.equal(inferNumericValue("soc_percent", "80%"), 0.8);
});

test("duration picks an exact useful default unit", () => {
  assert.equal(defaultUnit("duration_s", 10), "초");
  assert.equal(defaultUnit("duration_s", 1800), "분");
  assert.equal(defaultUnit("duration_s", 7200), "시간");
  assert.equal(defaultUnit("duration_s", 172800), "일");
  assert.equal(defaultUnit("duration_s", 3660), "분");
});

test("unit changes preserve the physical amount without committing it", () => {
  assert.equal(convertDraft("duration_s", "30", "분", "초"), "1800");
  assert.equal(convertDraft("voltage_v", "4.2", "V", "mV"), "4200");
  assert.equal(convertDraft("current_mA", "1.5", "A", "mA"), "1500");
  assert.equal(convertDraft("duration_s", "unfinished", "초", "분"), null);
  const unchangedDraft = convertDraft("duration_s", "30", "분", "초");
  const unchangedBaseline = convertDraft("duration_s", "30", "분", "초");
  assert.equal(unchangedDraft, unchangedBaseline);
  const editedDraft = convertDraft("duration_s", "45", "분", "초");
  assert.notEqual(editedDraft, unchangedBaseline);
});

test("commits canonical numeric text while leaving validation to the server", () => {
  assert.equal(commitValue("duration_s", "1.5", "분"), "90");
  assert.equal(commitValue("voltage_v", "4200", "mV"), "4.2");
  assert.equal(commitValue("current_mA", "1.5", "A"), "1500");
  assert.equal(commitValue("c_rate", "C/3", "C"), "C/3");
  assert.equal(commitValue("count", "not-yet-valid", "회"), "not-yet-valid");
});

test("SOC and fraction fields show percent once and submit percent syntax", () => {
  assert.equal(displayValue("soc_percent", 0.8, "80%", "%"), "80");
  assert.equal(displayValue("fraction", 0.2, "20%", "%"), "20");
  assert.equal(displayValue("soc_percent_list", null, "80%, 50%, 20%", "%"), "80, 50, 20");
  assert.equal(commitValue("soc_percent", "80", "%"), "80%");
  assert.equal(commitValue("fraction", "20", "%"), "20%");
  assert.equal(commitValue("soc_percent_list", "80, 50, 20", "%"), "80, 50, 20%");
});

test("C-rate display uses raw numeric value instead of a lossy formatted string", () => {
  assert.equal(displayValue("c_rate", 1 / 3, "~0.33C", "C"), "1/3");
  assert.equal(displayValue("c_rate", 1 / 3, "C/3", "C"), "1/3");
  assert.equal(commitValue("c_rate", "1/3", "C"), "C/3");
  assert.equal(displayValue("c_rate", 0.4, "~0.40C", "C"), "0.4");
  assert.equal(supportsUnitInput("text"), false);
});

test("empty input is not silently converted into zero when changing units or committing", () => {
  assert.equal(convertDraft("duration_s", "", "분", "초"), null);
  assert.equal(commitValue("duration_s", "", "분"), "");
  assert.equal(commitValue("c_rate", "  ", "C"), "");
});

test("list inputs keep one unit and preserve raw rates and durations", () => {
  assert.equal(displayValue("c_rate_list", null, "C/3, 1.5C", "C", [1 / 3, 1.5]), "1/3, 1.5");
  assert.equal(commitValue("c_rate_list", "1/3, 1.5", "C"), "C/3, 1.5");
  assert.equal(defaultUnit("duration_list", null, [60, 180]), "분");
  assert.equal(displayValue("duration_list", null, "60초, 180초", "분", [60, 180]), "1, 3");
  assert.equal(convertDraft("duration_list", "1, 3", "분", "초"), "60, 180");
  assert.equal(commitValue("duration_list", "1.5, 3", "분"), "90, 180");
  assert.equal(convertDraft("duration_list", "1, unfinished", "분", "초"), null);
  assert.equal(displayValue("voltage_list", null, "3.918 V, 4.008 V", "mV", [3.918, 4.008]), "3918, 4008");
  assert.equal(commitValue("voltage_list", "3918, 4008", "mV"), "3.918, 4.008");
});

test("repeated unit detail is hidden but useful semantic detail remains", () => {
  assert.equal(isRepeatedUnitDetail("duration_s", "30분", "30분"), true);
  assert.equal(isRepeatedUnitDetail("duration_list", "10초, 30초", "10초 / 30초"), true);
  assert.equal(isRepeatedUnitDetail("soc_percent", "80%", "SOC 80%"), true);
  assert.equal(isRepeatedUnitDetail("soc_percent_list", "80%, 50%, 20%", "SOC 80% / SOC 50% / SOC 20%"), true);
  assert.equal(isRepeatedUnitDetail("fraction", "20%", "기준용량의 20%"), false);
  assert.equal(isRepeatedUnitDetail("c_rate", "0.5C", "0.5C = 500 mA"), false);
});
