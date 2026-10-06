// Browser regression checks for the user-reported navigation, box editor,
// batch preview, storage timer and narrow-window layout. Run against local UI.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PNE_PLAYWRIGHT_MODULE || "playwright");

async function main() {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, locale: "ko-KR" });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(process.env.PNE_UI_URL || "http://127.0.0.1:3000/", { waitUntil: "networkidle" });
      await page.getByRole("navigation", { name: "작업 단계" }).getByRole("button", { name: /프로토콜/ }).click();
      await page.getByRole("heading", { name: "모듈 연결" }).waitFor();
      await page.getByRole("button", { name: /무엇을 알고 싶으신가요/ }).click();
      const choices = page.getByRole("group", { name: "실험 목적 목록" });
      assert.ok(await choices.getByRole("button").count() > 1, "goal picker options");
      assert.equal(await page.getByRole("button", { name: /무엇을 알고 싶으신가요/ }).getAttribute("aria-expanded"), "true");
      await choices.getByRole("button").first().click();
      await page.waitForFunction(() => document.querySelectorAll(".flow-node").length > 0);
      await page.getByRole("button", { name: /되돌리기/ }).click();
      await page.waitForFunction(() => document.querySelectorAll(".flow-node").length === 0);
      const flow = page.getByRole("group", { name: "모듈 실행 흐름" });
      await page.locator(".flow-palette-item").first().click();
      await page.waitForFunction(() => document.querySelectorAll(".flow-node").length > 0);
      const before = await flow.locator("article.flow-node").count();
      assert.ok(before > 0, "seed modules are available");
      const first = flow.locator("article.flow-node").first();
      await first.getByRole("button", { name: /추가 작업/ }).click();
      await first.getByRole("button", { name: "이 박스 복제" }).click();
      await page.waitForFunction((n) => document.querySelectorAll(".flow-node").length === n + 1, before);
      await page.getByRole("button", { name: /되돌리기/ }).click();
      await page.waitForFunction((n) => document.querySelectorAll(".flow-node").length === n, before);
      page.once("dialog", (dialog) => dialog.accept());
      await flow.locator("article.flow-node").first().getByRole("button", { name: /추가 작업/ }).click();
      await flow.getByRole("button", { name: "이 박스 삭제" }).click();
      await page.waitForFunction((n) => document.querySelectorAll(".flow-node").length === n - 1, before);
      await page.getByRole("button", { name: /되돌리기/ }).click();
      await page.waitForFunction((n) => document.querySelectorAll(".flow-node").length === n, before);
      const layout = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth }));
      assert.ok(layout.page <= layout.viewport + 2, `horizontal page overflow at ${width}px: ${JSON.stringify(layout)}`);
      await page.getByRole("navigation", { name: "작업 단계" }).getByRole("button", { name: /내보내기/ }).click();
      await page.getByRole("heading", { name: "셀별 파일 일괄 생성" }).waitFor();
      assert.equal(await page.getByText("전류 계산 기준", { exact: true }).count(), 0, "direct reference input has no basis picker");
      await page.getByLabel("셀 목록 · 한 줄에 한 셀").fill("A01,80\nA02,82\nA03,84");
      await page.getByRole("button", { name: "셀별 전류 미리보기" }).click();
      await page.getByText("3셀 생성 가능").waitFor();
      assert.equal(await page.getByRole("table").last().locator("tbody tr").count(), 3, "three direct-capacity rows");
      await page.getByRole("navigation", { name: "작업 단계" }).getByRole("button", { name: /고온저장/ }).click();
      await page.getByRole("heading", { name: "고온저장 경과시간" }).waitFor();
      await page.getByText(/Windows 알림 실행기/).waitFor();
      assert.deepEqual(errors, [], `browser errors at ${width}px`);
      await context.close();
      process.stdout.write(`UI smoke ${width}px passed\n`);
    }
  } finally { await browser.close(); }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
