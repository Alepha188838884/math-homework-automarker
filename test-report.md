# 前端自动化测试与美观性评估报告

> **📌 修复状态更新（2026-07-12）**：本报告发现的问题已全部修复并经独立 verifier 复核。
> - P1 移动端表格操作列被裁 → 已修（操作列 sticky 固定右缘 + 根治全站移动端横向溢出，320/375/1440 三视口 × 教师 6 路由实测无溢出）
> - P2 加载中误显示空态 → 已修（loading/空态分离，`isLoadingAssignments` 初始 true）
> - P3 后端地址调试框外露 → 已修（仅 DEV 构建显示）
> - P4 日期英文格式 → 已修（zh-CN 本地化，全站显示语言统一中文，含状态码中文映射）
> - P5 React Router v7 警告 ×84 → 已修（BrowserRouter future flags，警告归零）
> - P6 登录/注册语义模糊 → 已修（教师登录按钮改「登录 / 注册」）
> - 轮询负载 → 已优化（页面不可见时暂停，恢复可见立即刷新）
> - 美观性建议 1/2/3/4/5/6 全部落地（移动端横向导航条、sticky 操作列、登录卡片居中、日期本地化、加载态分离、调试框收纳）
>
> E2E 测试已收编入 repo：`cd frontend && npm run test:e2e`（见 `frontend/e2e/README.md`），当前 16/16 通过，支持重复运行。

- **测试日期**：2026-07-10
- **测试对象**：前端 `http://localhost:5174`（Vite dev）+ 后端 `http://127.0.0.1:8000`（uvicorn，临时 sqlite，空库起测）
- **工具**：Playwright（chromium headless），脚本与原始结果见文末附录
- **范围**：9 个路由 × 未登录/已登录、全业务流程（教师注册→建课→加学生→建作业→学生登录→PDF 上传）、全量网络监听、18 张双端截图

---

## 一、功能测试结果汇总

| 类别 | 通过 | 警告 | 失败 | 说明 |
|---|---|---|---|---|
| 页面加载（25 项） | 25 | 0 | 0 | 全路由无白屏；未登录访问受保护路由均正确重定向到登录页 |
| 交互元素（9 项） | 9 | 0 | 0 | 刷新/切换/生成链接/复制等按钮行为均符合预期，点击后无 console 报错 |
| 表单流程（8 项） | 8 | 0 | 0 | 详见下表 |
| 网络请求（242 条） | 239 | 3 | 0 | 3 条 warn 为页面导航取消的 ERR_ABORTED，非故障 |
| 截图（18 张） | 18 | 0 | 0 | 9 页面 × 桌面 1440px / 移动 375px |

### 表单流程明细

| # | 流程 | 结果 | 验证点 |
|---|---|---|---|
| 1 | 教师注册（`/auth/teacher/entry` 新账号） | ✅ | 注册后跳转 `/teacher/courses` |
| 2 | 创建班级「五年级数学E2E」 | ✅ | 列表即时出现新班级 |
| 3 | 手动添加学生（高级管理面板） | ✅ | 学生列表更新 |
| 4 | 创建作业「E2E测试作业」 | ✅ | 作业表格更新（截止日期/答案文件为可选项，未填） |
| 5 | 教师登出 → 学生登录 | ✅ | 跳转 `/student`，作业列表含新作业 |
| 6 | 学生上传 PDF | ✅ | `POST /assignments/1/submissions/me` 返回 **201**，DB 落库 `status=uploaded` |
| 7 | 负路径：教师错误密码 | ✅ | 页面显示中文错误 `HTTP 401: 邮箱或密码错误。` |
| 8 | 负路径：学生账号不存在 | ✅ | 页面显示 `登录失败：账号或密码错误。如果你是首次使用，请先通过老师提供的班级加入链接完成注册。` |

**结论：核心业务链路（教师建课发作业 → 学生登录交作业）端到端全部通过，无阻塞性 bug。**

---

## 二、发现的问题（按严重程度排序）

### P1（中）：移动端表格溢出，关键操作按钮默认视口外
- **现象**：375px 宽度下，学生上传页作业表格的「状态」列被截半、「操作／提交作业」按钮完全在视口外；教师端作业管理表格同样被裁。`.table-wrap` 有 `overflow-x: auto` 所以能横向滚动，但没有任何滚动提示，学生在手机上很容易找不到提交按钮。
- **复现**：手机（或 375px 视口）→ 学生登录 → `/student` → 查看作业列表。
- **证据**：截图 `student-upload-mobile.png`、`teacher-assignments-mobile.png`。

### P2（中）：作业列表加载中误显示空态文案
- **现象**：`/student` 页数据请求还在进行时，页面同时显示「加载中...」和「当前没有可提交的作业，请联系老师发布作业后再试」。慢网络下学生会先看到误导性的空态提示。
- **原因**：`frontend/src/components/StudentUploadPage.tsx:97` 只判断 `assignmentsOverview.length === 0`，未区分 `isLoadingAssignments`（该状态存在但只用于按钮文字，第 92 行）。
- **复现**：弱网或首次冷加载进入 `/student`，前 1 秒内可见。

### P3（低）：班级管理页暴露「后端地址」调试输入框
- **现象**：`/teacher/courses` 顶部有可编辑的后端 API 地址输入框 + 「应用」按钮，任何登录教师都可改写客户端 API 指向。这是开发期遗留能力，生产环境不应展示。
- **位置**：`frontend/src/teacher/pages/TeacherCoursesPage.tsx`（「班级管理」卡片）。

### P4（低）：日期显示为美式英文格式
- **现象**：作业创建时间显示 `7/10/2026, 1:37:26 PM`，与全中文界面不协调。
- **原因**：`frontend/src/utils.ts:30` 的 `date.toLocaleString()` 未指定 locale，跟随浏览器语言。

### P5（低）：React Router v7 兼容性警告 ×84
- **现象**：每次路由挂载 console 出现 2 条 Future Flag 警告（`v7_startTransition`、`v7_relativeSplatPath`），整轮测试共 84 条。不影响功能，升级 v7 前需处理。

### P6（低）：登录/注册语义模糊
- **现象**：教师与学生登录页按钮永远显示「登录」，但 `/auth/teacher/entry` 对新邮箱实际执行注册。用户无法感知自己是登录还是开新账号。另外 `main.py` 中学生自注册路径（约 465–468 行的 assignmentId 分支）当前前端永远不会触达，属死代码路径。

### 备注（非问题）
- console 中 2 条 401 error 是负路径测试（故意输错密码）产生的预期报错。
- 教师工作台每 10 秒轮询 4 个接口（`TeacherWorkspaceContext.tsx`），本轮 242 条请求中约 220 条来自轮询。功能正常，但多教师同时在线时服务器压力线性增长，可考虑改 30s 或页面不可见时暂停。

---

## 三、网络请求清单

共监听 242 条发往后端的请求，**0 条失败（4xx/5xx 均为负路径预期），0 条超时（>5s）**。

| 端点 | 次数 | 均值 | 最大 | 备注 |
|---|---|---|---|---|
| `POST /assignments/:id/submissions/me` | 1 | 1083ms | 1083ms | PDF 上传+落盘，唯一 >1s，可接受 |
| `POST /auth/teacher/entry` | 3 | 40ms | 45ms | 含 1 次预期 401（负路径） |
| `POST /auth/student/login` | 4 | 32ms | 44ms | 含 1 次预期 401（负路径） |
| `POST /courses/:id/students` | 1 | 41ms | 41ms | payload 格式正确，响应符合 `StudentPublic` |
| `GET /teachers/me/courses` | 51 | 10ms | 18ms | 轮询主力 |
| `GET /courses/:id/assignments` | 46 | 11ms | 19ms | 轮询 |
| `GET /courses/:id/students` | 46 | 11ms | 18ms | 轮询 |
| `GET /assignments/:id/submissions` | 40 | 11ms | 18ms | 轮询 |
| `GET /assignments/:id/students-status` | 40 | 12ms | 20ms | 轮询 |
| `GET /students/me/assignments` | 7 | 8ms | 17ms | 返回数据正确渲染到作业表格 |
| `POST /teachers/me/courses` / `POST /courses/:id/assignments` / `POST /courses/:id/join-link` | 各 1 | ≤13ms | — | payload 与响应结构均符合 `schemas.py` 契约 |

3 条 `net::ERR_ABORTED`（GET `/teachers/me/courses`）为路由切换时浏览器主动取消的在途请求，无影响。

---

## 四、美观性评估

### 评分表（1–10）

| 维度 | 得分 | 依据 |
|---|---|---|
| 视觉层次与排版 | 7 | 卡片分区清晰、标题层级（1.6rem→卡片题→表单 label）合理、行距 1.6 舒适；但桌面端登录页卡片（~460px）在 1200px 容器内**靠左不居中**，右侧 2/3 全空；空态页面（提交状态/提交记录）内容极少，视觉重心失衡 |
| 配色方案 | 7 | indigo 主色贯穿按钮/选中态/链接，深色侧边栏（#0f172a）与浅色内容区对比明确；正文/次要文字对比度达标。扣分：侧边栏 active 指示条用橙色，与全站 indigo 系不呼应；信息提示蓝、警示橙、错误红齐全但饱和度不完全统一 |
| 组件一致性 | 8 | `.btn` / `.card` / `.form-group` / `.data-table` 高度复用，圆角阴影统一，两个上传区（教师 DOCX/学生 PDF）同构；扣分：日期格式英文（P4）、「复制」「应用」等小按钮与主按钮视觉权重区分略弱 |
| 响应式表现 | 5 | 无页面级水平溢出，栅格正确折叠单列；但**侧边导航在移动端整块置顶占满首屏**（约 440px，每页都要先划过 6 个菜单项）；表格操作列被裁且无滚动提示（P1）；加入链接行 placeholder 被压缩截断 |
| 整体第一印象 | 7 | 干净、现代、有专业感的后台风格，中文文案完整友好；移动端体验与桌面端差距明显 |

**综合：6.8 / 10** —— 桌面端合格的后台工具颜值，移动端（恰是学生交作业的主要场景）是短板。

### 改进建议（具体可执行）

1. **移动端侧边栏改横向导航**：`frontend/src/global.css:892` 的 `@media (max-width: 768px)` 中，除 `position: static` 外，将 `.sidebar-nav`（sticky 定义在 `.sidebar`，global.css:146）改为 `display: flex; flex-direction: row; overflow-x: auto; gap: 4px`，并隐藏 `.sidebar-hint`/收缩 `.sidebar-brand`——首屏立省 ~350px。
2. **表格移动端操作列可达性**：`frontend/src/global.css:463` `.table-wrap` 在 768px 断点下给最后一列加 `position: sticky; right: 0; background: inherit`（`.data-table td:last-child`），或给 `.table-wrap` 加右缘渐隐阴影提示可滚动，确保「提交作业」按钮始终可见。
3. **登录卡片居中**：`frontend/src/global.css:283` `.card-narrow` 增加 `margin: 0 auto`，桌面端登录页视觉重心立即回正。
4. **日期本地化**：`frontend/src/utils.ts:30` 改为 `date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" })`，输出「2026年7月10日 13:37」风格，与全中文界面一致。
5. **加载态与空态分离**：`frontend/src/components/StudentUploadPage.tsx:97` 条件改为 `!isLoadingAssignments && assignmentsOverview.length === 0` 才渲染空态 alert，加载中渲染骨架或「正在加载作业列表...」。
6. **收纳调试入口**：`TeacherCoursesPage.tsx` 的「后端地址」输入框用 `import.meta.env.DEV &&` 条件渲染，生产构建自动隐藏。

---

## 五、附录

### 截图（18 张）

目录：`/private/tmp/claude-501/-Users-erichuang-Desktop-03-Projects-MathHomeworkAutomarker/ebc3f7ec-6c5e-4a9f-b01f-aca2983d9870/scratchpad/screenshots/`
（会话级临时目录，需要留存请及时拷贝）

| 页面 | 桌面 1440px | 移动 375px |
|---|---|---|
| 教师登录 | `teacher-login-desktop.png` | `teacher-login-mobile.png` |
| 学生登录 | `student-login-desktop.png` | `student-login-mobile.png` |
| 班级管理 | `teacher-courses-desktop.png` | `teacher-courses-mobile.png` |
| 学生管理 | `teacher-students-desktop.png` | `teacher-students-mobile.png` |
| 作业管理 | `teacher-assignments-desktop.png` | `teacher-assignments-mobile.png` |
| 批改中心 | `teacher-grading-desktop.png` | `teacher-grading-mobile.png` |
| 提交状态 | `teacher-submission-status-desktop.png` | `teacher-submission-status-mobile.png` |
| 提交记录 | `teacher-submission-records-desktop.png` | `teacher-submission-records-mobile.png` |
| 学生上传（有作业态） | `student-upload-desktop.png` | `student-upload-mobile.png` |

### 测试工件
- 测试脚本：scratchpad 下 `e2e-test.js`（纯 Node + Playwright，非 test-runner）
- 原始结果：scratchpad 下 `test-results.json`（pages / interactions / forms / network / consoleMessages / screenshots 六组结构化记录）
- 后端环境：临时 sqlite（空库）、`APP_DATA_DIR` 指向临时目录、无 `DASHSCOPE_API_KEY`（批改调用不在本轮测试范围）

### 测试环境备注
- 本轮未测：批改流程（依赖真实 DashScope/豆包 key）、教师答案 DOCX 上传（作业创建时该项可选）、学生 join-link 注册流（用教师手动添加学生替代，join-link 生成按钮本身已测通过）
- 源代码零修改；Playwright 安装于会话临时目录，未改动项目 `package.json`
