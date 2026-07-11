// 前端 E2E 冒烟测试（Playwright 裸脚本，非 test-runner）
// 前置：前端 dev server 与后端已启动（见 e2e/README.md），后端为可写的测试数据库。
// 用法：node e2e/e2e.mjs
// 环境变量：FRONTEND_URL（默认 http://localhost:5174）、BACKEND_URL（默认 http://localhost:8000）

import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND = process.env.FRONTEND_URL ?? "http://localhost:5174";
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), "screenshots");
mkdirSync(OUT_DIR, { recursive: true });

const TEACHER = { email: "e2e-teacher@test.local", password: "E2eTest#2026", name: "E2E测试教师" };
const STUDENT = { email: "e2e-student@test.local", password: "E2eStu#2026", name: "E2E测试学生" };
const COURSE = "五年级数学E2E";
const ASSIGNMENT = "E2E测试作业";
const TEACHER_ROUTES = ["courses", "students", "assignments", "grading", "submission-status", "submission-records"];

const results = [];
function record(name, pass, detail = "") {
  results.push({ name, pass, detail });
  console.log(`${pass ? "✓" : "✗"} ${name}${detail ? " — " + detail : ""}`);
}

async function api(path, options = {}, token = null) {
  const res = await fetch(BACKEND + path, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  return { status: res.status, json: await res.json().catch(() => null) };
}

// —— 种子数据：教师 / 班级 / 学生 / 作业（幂等：entry 对已有账号即登录）——
async function seed() {
  const t = await api("/auth/teacher/entry", { method: "POST", body: JSON.stringify(TEACHER) });
  if (t.status !== 200) throw new Error(`教师 entry 失败: ${t.status}`);
  const token = t.json.access_token;

  let courses = (await api("/teachers/me/courses", {}, token)).json ?? [];
  let course = courses.find((c) => c.name === COURSE);
  if (!course) course = (await api("/teachers/me/courses", { method: "POST", body: JSON.stringify({ name: COURSE }) }, token)).json;

  const students = (await api(`/courses/${course.id}/students`, {}, token)).json ?? [];
  if (!students.some((s) => s.email === STUDENT.email)) {
    await api(`/courses/${course.id}/students`, { method: "POST", body: JSON.stringify(STUDENT) }, token);
  }

  const assignments = (await api(`/courses/${course.id}/assignments`, {}, token)).json ?? [];
  if (!assignments.some((a) => a.title === ASSIGNMENT)) {
    await api(`/courses/${course.id}/assignments`, { method: "POST", body: JSON.stringify({ title: ASSIGNMENT }) }, token);
  }
  record("种子数据就绪", true, `course #${course.id}`);
}

async function loginTeacher(page) {
  await page.goto(`${FRONTEND}/teacher/login`, { waitUntil: "networkidle" });
  await page.locator('input[type="email"]').fill(TEACHER.email);
  await page.locator('input[type="password"]').fill(TEACHER.password);
  await page.getByRole("button", { name: /登录/ }).click();
  await page.waitForURL("**/teacher/courses", { timeout: 15000 });
}

async function loginStudent(page) {
  await page.goto(`${FRONTEND}/student/login`, { waitUntil: "networkidle" });
  await page.locator('input[type="email"]').fill(STUDENT.email);
  await page.locator('input[type="password"]').fill(STUDENT.password);
  await page.getByRole("button", { name: /登录/ }).click();
  await page.waitForURL("**/student", { timeout: 15000 });
}

async function main() {
  await seed();
  const browser = await chromium.launch();
  const consoleErrors = [];
  const consoleWarnings = [];
  const hookConsole = (page) => page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
    if (m.type() === "warning") consoleWarnings.push(m.text());
  });
  // 后端 /auth/* 有 10 次/60s 的 IP 限流：教师/学生各走一次 UI 登录，
  // 之后所有 context 复用 storageState，避免连续运行触发 429。
  let teacherState = null;
  let studentState = null;

  // —— 1. 桌面端：教师全路由加载 + console 错误收集 + 截图 ——
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    hookConsole(page);
    await loginTeacher(page);
    teacherState = await ctx.storageState();
    record("教师登录", true);
    for (const route of TEACHER_ROUTES) {
      await page.goto(`${FRONTEND}/teacher/${route}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(400);
      const text = await page.locator("body").innerText();
      record(`教师页 /${route} 非白屏`, text.trim().length > 50);
      await page.screenshot({ path: join(OUT_DIR, `teacher-${route}-desktop.png`), fullPage: true });
    }
    await ctx.close();
  }

  // —— 2. 学生端：登录 + 作业列表渲染 + 截图 ——
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    hookConsole(page);
    await loginStudent(page);
    studentState = await ctx.storageState();
    record("学生登录", true);
    await page.getByText(ASSIGNMENT).first().waitFor({ timeout: 10000 });
    record("学生作业列表渲染", true);
    const bodyText = await page.locator("body").innerText();
    record("状态列无英文状态码", !/\b(uploaded|grading|graded|failed_\w*)\b/.test(bodyText), "");
    await page.screenshot({ path: join(OUT_DIR, "student-upload-desktop.png"), fullPage: true });
    await ctx.close();
  }

  // —— 3. 响应式：320/375 无整页横向溢出（回归保护：CSS Grid min-content 传播）——
  for (const vw of [320, 375]) {
    const ctx = await browser.newContext({ viewport: { width: vw, height: 812 }, storageState: teacherState });
    const page = await ctx.newPage();
    let worst = 0;
    for (const route of TEACHER_ROUTES) {
      await page.goto(`${FRONTEND}/teacher/${route}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(400);
      const w = await page.evaluate(() => document.documentElement.scrollWidth);
      if (w > worst) worst = w;
      if (w > vw) record(`溢出检查 ${vw}px /${route}`, false, `scrollWidth=${w}`);
    }
    record(`教师 6 路由无横向溢出 @${vw}px`, worst <= vw, `max scrollWidth=${worst}`);
    if (vw === 375) {
      await page.goto(`${FRONTEND}/teacher/assignments`, { waitUntil: "networkidle" });
      await page.locator(".data-table tbody tr").first().waitFor({ timeout: 8000 }).catch(() => {});
      await page.screenshot({ path: join(OUT_DIR, "teacher-assignments-mobile.png") });
    }
    await ctx.close();
  }

  // —— 4. 移动端学生页：sticky 操作列可直接点击 ——
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, storageState: studentState });
    const page = await ctx.newPage();
    await page.goto(`${FRONTEND}/student`, { waitUntil: "networkidle" });
    await page.locator(".data-table tbody tr").first().waitFor({ timeout: 10000 });
    const btn = page.getByRole("button", { name: /重新提交|提交作业/ }).first();
    const box = await btn.boundingBox();
    const inViewport = !!(box && box.x >= 0 && box.x + box.width <= 375);
    await btn.click({ trial: true });
    record("移动端提交按钮无需滚动可点", inViewport, JSON.stringify(box));
    await page.screenshot({ path: join(OUT_DIR, "student-upload-mobile.png") });
    await ctx.close();
  }

  await browser.close();

  // React Router future flag 警告走 console.warn，需从 warning 流里检
  const routerWarnings = consoleWarnings.filter((w) => w.includes("React Router Future Flag Warning"));
  record("无 React Router future flag 警告", routerWarnings.length === 0, routerWarnings.length ? `${routerWarnings.length} 条` : "");
  record("无 console 错误", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "));

  const failed = results.filter((r) => !r.pass);
  writeResults();
  console.log(`\n结果：${results.length - failed.length}/${results.length} 通过，截图在 e2e/screenshots/`);
  process.exit(failed.length ? 1 : 0);
}

function writeResults(fatalError = null) {
  const payload = fatalError ? { fatalError: String(fatalError), results } : results;
  writeFileSync(join(OUT_DIR, "..", "last-run.json"), JSON.stringify(payload, null, 2));
}

const timeout = setTimeout(() => { console.error("E2E 总超时（5 分钟）"); writeResults("timeout"); process.exit(2); }, 300000);
main().catch((e) => { console.error("E2E 失败:", e); writeResults(e); process.exit(1); }).finally(() => clearTimeout(timeout));
