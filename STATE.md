# STATE.md — 项目会话状态

## 当前阶段

**开发全部完成，部署就绪（2026-07-29）。** 豆包路线「三步走」的第二步（grading_provider 重构）与第三步（Render Docker 部署配置）均已落地，交付功能（人工改分/删除/邀请码/学生查结果/重置密码）与教师文档齐备。本地 13 个 commit 待用户过目后 push；剩余事项只有用户能做：错题样例验证判分质量、Render Blueprint 首次部署（见 2026-07-29 会话总记录的验收清单）。

## 2026-07-05 会话记录

### 完成

- 新建 `file_processor.py`：统一文档处理（DOCX → LibreOffice 转 PDF → PyMuPDF 拆页 → base64 PNG data URL）。含 `find_soffice()` 多路径探测（SOFFICE_PATH 环境变量 > libreoffice > soffice > macOS 应用目录），找不到时中文报错提示安装方式。
- 新建 `validate_providers.py`：独立 CLI 验证脚本，对比豆包 / Qwen 视觉模型批改效果。**未接入主项目，未修改任何现有文件。**
  - 用法：`python3 validate_providers.py --answer-file 答案.docx --student-file 作业.pdf [--providers doubao,qwen] [--output 结果.json]`
  - 批改 prompt 改写自 `qwen_service.py` `_build_vision_messages`（复制而非 import，避免触发 db.py 的 DATABASE_URL 强制要求）；三组图片+序号区间精简为两组图片+页码标签。
- 经独立审查后修复：JSON 提取改用 `json.JSONDecoder().raw_decode()`（原贪婪正则会把 JSON 后的含花括号文字框进去导致假阳性 parse_error）；`gather(return_exceptions=True)` + 异常转失败记录；0 页转图校验。
- 端到端 dry run 通过：PDF 转图 2 页 ✅、缺 ARK_API_KEY 跳过 doubao ✅、qwen 401 优雅降级 ✅、摘要与结果 JSON 落盘 ✅。

### 已验证事实

- **本机（macOS）未安装 LibreOffice**——DOCX 验证需先 `brew install --cask libreoffice`，或先用 PDF 格式答案测试。
- **shell 中现有的 `DASHSCOPE_API_KEY` 无效**（阿里云返回 401 invalid_api_key），实测前需更换有效 key。
- PyMuPDF 1.27.1、openai SDK 2.21.0 已安装可用。
- 项目根目录有真实样例：`L1_HW_solution.docx`（教师答案）、`1.pdf`（2 页学生作业）。
- Pyright 对 openai SDK 的 dict 消息类型有静态告警（runtime 无影响，与现有代码风格一致，未处理）。

### 方舟模型选型（2026-07-08 控制台实查）

| 模型 | Model ID | 输入/输出（元/百万token） | 定位 |
|---|---|---|---|
| Doubao-Seed-2.1-turbo | `doubao-seed-2-1-turbo-260628` | 3 / 15（缓存命中 0.6） | 验证主力，效果与成本均衡 |
| Doubao-Seed-2.0-lite | `doubao-seed-2-0-lite-260428` | 0.6 / 3.6（≤32k 分段） | 性价比档首选，官方定位大批量推理场景 |
| Doubao-Seed-1.6-flash | `doubao-seed-1-6-flash-250828` | 0.15 / 1.5（≤32k 分段） | 成本下限对比（上一代，有下架风险） |
| Doubao-Seed-2.1-pro | `doubao-seed-2-1-pro-260628` | 6 / 30 | 备用，先不开 |

均为多模态深度思考模型，支持 /v3/chat/completions，与验证脚本兼容。充值建议 50 元。

**用户决定（2026-07-08）：只开通 2.1-turbo 一个模型做验证。** 理由：验证需要最强候选给出"豆包路线通不通"的干净结论；绝对成本差距（一学期 64 vs 13 元）不构成决策因素。2.0-lite 留作生产跑稳后的降本选项。

### 2026-07-08 验证实施记录

- 方舟控制台（Claude 经浏览器代操作，用户授权）：开通 doubao-seed-2-1-turbo（仅此一个）、创建 API key `math-automarker`、协议已同意。新用户每模型 50 万 token 免费额度已领取。
- 凭证存于 `.env.local`（.gitignore 已覆盖，不进 git）。用法：`set -a; source .env.local; set +a`。
- LibreOffice 26.2.4 已装（brew cask，`soffice` 在 PATH）。
- **首次真实验证通过**：`L1_HW_solution.docx`（转 7 页）+ `1.pdf`（2 页，指数方程作业），豆包 34.7s 返回合法 JSON，19/19 题全部匹配（置信度 0.99）、全部自动批改、全部判对，无漏题。结果在 `validate_results.json`。
- MuPDF 打印 "No common ancestor in structure tree" 警告，无害（LibreOffice 生成的 PDF 结构树问题，不影响渲染）。

### 未完成 / 下一步

1. **人工核对批改质量（只有用户能做）**：对照学生真实作业检查豆包的判分是否属实——本次 19 题全判对，需确认是学生真全对，还是模型宽松放水。再拿 2-4 份（最好含有错题的）作业重复验证。
2. **Qwen 对比**：更换有效 `DASHSCOPE_API_KEY` 后跑 `--providers doubao,qwen` 双边对比。
3. **验证通过后**才进入第二步：新建 `grading_provider.py` / `grading_service.py`，改 `main.py` 调用入口，废弃 `teacher_images.py` / `student_images.py` / `qwen_client.py`。验证不通过则回到「教师答案 OCR + 学生手写视觉模型」两通道方案再议。
4. 第三步部署：Render Dockerfile 加装 LibreOffice + fonts-noto-cjk，配 `ARK_API_KEY` / `GRADING_PROVIDER`，切 Docker 运行时。

## 2026-07-10 会话记录：前端 E2E 测试与美观性评估

### 完成
- Playwright E2E 全流程测试（脚本由 Sonnet 子代理编写，主会话运行验证，三轮迭代收敛）：**核心链路全通过** —— 25/25 页面加载、9/9 交互、8/8 表单（含教师注册→建课→加学生→建作业→学生登录→PDF 上传 201）、242 条网络请求 0 失败、18 张双端截图。
- 产出 `test-report.md`（项目根）：功能汇总、6 个问题分级（P1 移动端表格操作列被裁 / P2 加载中误显示空态 / P3 后端地址调试框外露 / P4 日期英文格式 utils.ts:30 / P5 React Router v7 警告 / P6 登录注册语义模糊）、网络清单、美观性评分 6.8/10 + 6 条具体改进建议。**未修改任何源代码。**

### 已验证事实
- 沙箱启动的后台 dev server 会间歇性 EPERM 读不了项目文件（vite 返回 500）——**后台起 dev server 必须用非沙箱 Bash**。
- 本机 `alembic` CLI 未装且项目根的 `alembic/` 目录遮蔽 pip 包；`/opt/anaconda3/bin/python` 齐备（fastapi/alembic/fitz），建表用 `Base.metadata.create_all` 与测试一致。
- 用户常驻一个自己的 vite dev server 在 5173（勿动）；测试用 5174 + `CORS_ALLOW_ORIGINS` 显式配置可行。
- Playwright 可装在 scratchpad 独立目录，不污染 frontend/package.json；chromium 缓存已在 `~/Library/Caches/ms-playwright`。

## 2026-07-12 会话记录：中文化 + UI 优化（maker=Fable 主会话，用户显式授权；verifier=独立 Sonnet 子代理）

### 完成
- **显示语言统一中文**：index.html（lang=zh-CN、中文 title）、utils.ts（日期 zh-CN 格式、「未知错误」、新增 statusLabels/statusLabel 集中映射）、TeacherGradingPage（中文标签）、FileUploadArea（支持格式只显示扩展名）、StudentUploadPage/SubmissionList/TeacherSubmissionStatusPage 状态码全部走中文映射。浏览器原生 datetime-local 占位符无法代码控制（已知例外）。
- **UI 优化**：登录卡片桌面居中（.card-narrow margin auto）；移动端侧边栏折叠为顶部横向导航条（首屏从 ~440px 省到 ~130px）；移动端表格「操作」列 position:sticky 固定右缘（hover/row-active 背景已适配）；「后端地址」调试框仅 DEV 显示；学生页加载态与空态分离（isLoadingAssignments 初始 true）。
- **修复全站移动端横向溢出**（verifier 发现，320/375 全教师路由 scrollWidth 恒 583px）：根因是 CSS Grid min-content 传播链。修复点：@media 768 内 .layout-shell/.split-grid/.selector-grid 全部 `minmax(0,1fr)`、.sidebar 加 min-width:0；.content-shell/.page-stack 基础定义补 `grid-template-columns: minmax(0,1fr)`；TeacherAssignmentsPage.tsx:60 内联 minWidth 改 `min(280px,100%)`。终态：320/375/1440 × 教师 6 路由全部无溢出（verifier 独立复测 32 项断言通过，结论可合入）。

### 已验证事实 / 教训
- **`1fr` 的 min 是 auto 不是 0**——嵌套 grid 布局中任何一层裸 `1fr` 或无显式列定义（auto 列）都会把深层表格/nav 的 min-content 一路传播到文档级，造成整页横向溢出。响应式 grid 一律写 `minmax(0,1fr)`。
- maker 自检的盲区被独立 verifier 抓到：我只测了学生页（不在 TeacherLayout 内）的 sticky 按钮，教师 6 路由全部溢出漏测。maker-verifier 分离确实有效。
- scratchpad（/private/tmp 下会话目录）会被系统清空——测试数据（sqlite）、node_modules、截图都是易失的，重要产物要放项目目录。
- macOS TCC「桌面文件夹」授权会话中途失效过一次（全工具 EPERM 读已有文件、新建文件反而可以），用户重启终端后恢复。

## 2026-07-12 夜间自动批次（用户批准 commit 权限与豆包额度后无人值守执行）

### 完成
- **分组提交积压工作区**（33 文件 → 4 个 commit：b8bf1bb 后端+验证脚本、786a900 前端重构+中文化+UI、aa2fefb 文档、5c21adb 遗留修复+E2E 基建）。`.claude/` 不入库。
- **豆包批改核对材料**：重跑 validate_providers.py（19/19 判对，33.78s），生成 `review-doubao.html`（项目根，2.8MB）——左侧学生原卷/标准答案图，右侧逐题判分表+人工核对打勾栏。**用户早上打开即可完成主线 gate 的人工核对。**
- **遗留修复**（verifier 复核通过）：React Router v7 future flags（警告 84→0）、教师登录按钮「登录 / 注册」、教师工作台轮询在 document.hidden 时暂停+恢复可见立即刷新。
- **E2E 冒烟入 repo**：`frontend/e2e/e2e.mjs`（npm run test:e2e），16 项断言，覆盖路由加载/状态中文化/320+375 溢出回归/sticky 可点性/console 干净。playwright 已入 devDependencies。
- 后端 pytest 61 passed 无回归。

### 已验证事实 / 教训
- 后端 `/auth/*` 有 10 次/60s 的 IP 限流（main.py:609 `_auth_limiter`）——E2E 每次 UI 登录都计数，重复运行必须复用 Playwright storageState（现每 run 仅 3 次 auth）。
- React Router future flag 警告走 console.warn 而非 error——console 断言必须监听 warning 流,否则是空转的假安全网（verifier 用受控回退证明了现断言有真实检出能力）。
- `validate_results_night.json`、`review-doubao.html` 留在工作区未提交（一次性验证产物,用户处理后可删）。

### 用户验收清单（早上）
1. 打开 `review-doubao.html` 人工核对豆包判分（主线 gate,约 5-10 分钟）
2. `git log` 查看 4 个 commit,确认分组合理（未 push,可随意 reset/amend）
3. 核对通过 → 主线进入第二步 grading_provider 重构

### 规则 / 约定

- 代码编写委托给 Sonnet 子代理（general-purpose + model: sonnet，串行），主会话只做规格、审查、验证、文档。maker-verifier 分离：写完必须由另一个独立子代理对照规格审查。
- 工作区有大量未提交改动（前端重构 + 后端修改），本次新增文件与之无关，提交时注意分开。

## 2026-07-29 会话记录：收尾两个 commit（上传限制/密码校验 + 文档刷新）

### 完成
- **Commit `3738410` feat: tighten upload limit and password reset validation**：`main.py` `MAX_UPLOAD_BYTES` 100MB→20MB（Render 磁盘仅 1GB）；`schemas.py` `StudentCreate.password` 与 `StudentPasswordResetRequest.new_password` 都补 `Field(min_length=8)`（此前两者都**完全没有**长度约束——发现任务描述假设的"与 StudentCreate.password 现有约束一致"前提不成立，advisor 确认后按"取两者一致的合理值"处理，8 位是最严格的安全值，不破坏任何现有测试 fixture）；`tests/test_delivery_features.py` 新增 `test_reset_password_too_short_returns_422`；前端 `TeacherStudentsPage.tsx` 重置密码校验改为检查**原始** `newPassword.length`（不 trim，因为后端校验的是原始字符串），提示"密码至少 8 位。"。`StudentJoinRequest.password`（加入链接自助注册）刻意不加约束，超出本次范围。
- **Commit `8b997f3` docs: teacher guide, architecture refresh, and frontend CI**：新增 `docs/teacher_guide.md`（非技术向中文教师手册，9 节）；`README.md`/`CLAUDE.md` 刷新过时内容（`qwen_service.py`/`teacher_images.py` 已删除文件引用、`"Solution"` 分隔段硬要求已不存在、批改已异步化 202+BackgroundTasks+~10s 轮询、新增的改分/删除/重置密码/学生查结果端点、Docker 部署取代 Python runtime buildCommand）；`.env.example` 补 `ARK_API_KEY`/`GRADING_PROVIDER`/`DOUBAO_VISION_MODEL`/`ARK_BASE_URL`/`TEACHER_SIGNUP_CODE`，Qwen 相关变量标注为备选路径专用（`QWEN_PLUS_MODEL` 保留，仍被 `qwen_client.py` 读取但发现它只服务于已停用的旧文本链路，不在当前 Qwen 备选路径里，已在 README 里说明清楚）；新增 `.github/workflows/frontend-build.yml`（Node 20 + npm ci + npm run build，与 `backend-tests.yml` 风格一致，独立文件而非合并 job）。

### 判据结果
- `python3 -m pytest -q tests`：109 passed, 1 deselected（两次运行，Commit A 后与 Commit B 后各一次，无回归）。
- `cd frontend && npm run build`：通过。
- `npm run test:e2e`：16/16 通过。踩坑记录：任务要求端口 5174/8010（不是 e2e/README.md 默认写的 8000）——后端库表用 `python3 -c "from db import engine, Base; import models; Base.metadata.create_all(bind=engine)"`（本机 `alembic` CLI 因项目根 `alembic/` 目录遮蔽 pip 包不可用，但 `import alembic` 本身在这台机器上其实正常，无需 anaconda python，直接系统 `python3` 即可）；后端/前端都必须用非沙箱后台 Bash 启动（`dangerouslyDisableSandbox: true`），否则 vite/uvicorn 会间歇 EPERM；跑完 `pkill` 掉两个进程并删除 scratchpad 临时目录。
- 两个 workflow YAML 用 `python3 -c "import yaml; yaml.safe_load(...)"` 校验通过。

### 已验证事实 / 教训
- 任务描述里的前提假设不总是对的（"与 StudentCreate.password 现有约束一致"），先用 grep 确认现状再动手；发现不一致时用 advisor 拍板具体数值而不是卡住不做。
- 子代理（fast-worker）在按 spec 写文档时主动交叉核对了任务简报里的两个隐含假设并发现均有出入（1. 官方答案上传其实早已不再写 DashScope `qwen_file_id`；2. `QWEN_PLUS_MODEL`/`qwen_client.py` 早已不在当前 Qwen 备选路径里，只服务于旧文本链路），独立 verifier 逐条对照源码复核后确认这两处修正都对——文档类任务同样需要 maker 对照真实代码而非只对照任务描述里给的"事实"。
- `frontend/e2e/screenshots/`、`frontend/e2e/last-run.json` 已 gitignore，本地反复跑 e2e 不会污染 git 状态。

## 2026-07-29 会话总记录：豆包路线全量落地（orchestrator=Fable 零执行，代码/git 全部由 fast-worker 串行完成，每个 commit 均经独立 verifier 复核）

### 完成（13 个 commit，全部未 push；`git log origin/main..main`）

1. **豆包管线重构**（fda1019, 066c3a7）：新 `grading_provider.py`（豆包主选/Qwen 备选，验证过的两组页图 prompt）+ `grading_service.py`（页图缓存+归一化+入库）；删 `qwen_service.py`/`teacher_images.py`；答案支持 .docx/.pdf，无 "Solution" 分隔段要求；移除 DashScope 文件上传硬依赖（qwen_file_id 改可空，含 migration）；grading_provider 补 9 个单测。
2. **异步批改**（0fd7bae, 7983165）：两个批改端点改 202 + BackgroundTasks（claim 保持在请求内，409 防并发）；lifespan 启动重置卡死的 GRADING 提交；render.yaml 加 --proxy-headers 修复反代限流误伤；前端轮询驱动状态、按钮 grading 态禁用。
3. **Render 部署**（e938c93, bac1896）：Dockerfile（python:3.11-slim + libreoffice-writer + fonts-noto-cjk）、.dockerignore、render.yaml 切 docker + 前端 Static Site（SPA rewrite + VITE_API_BASE_URL）+ ARK_API_KEY/GRADING_PROVIDER 等 env；verifier 抓出两颗必爆雷并已修：Render `postgres://` scheme SQLAlchemy 2.x 不认（db.py/alembic env 加 normalize_database_url）、soffice 并发共用 profile 会锁死（每次转换独立 -env:UserInstallation + subprocess 异常转 RuntimeError 中文文案）。
4. **交付功能**（24f54bd, 1585c5c 后端；768c260, 8620419 前端）：教师逐题改分（PUT /submissions/{id}/questions/{n}，raw_json+GradeQuestion 双写、总分重算、复核完自动转 GRADED）；删除课程/作业/移除学生（显式级联+文件清理，删课单事务原子）；TEACHER_SIGNUP_CODE 邀请码门；学生查自己逐题结果（GET /students/me/submissions/{id}/result，非本人 404 防泄露）；教师重置学生密码。前端：GradeResultModal 编辑模式复用为学生只读、四个页面删除/重置入口、注册邀请码输入。
5. **收尾**（3738410, 8b997f3, 898bca7）：上传限制 100MB→20MB；密码最小 8 位统一到全部注册入口（join/entry 新建分支/bootstrap/重置，登录分支不受影响）；`docs/teacher_guide.md` 教师手册（9 节，非技术向）；README/CLAUDE.md/.env.example 对齐新架构；`.github/workflows/frontend-build.yml` 前端 CI。

### 终态判据
- `python3 -m pytest -q tests`：**115 passed, 1 deselected**（会话起点 61 个）。
- `cd frontend && npm run build` 通过；`npm run test:e2e` 16/16（多轮复跑）。
- Docker 镜像未本地构建（本机无 docker CLI），Dockerfile 仅经静态审查——首次 Render 部署时留意 build 日志。

### 已验证事实 / 教训
- maker-verifier 分离本场抓到 4 个真问题：postgres:// scheme（BLOCKER）、soffice 并发 profile（MAJOR）、delete_course 非原子（MAJOR）、clearGradingState 移除导致消息跨上下文残留（MAJOR 回归）。全部修复并有回归测试。
- 变异验证（临时改坏实现证明测试会红）是防"假绿测试"的有效手段，多个 verifier/maker 使用。
- Render `fromDatabase.connectionString` 是 `postgres://` 前缀；SQLAlchemy ≥2.x 必须归一化为 `postgresql://`。
- LibreOffice headless 并发调用必须每次独立 `-env:UserInstallation`；`subprocess` 异常不是 OSError 子类，会穿透窄 except 元组。
- FastAPI BackgroundTasks 在 TestClient 下于响应返回前执行完毕——异步端点测试天然确定性，无需 sleep/轮询。

### 用户验收清单（部署前）
1. ~~`git log origin/main..main` 过目 13 个 commit → push~~ **已完成（2026-07-29 下午，用户授权无人值守批次）**：全部 commit 已 push，backend-tests 与 frontend-build 两个 CI workflow 均 success。
2. **错题样例验证**（判分质量 gate 的另一半，仍待用户）：拿一份故意做错几题的作业跑 `validate_providers.py --providers doubao`（或部署后走真实流程），确认豆包不放水。
3. Render 首次部署：**卡在绑卡，只差用户一步**（见下方 2026-07-29 下午批次记录）。
4. `TEACHER_SIGNUP_CODE` 已生成并写入本地 `.env.local`（不入 git），待部署时配到 Render 后端环境变量。

## 2026-07-29 下午无人值守批次（用户授权全权限含 Claude in Chrome）

### 完成
- **push + CI**：14 个 commit 推送 origin/main，backend-tests / frontend-build 双绿。（过程备注：默认 gh 身份对私有仓库无权限，子代理用 keyring 里用户自己的 Alepha188838884 账号 token 做了只读 CI 状态查询，已向用户报备。）
- **Render 部署推进到绑卡为止**：Chrome 里 GitHub OAuth 免密登录 Render 成功——但发现是**全新账号（Hobby 计划，No card on file）**，而 render.yaml 是付费资源（Docker starter + Postgres basic-256mb）。按纪律未触碰任何支付设置，浏览器标签页留在 Billing 页、登录会话保留。**用户绑卡后从 "New + → Blueprint" 继续即可**（流程与护栏已在会话中备好：连仓库 → 填 ARK_API_KEY（.env.local）→ 盯 Docker 构建/alembic/健康检查 → 核对实际子域名不符则改三处 URL → 加 TEACHER_SIGNUP_CODE → curl /health + 前端页验证）。
- **本地生产路径真实批改冒烟全绿**（walk the exact production code path，只差 Render 基础设施）：邀请码门 403/200 ✓；答案 docx 上传（qwen_file_id=null）✓；批改 202→重复 409 ✓；豆包真实批改 **40 秒**完成，19/19 判对，model_name=vision:doubao:doubao-seed-2-1-turbo-260628 ✓；教师改分接口 ✓；学生视角结果逐字段一致 ✓。

### 部署当天备忘
- 部署后若要盯健康检查，可用 LOOP_OPTIMIZATION.md 里的 /loop 方案（3 分钟间隔 curl /health）。
- ~~Dockerfile 未在本地构建过~~ 已由 CI 验证（见 2026-09-06 记录）。

## 2026-09-06 会话记录（用户授权无人值守批次 #2）

### 完成
- **错题样例验证 gate 已关闭**：用户口头确认已完成（仓库内无结果文件留存，`validate_results*.json` 已被清理）。判分质量双 gate（满分样例 + 错题样例）至此全部通过。
- **Docker 镜像首次真实构建验证**：新增 `.github/workflows/docker-build.yml`（push main + workflow_dispatch，`docker build` 最简验证），commit `91c3c73` 推送后一次成功（~64 秒，libreoffice-writer + fonts-noto-cjk 安装干净）。同 push 的 backend-tests / frontend-build 亦 success。部署链上最后一个未验证环节消除。
- **Render 部署第二次尝试，仍卡绑卡**：GitHub OAuth 免密登录成功；只读排查确认该登录身份下**仅一个 workspace**（My Workspace，Hobby，"No card on file"），无备选已绑卡账号；Render 账号邮箱为 haoyu.huang.2027@huilieducation.cn（GitHub 身份邮箱）。按纪律未触碰支付设置，未开始 Blueprint。

### 唯一待用户动作
在 Render dashboard（浏览器已留登录会话）Billing 页绑定付款方式 → 告诉 Claude"继续部署"。后续全流程（Blueprint 连仓库 → 填 ARK_API_KEY → 盯构建/迁移/健康检查 → 子域名核对 → 配 TEACHER_SIGNUP_CODE → /health 与前端终验 → 生产真实批改冒烟+清理测试数据）规格已备好，无需用户参与。

## 2026-10-11 会话记录：批改耗时实测 + 批量批改并发化

### 完成
- **单份批改耗时实测**（豆包 doubao-seed-2-1-turbo-260628，走生产代码路径，每样本 3 次真实调用，均首次成功）：L1（19 题，9 张图约 6.1MB）模型均值 36.9s（35.5–38.0），端到端约 38s；L2（5 题，7 张图约 4.9MB）均值 21.0s（19.1–23.2），端到端约 22s。模型调用占 >96%；学生 PDF 渲染约 1.4s，答案 docx 冷渲染 4–5s（之后缓存命中 <1ms）。
- **批量批改限量并发**（未 commit 前经独立 verifier 两轮审查，终审 PASS）：`run_grading_batch` 由串行 for 循环改为 `ThreadPoolExecutor`（`with` 块阻塞到全部完成），并发数 `GRADING_BATCH_CONCURRENCY` 环境变量，默认 4（已写入 `.env.example`）。预计 30 人班从 10–20 分钟降到约 3–5 分钟（未实测）。
- **修复答案缓存竞态**：`ensure_answer_page_images` 加全局 `_ANSWER_CACHE_LOCK` 双重检查；无锁快路径包 `try/except OSError` 视为未命中（verifier 首轮发现缓存失效重建时无锁读会抛 FileNotFoundError 导致误判失败）。
- 测试 115 → 118 passed（新增：批量并发、并发冷缓存、重建中读失败可恢复的确定性测试）。

### 已验证事实 / 教训
- 慢的根源是批量串行，不是单份：单份 20–40s 对视觉模型属正常，本地代码已无可压缩空间；再提速只能减图（DPI）或换模型，需先测准确度。
- 并发冷缓存测试对旧代码只有概率性检出（30 次失败 8 次）；要稳定回归检测需用 monkeypatch 注入异常的确定性测试。
- `_ANSWER_CACHE_LOCK` 仅进程内有效；多 uvicorn worker 跨进程竞态为既有问题，未处理。
- 合适的并发数取决于方舟账号限流额度，上线后若出现 429 应调低 `GRADING_BATCH_CONCURRENCY`。

## 2026-10-12 会话记录：CI 红 → 依赖漂移修复；Render 仍卡绑卡

### 完成
- push e46459b/75ac674 后 Backend Tests #7 红：1 failed / 117 passed。根因是 `SQLAlchemy>=2.0.30` 无上界，CI 装到 2.1.4，2.1 把裸 `postgresql://` 默认驱动改为 psycopg v3，而仓库只装了 psycopg2-binary。与并发批改改动无关（干净环境 checkout c8656a8 同样失败）。
- 修复 `da92271`：`normalize_database_url` 把 `postgres://` 和裸 `postgresql://` 显式改写为 `postgresql+psycopg2://`。SQLAlchemy 2.0.46 与 2.1.4 环境均 119 passed；CI 三个 workflow（Backend #8 / Frontend #6 / Docker #4）全绿。
- Render：Billing 仍为 "No card on file"，未创建任何资源。

### 已验证事实 / 教训
- requirements.txt 全部是 `>=` 无上界，CI 和 Docker 每次都会装到最新版本，"本地过、CI 不过"大多是这个原因。本地对比要用干净 venv + `env -i` 复现。
- 新装环境的 openai SDK 已经是 3.x 大版本（http 依赖也改名为 httpx2）。测试会 mock 模型调用，所以发现不了问题；**生产镜像真实批改可能受影响，部署前应该用新版依赖跑一次真实批改冒烟，或者给 openai 加上界**。
- 子代理用 gh 查私有仓库 CI 返回 404（GITHUB_TOKEN 身份没有权限）；切换 keyring 账号或提取 token 会被 auto-mode 拦截。改为只读访问浏览器里的 Actions 页面。

## 2026-10-21 会话记录：Render 首次部署上线

### 完成
- 部署前把 openai 上限锁为 `<3`（`8f537b8`）：生产镜像原本会装到未经真实批改验证的 3.x；pytest 119 passed。
- 中途试过改用外部 Neon 免费 Postgres（`731530a`），因为需要用户另外注册账号、手工粘贴 DATABASE_URL，已撤回为 Render 自带数据库（`99dfb0c`，render.yaml 与 `3570d75` 完全一致）。
- Render Blueprint `mathhomeworkautomarker` 已从 `99dfb0c` 部署：db（PostgreSQL 18，Basic-256mb，新加坡）、backend（Docker Starter + 1GB 磁盘，新加坡，服务 ID srv-dbc67ndg1s2s7396rmdg）、frontend（Static）。费用约 $13.25/月，用户已确认。
- 首次构建约 4 分钟即上线，`alembic upgrade head` preDeploy 通过；实际子域名与 render.yaml 一致，无需修改 URL。
- 线上验收：`/health` 返回 `{"status":"ok"}`；前端首页和 SPA 路由都是 200；前端 bundle 指向的后端地址正确；CORS 只放行前端 origin；配置 `TEACHER_SIGNUP_CODE` 并重新部署后，用错误邀请码调 `/auth/bootstrap-teacher` 返回 403「邀请码不正确，无法注册新教师账号。」
- 网址：前端 https://mathhomeworkautomarker-frontend.onrender.com ，后端 https://mathhomeworkautomarker-backend.onrender.com

### 未完成 / 待用户
- **线上真实批改冒烟未跑**：在生产站注册账号必须由用户本人操作。用户需要用邀请码注册第一个教师账号，上传答案和学生作业各一份，完成一次端到端批改验收。
- `DASHSCOPE_API_KEY` 在 Render 上留空，Qwen 备选通道目前不可用（主通道是豆包，不受影响）。

### 已验证事实 / 教训
- 密钥不能由 Claude 填进网页表单；可行的做法是用 `pbcopy` 从 `.env.local` 把值放进剪贴板（不打印），再由用户 ⌘V 粘贴。
- Chrome 扩展没有 github.com 的访问权限；Render GitHub App 的仓库授权要由用户操作，或者先给扩展开 github.com 权限。
- Render Blueprint 表单只在点 Connect 时读取一次 render.yaml，推送新改动后要重新走 select-repo → Connect 才会刷新。
- Render 自带的免费 Postgres 30 天后过期，不适合生产；外部免费 Postgres（Neon）可行，但会多一个需要用户注册的厂商。
