// Real silent subprocess and restored API; never real OS notifications.
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { chromium } = require(process.env.PNE_PLAYWRIGHT_MODULE || "playwright");

async function main() {
  const base = process.env.PNE_UI_URL;
  const root = process.env.PNE_QA_DATA_ROOT;
  const restoredAPI = process.env.PNE_RESTORED_API;
  assert.ok(base && root && restoredAPI && process.env.PNE_PYTHON, "Isolated QA paths required");
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  let child;
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(15000);
    await page.goto(base, { waitUntil: "networkidle" });
    const status = await (await page.request.post(new URL("/api/data/status", base).href, { data: {} })).json();
    assert.equal(path.resolve(status.database), path.join(path.resolve(root), "storage.sqlite3"));
    child = spawn(process.env.PNE_PYTHON, ["-c", `
import sys
from pathlib import Path
from pne_scheduler.storage_records import StorageStore
from pne_scheduler.storage_companion import run_companion
run_companion(StorageStore(Path(sys.argv[1])), notify=lambda *args: None, poll_seconds=3600)
`, status.database], { cwd: path.resolve(__dirname, "../../.."), stdio: "ignore" });
    const exited = new Promise((resolve) => child.once("exit", resolve));
    const nav = page.getByRole("navigation", { name: "작업 단계" });
    await nav.getByRole("button", { name: /데이터 관리/ }).click();
    const care = page.locator(".data-safety");
    const stop = care.getByRole("button", { name: "안전 종료 요청" });
    await stop.waitFor();
    await page.waitForFunction(() => ![...document.querySelectorAll(".data-safety button")].find(b => b.textContent === "안전 종료 요청").disabled);
    await care.getByRole("button", { name: "백업 내용 미리보기" }).click();
    await care.getByRole("alert").waitFor();
    await stop.click();
    await care.getByText("안전 종료 확인", { exact: true }).waitFor();
    assert.equal(await exited, 0);
    assert.equal(await stop.isDisabled(), true);

    // Route only data-care requests to a second real local API using the
    // previously verified restored DB. No synthetic state/response fixtures.
    await page.route("**/api/data/*", async (route) => {
      const url = new URL(route.request().url());
      const response = await route.fetch({ url: new URL(url.pathname, restoredAPI).href });
      await route.fulfill({ response });
    });
    await care.getByRole("button", { name: "실행기 상태 새로고침" }).click();
    await care.getByText("복원된 알림은 일시 정지 중입니다", { exact: true }).waitFor();
    const resume = care.getByRole("button", { name: "기존 알림 설정 재개" });
    assert.equal(await resume.isDisabled(), true);
    await care.getByLabel("복원 일정과 지연 알림을 검토했습니다").check();
    await resume.click();
    await page.waitForFunction(() => !document.querySelector(".data-safety .data-companion input[type=checkbox]"));
    const final = await (await page.request.post(new URL("/api/data/status", restoredAPI).href, { data: {} })).json();
    assert.equal(final.companion.restorePaused, false);
    assert.equal(final.companion.active, false);
    process.stdout.write("Safe stop UI, busy backup refusal and restored-alert explicit resume passed\n");
  } finally {
    if (child && child.exitCode === null) child.kill("SIGTERM"); // only this test's silent child
    await browser.close();
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
