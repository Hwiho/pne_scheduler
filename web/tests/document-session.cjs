// Non-browser async regressions for the production document coordinator.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

function loadDocumentModule() {
  const filename = path.join(__dirname, "../src/lib/useDocument.ts");
  const source = fs.readFileSync(filename, "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    fileName: filename,
  }).outputText;
  const module = { exports: {} };
  const apiStub = {
    ApiError: class ApiError extends Error {},
    api: {
      views: async () => { throw new Error("default API stub used"); },
      edit: async () => { throw new Error("default API stub used"); },
    },
  };
  const localRequire = (request) => {
    if (request === "react") return require("react");
    if (request === "./api") return apiStub;
    return require(request);
  };
  Function("exports", "require", "module", "__filename", "__dirname", output)(
    module.exports, localRequire, module, filename, path.dirname(filename),
  );
  return module.exports;
}

const { DocumentSession, readRecovery, writeRecovery } = loadDocumentModule();

test("opening or starting a project is one undoable replacement", async () => {
  const client = { views: async (project) => ({ views: views(project.name) }) };
  const session = new DocumentSession(client);
  await session.open({ name: "original", modules: ["kept"] });
  await session.replace({ name: "loaded", modules: ["new"] }, "프로젝트 열기");
  assert.equal(session.snapshot().project.name, "loaded");
  assert.equal(session.snapshot().undoLabel, "프로젝트 열기");
  await session.undo();
  assert.deepEqual(session.snapshot().project, { name: "original", modules: ["kept"] });
  await session.redo();
  assert.equal(session.snapshot().project.name, "loaded");
});

test("failed project replacement preserves the current document and undo stack", async () => {
  const client = { views: async (project) => {
    if (project.name === "broken") throw new Error("읽을 수 없음");
    return { views: views(project.name) };
  } };
  const session = new DocumentSession(client);
  await session.open({ name: "original" });
  await session.replace({ name: "broken" });
  assert.equal(session.snapshot().project.name, "original");
  assert.equal(session.snapshot().canUndo, false);
  assert.match(session.snapshot().error, /읽을 수 없음/);
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function views(selectedModule, marker = selectedModule) {
  return { selectedModule, marker };
}

test("rapid edits serialize and the second edit uses the first result", async () => {
  const first = deferred();
  const editBases = [];
  let editNumber = 0;
  const client = {
    views: async () => ({ views: views("module-a") }),
    edit: async (_action, project) => {
      editBases.push(project.version);
      editNumber += 1;
      if (editNumber === 1) await first.promise;
      const version = project.version + 1;
      return {
        project: { version },
        label: `edit-${version}`,
        views: views("module-a"),
        diff: { headline: `change-${version}` },
      };
    },
  };
  const session = new DocumentSession(client);
  await session.open({ version: 0 });
  const one = session.apply("change");
  const two = session.apply("change");
  await Promise.resolve();
  assert.deepEqual(editBases, [0]);
  first.resolve();
  await Promise.all([one, two]);
  assert.deepEqual(editBases, [0, 1]);
  assert.equal(session.snapshot().project.version, 2);
  assert.equal(session.snapshot().canUndo, true);
  assert.equal(session.snapshot().lastDiff.headline, "change-2");
});

test("late selection response cannot overwrite a newer selection", async () => {
  const oldSelection = deferred();
  const client = {
    views: async (_project, selected) => {
      if (selected === "old") return oldSelection.promise;
      return { views: views(selected || "initial") };
    },
    edit: async () => { throw new Error("unused"); },
  };
  const session = new DocumentSession(client);
  await session.open({ version: 0 });
  const old = session.select("old");
  const current = session.select("current");
  await current;
  oldSelection.resolve({ views: views("old") });
  await old;
  assert.equal(session.snapshot().selected, "current");
  assert.equal(session.snapshot().views.marker, "current");
});

test("selection refresh from the old project cannot overwrite an edit result", async () => {
  const staleSelection = deferred();
  const client = {
    views: async (_project, selected) => {
      if (selected === "stale") return staleSelection.promise;
      return { views: views(selected || "initial") };
    },
    edit: async (_action, project) => ({
      project: { version: project.version + 1 },
      label: "edited",
      views: views("from-edit"),
      diff: { headline: "accepted edit" },
    }),
  };
  const session = new DocumentSession(client);
  await session.open({ version: 0 });
  const selecting = session.select("stale");
  await session.apply("change");
  staleSelection.resolve({ views: views("stale") });
  await selecting;
  assert.equal(session.snapshot().project.version, 1);
  assert.equal(session.snapshot().selected, "from-edit");
  assert.equal(session.snapshot().views.marker, "from-edit");
  assert.equal(session.snapshot().lastDiff.headline, "accepted edit");
});

test("failed undo keeps project and history intact, then one retry moves one entry", async () => {
  let failUndo = true;
  const client = {
    views: async (project) => {
      if (project.version === 1 && failUndo) throw new Error("refresh failed");
      return { views: views("module-a", `v${project.version}`) };
    },
    edit: async (_action, project) => {
      const version = project.version + 1;
      return { project: { version }, label: `edit-${version}`, views: views("module-a"), diff: null };
    },
  };
  const session = new DocumentSession(client);
  await session.open({ version: 0 });
  await session.apply("change");
  await session.apply("change");
  await session.undo();
  assert.equal(session.snapshot().project.version, 2);
  assert.equal(session.snapshot().undoLabel, "edit-2");
  assert.equal(session.snapshot().canRedo, false);

  failUndo = false;
  await session.undo();
  assert.equal(session.snapshot().project.version, 1);
  assert.equal(session.snapshot().undoLabel, "edit-1");
  assert.equal(session.snapshot().canRedo, true);
  assert.equal(session.snapshot().lastDiff, null);
});

test("recovery failures preserve stored data and never throw", () => {
  const original = "{broken-but-valuable";
  const malformed = {
    getItem: () => original,
    setItem: () => { throw new Error("quota"); },
  };
  const read = readRecovery(malformed);
  assert.equal(read.project, null);
  assert.match(read.warning, /그대로 보존/);
  assert.equal(read.writable, false);
  assert.equal(malformed.getItem(), original);
  assert.match(writeRecovery(malformed, { version: 3 }), /메모리에서 유지/);
  assert.equal(malformed.getItem(), original);

  const unavailable = {
    getItem: () => { throw new Error("security"); },
    setItem: () => { throw new Error("security"); },
  };
  const unavailableRead = readRecovery(unavailable);
  assert.match(unavailableRead.warning, /사용할 수 없습니다/);
  assert.equal(unavailableRead.writable, false);
});

test("API failures clear loading state and retain the current document", async () => {
  let failEdit = false;
  const client = {
    views: async () => ({ views: views("module-a") }),
    edit: async (_action, project) => {
      if (failEdit) throw new Error("edit unavailable");
      return { project: { version: project.version + 1 }, label: "edited", views: views("module-a"), diff: null };
    },
  };
  const session = new DocumentSession(client);
  await session.open({ version: 0 });
  failEdit = true;
  await session.apply("change");
  assert.equal(session.snapshot().busy, false);
  assert.equal(session.snapshot().project.version, 0);
  assert.equal(session.snapshot().canUndo, false);
  assert.equal(session.snapshot().error, "edit unavailable");
});
