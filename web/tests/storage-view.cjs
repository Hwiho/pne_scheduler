const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/lib/storageView.ts"), "utf8");
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const loaded = { exports: {} };
Function("exports", "module", output)(loaded.exports, loaded);
const { filterStorageRecords, storageNeedsAttention } = loaded.exports;

const now = Date.parse("2026-10-18T00:00:00Z");
const row = (id, changes = {}) => ({
  id, sample: `Cell ${id}`, completedAt: null, archivedAt: null,
  alerts: [{ dueAt: "2026-10-17T00:00:00Z", acknowledgedAt: null, snoozedUntil: null, notifiedAt: null }],
  ...changes,
});

test("storage filters distinguish active, completed and archived records", () => {
  const records = [row("A"), row("B", { completedAt: "2026-10-18T00:00:00Z" }), row("C", { archivedAt: "2026-10-18T00:00:00Z" })];
  const ids = (filter) => filterStorageRecords(records, "", filter, now).map((item) => item.id);
  assert.deepEqual(ids("current"), ["A", "B"]);
  assert.deepEqual(ids("active"), ["A"]);
  assert.deepEqual(ids("completed"), ["B"]);
  assert.deepEqual(ids("archived"), ["C"]);
  assert.deepEqual(ids("all"), ["A", "B", "C"]);
});

test("search is normalized, case-insensitive and matches sample or ID without mutating data", () => {
  const records = [row("A01", { sample: "시료 Ａ" }), row("B02")];
  const original = JSON.stringify(records);
  assert.equal(filterStorageRecords(records, "시료 a", "current", now).length, 1);
  assert.equal(filterStorageRecords(records, " a01 ", "current", now).length, 1);
  assert.equal(filterStorageRecords(records, "missing", "all", now).length, 0);
  assert.equal(JSON.stringify(records), original);
});

test("attention includes due checkpoints even after notification, until acknowledged", () => {
  const record = row("A");
  assert.equal(storageNeedsAttention(record, now), true);
  record.alerts[0].notifiedAt = "2026-10-17T00:01:00Z";
  assert.equal(storageNeedsAttention(record, now), true);
  record.alerts[0].acknowledgedAt = "2026-10-17T00:02:00Z";
  assert.equal(storageNeedsAttention(record, now), false);
});

test("future snoozes, completed and archived records do not need attention", () => {
  const record = row("A");
  record.alerts[0].snoozedUntil = "2026-10-19T00:00:00Z";
  assert.equal(storageNeedsAttention(record, now), false);
  record.alerts[0].snoozedUntil = null;
  assert.equal(storageNeedsAttention({ ...record, completedAt: "2026-10-18T00:00:00Z" }, now), false);
  assert.equal(storageNeedsAttention({ ...record, archivedAt: "2026-10-18T00:00:00Z" }, now), false);
  assert.deepEqual(filterStorageRecords([record], "", "attention", now), [record]);
});
