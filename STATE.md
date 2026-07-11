# STATE.md — 项目会话状态

## 当前阶段

多供应商重构「三步走」的 **第一步（验证）已交付脚本，等待真实 API key 实测**。
总体方案见本次对话的架构框架文档：两阶段分离（文档解析 → GradingProvider 抽象层），主选豆包、备选 Qwen。

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

### 规则 / 约定

- 代码编写委托给 Sonnet 子代理（general-purpose + model: sonnet，串行），主会话只做规格、审查、验证、文档。maker-verifier 分离：写完必须由另一个独立子代理对照规格审查。
- 工作区有大量未提交改动（前端重构 + 后端修改），本次新增文件与之无关，提交时注意分开。
