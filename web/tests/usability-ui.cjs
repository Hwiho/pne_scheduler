// Run only against an isolated local API/library. Always headless; never touches
// the user's browser profile. PNE_UI_OUTPUT must point to a disposable QA folder.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const { chromium } = require(process.env.PNE_PLAYWRIGHT_MODULE || "playwright");

async function main() {
  assert.ok(process.env.PNE_UI_OUTPUT, "Set PNE_UI_OUTPUT to an isolated QA folder");
  const output = path.resolve(process.env.PNE_UI_OUTPUT);
  const project = JSON.parse(fs.readFileSync(path.join(__dirname, "../../example/example.schproj"), "utf8"));
  project.name = "Usability QA";
  project.modules = project.modules.slice(0, 1);
  project.connections = [];
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    for (const width of [1280, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, locale: "ko-KR" });
      await context.addInitScript((value) => localStorage.setItem("pne_scheduler.draft.v1", JSON.stringify(value)), project);
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      const overflow = async () => {
        const layout = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth }));
        assert.ok(layout.page <= layout.viewport + 2, `overflow ${width}px: ${JSON.stringify(layout)}`);
      };
      const committed = (key, value) => page.waitForFunction(([k, v]) => JSON.parse(localStorage.getItem("pne_scheduler.draft.v1")).modules[0].params[k] === v, [key, value]);
      try {
        await page.goto(process.env.PNE_UI_URL || "http://127.0.0.1:3000/", { waitUntil: "networkidle" });
        const nav = page.getByRole("navigation", { name: "작업 단계" });
        await nav.getByRole("button", { name: /프로토콜/ }).click();
        const core = page.getByRole("region", { name: "실험 핵심 조건" });
        const rate = core.getByLabel("화성 충전율", { exact: true });
        await rate.fill("0.2");
        await rate.press("Enter");
        await committed("charge_c_rate", .2);
        await page.getByRole("button", { name: /되돌리기/ }).click();
        await committed("charge_c_rate", .1);
        await rate.fill("bad");
        await rate.press("Enter");
        await core.getByRole("button", { name: "입력한 값 바로 수정" }).click();
        assert.equal(await rate.evaluate((el) => el === document.activeElement), true, "error focuses input");
        assert.equal(await rate.inputValue(), "bad", "failed edit retains draft");
        await rate.fill("0.15");
        await rate.press("Enter");
        await committed("charge_c_rate", .15);
        await page.waitForFunction(() => !document.querySelector(".key-conditions [role=alert]"));
        await core.getByLabel("기준용량 (mAh)", { exact: true }).fill("90");
        await core.getByLabel("기준용량 (mAh)", { exact: true }).press("Enter");
        await page.waitForFunction(() => JSON.parse(localStorage.getItem("pne_scheduler.draft.v1")).cell_profile.nominal_capacity_mAh === 90);
        await overflow();
        await core.screenshot({ path: path.join(output, `conditions-${width}.png`) });

        await nav.getByRole("button", { name: /내보내기/ }).click();
        const batch = page.getByRole("region", { name: "셀별 배치 생성" });
        const table = batch.getByRole("region", { name: "셀 목록 편집" });
        await table.getByText("엑셀·텍스트에서 여러 셀 추가", { exact: true }).click();
        await table.getByLabel("셀 목록 · 한 줄에 한 셀").fill("셀 ID\t기준용량\nA01\t80\nA02\t\nA03\t100");
        await table.getByRole("button", { name: "표에 추가", exact: true }).click();
        const row = table.locator("tbody tr").nth(1);
        await row.getByRole("button", { name: /수정/ }).click();
        const capacity = table.getByLabel("2행 기준용량", { exact: true });
        assert.equal(await capacity.evaluate((el) => el === document.activeElement), true, "row error focuses capacity");
        await capacity.fill("90");
        await page.waitForFunction(() => document.querySelectorAll(".cell-input-table tbody tr")[1].cells[3].textContent === "90");
        await table.getByLabel("1행 선택", { exact: true }).check();
        await table.getByRole("button", { name: "선택 행 복사" }).click();
        assert.equal(await table.getByLabel("4행 셀 ID", { exact: true }).inputValue(), "A04");
        await table.getByLabel("4행 선택", { exact: true }).check();
        await table.getByLabel("연번 접두어", { exact: true }).fill("TEST");
        await table.getByRole("button", { name: "선택 셀 연번" }).click();
        await page.waitForFunction(() => document.getElementById("batch-row-3-cellId")?.value === "TEST01");
        await table.getByLabel("4행 선택", { exact: true }).check();
        await table.getByRole("button", { name: "선택 행 삭제" }).click();
        await page.waitForFunction(() => document.querySelectorAll(".cell-input-table tbody tr").length === 3);
        await nav.getByRole("button", { name: /프로토콜/ }).click();
        await core.getByRole("heading", { name: "실험 핵심 조건" }).waitFor();
        await nav.getByRole("button", { name: /내보내기/ }).click();
        assert.equal(await capacity.inputValue(), "90", "cell rows survive tab changes");
        await batch.getByLabel(/파일 종류/).selectOption("review_candidate");
        await batch.getByRole("button", { name: "셀별 전류 미리보기" }).click();
        await batch.getByText("3셀 생성 가능", { exact: true }).waitFor();
        // A changed row must invalidate the previous file-generation token.
        await capacity.fill("91");
        assert.equal(await batch.getByRole("button", { name: "일괄 생성", exact: true }).isDisabled(), true);
        await capacity.fill("90");
        await batch.getByRole("button", { name: "셀별 전류 미리보기" }).click();
        await batch.getByText("3셀 생성 가능", { exact: true }).waitFor();
        const folder = path.join(output, `batch-${width}-${Date.now()}`);
        await batch.getByLabel("새 출력 폴더의 절대 경로", { exact: true }).fill(folder);
        await batch.getByRole("button", { name: "일괄 생성", exact: true }).click();
        await batch.locator(".batch-success").waitFor();
        const manifest = JSON.parse(fs.readFileSync(path.join(folder, "batch-manifest.json"), "utf8"));
        assert.equal(manifest.cells.length, 3);
        assert.equal(manifest.equipmentExecutable, false);
        assert.deepEqual(manifest.cells.map((cell) => cell.maxCurrentmA), [12, 13.5, 15]);
        for (const cell of manifest.cells) {
          for (const file of cell.files) {
            const digest = crypto.createHash("sha256").update(fs.readFileSync(path.join(folder, file.path))).digest("hex");
            assert.equal(digest, file.sha256, `hash mismatch: ${file.path}`);
          }
        }
        await page.waitForFunction(() => document.querySelectorAll(".cell-input-table tbody tr")[1].cells[3].textContent === "90");
        await overflow();
        await table.screenshot({ path: path.join(output, `cells-${width}.png`) });
        assert.deepEqual(errors, [], `browser errors at ${width}px`);
        process.stdout.write(`Usability ${width}px passed; generated ${folder}\n`);
      } catch (error) {
        await page.screenshot({ path: path.join(output, `failure-${width}.png`), fullPage: true });
        throw error;
      } finally { await context.close(); }
    }
  } finally { await browser.close(); }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
