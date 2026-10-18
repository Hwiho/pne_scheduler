// Isolated API/data roots only. Never opens or activates a desktop window.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PNE_PLAYWRIGHT_MODULE || "playwright");

async function main() {
  assert.ok(process.env.PNE_UI_OUTPUT, "Use a disposable QA directory");
  const output = path.resolve(process.env.PNE_UI_OUTPUT);
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const base = process.env.PNE_UI_URL || "http://127.0.0.1:3000/";
  try {
    for (const width of [1280, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, locale: "ko-KR" });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      try {
        await page.goto(base, { waitUntil: "networkidle" });
        if (width === 1280) {
          const response = await page.request.post(new URL("/api/storage", base).href, { data: {
            sample: "Isolated data-care QA", startedAt: "2025-01-01T00:00:00Z", temperatureC: 45,
            targetDays: 30, checkpointDays: [7, 14], notifyEnabled: true,
          } });
          assert.equal(response.status(), 200);
        }
        const nav = page.getByRole("navigation", { name: "작업 단계" });
        await nav.getByRole("button", { name: /데이터 관리/ }).click();
        const care = page.locator(".data-safety");
        const archive = path.join(output, `backup-${width}.zip`);
        const destination = path.join(output, `restored-${width}`);
        await care.getByRole("button", { name: "백업 내용 미리보기" }).click();
        await care.getByLabel("백업 미리보기").waitFor();
        await care.getByLabel("현재 웹 프로젝트 포함", { exact: false }).uncheck();
        assert.equal(await care.getByRole("button", { name: "검증 백업 저장" }).isDisabled(), true);
        await care.getByLabel("현재 웹 프로젝트 포함", { exact: false }).check();
        await care.getByLabel("새 백업 ZIP 절대 경로", { exact: true }).fill(archive);
        await nav.getByRole("button", { name: /프로토콜/ }).click();
        await nav.getByRole("button", { name: /데이터 관리/ }).click();
        assert.equal(await care.getByLabel("새 백업 ZIP 절대 경로", { exact: true }).inputValue(), archive);
        await care.getByRole("button", { name: "백업 내용 미리보기" }).click();
        await care.getByLabel("백업 미리보기").waitFor();
        await care.getByLabel("다른 구버전 앱·외부 편집기의 데이터 쓰기를 중지했습니다").check();
        await care.getByRole("button", { name: "검증 백업 저장" }).click();
        await care.getByText(/백업 생성·검증 완료:/).waitFor();
        assert.ok(fs.statSync(archive).size > 0);
        await care.getByRole("button", { name: "복원 전 검사" }).click();
        await care.getByLabel("복원 검사 결과").waitFor();
        await care.getByLabel("새 복원 폴더 절대 경로", { exact: true }).fill(destination);
        const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
        assert.ok(layout.scroll <= layout.width + 2, `Overflow ${JSON.stringify(layout)}`);
        await care.screenshot({ path: path.join(output, `data-care-${width}.png`) });
        await care.getByRole("button", { name: "원본 보존 · 새 폴더 복원" }).click();
        await care.getByText(/복원 완료:/).waitFor();
        const report = JSON.parse(fs.readFileSync(path.join(destination, "restore-report.json")));
        assert.ok(report.notificationsPaused && report.sourceUntouched);
        assert.ok(report.records >= 1);
        assert.ok(fs.existsSync(path.join(destination, "projects/current.schproj")));
        await care.getByLabel("백업 ZIP 절대 경로", { exact: true }).fill(path.join(output, "missing.zip"));
        await care.getByRole("button", { name: "복원 전 검사" }).click();
        await care.getByRole("alert").waitFor();
        assert.equal(await care.getByRole("button", { name: "원본 보존 · 새 폴더 복원" }).isDisabled(), true);
        assert.equal(await care.getByLabel("새 복원 폴더 절대 경로", { exact: true }).inputValue(), destination);
        assert.deepEqual(errors, []);
        process.stdout.write(`Data care ${width}px: verified ZIP + new-directory restore passed\n`);
      } catch (error) {
        await page.screenshot({ path: path.join(output, `data-failure-${width}.png`), fullPage: true });
        throw error;
      } finally { await context.close(); }
    }
  } finally { await browser.close(); }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
