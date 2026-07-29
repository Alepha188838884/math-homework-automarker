# MathHomeworkAutomarker

一个面向中小学数学作业场景的自动批改系统。老师上传题目+标准解答文件（`.docx` 或 `.pdf`），学生上传作业 `.pdf`，后端会先做本地图像预处理，再调用视觉模型（豆包/方舟 ARK 为默认供应商，Qwen 为备选）完成按题匹配与评分；若题目匹配不确定，则把对应题目标记为“需要人工复核”。

这份 README 不是营销文档，而是给 Claude 或其他接手该仓库的开发者看的代码导览。内容以当前仓库代码、测试和部署配置为准。

## 1. 项目结论速览

- 当前正式链路是“视觉批改链路”，核心入口在 `grading_provider.py`（视觉模型接入，豆包/方舟 ARK 为主、Qwen 为备选）+ `grading_service.py`（页面图片渲染与批改编排），不是旧的文本/spec 链路。
- 官方答案文件现在支持 `.docx` 或 `.pdf`（不再只支持 docx）。
- 后端是 `FastAPI + SQLAlchemy + Alembic`，前端是 `React + Vite + TypeScript`。
- 业务对象很清晰：`Teacher -> Course -> Student / Assignment -> Submission -> GradeResult`。
- 老师端支持：建班级、生成学生加入链接、建学生、建作业、上传官方答案、批量批改、查看提交状态与批改结果。
- 学生端支持：通过班级加入链接注册、登录、查看作业概览、上传/重传 PDF。
- 当前评分结果分两类：
  - `graded`：所有题都已自动评分。
  - `needs_manual_review`：至少有一题题目匹配失败或证据不足，系统只给出自动评分小计。
- 项目对前端契约和中文错误消息有较严格测试约束，不建议随意改接口字段名、状态名或错误文本。

## 2. 这个项目到底在做什么

### 2.1 目标

项目希望把“老师发作业、学生交 PDF、系统批改、老师复核”的闭环跑通。当前实现更偏“数学图像作业批改后台”，而不是通用 LMS。

### 2.2 当前正式工作流

1. 老师登录或首次自动注册。
2. 老师创建班级。
3. 老师为班级创建作业。
4. 老师上传一份官方答案，支持 `.docx` 或 `.pdf`（不再要求 docx-only）。系统只把文件落盘，**不会**再上传到 DashScope 或记录任何远程文件 ID（`qwen_file_id` 字段仍存在于表结构中，但新上传流程始终把它写为 `null`）。
5. 学生通过班级加入链接注册，随后登录。
6. 学生上传作业 `.pdf`。同样只落盘，不上传到 DashScope。
7. 老师在批改中心触发单份批改或批量批改（`POST /submissions/{id}/grade` 或 `POST /assignments/{id}/grade-all`）。这两个接口立即返回 **202**，实际批改在 FastAPI `BackgroundTasks` 里异步执行；前端每约 10 秒轮询一次刷新状态。
8. 后端执行本地预处理（`grading_service.ensure_answer_page_images`）：
    - 官方答案是 `.docx` 时，先用 LibreOffice 转成 PDF，再逐页渲染成 PNG
    - 官方答案是 `.pdf` 时，直接逐页渲染成 PNG
    - 学生 `.pdf` 同样逐页渲染成 PNG
9. 后端把老师答案页面图片和学生作答页面图片一起喂给视觉模型（`grading_provider.call_grading_model`），不再按“题目图/解答图”分组，也不要求老师文档里有任何分隔标记——模型自己做整份文档级别的题目匹配。
10. 模型返回严格 JSON：
    - 每题是否匹配到学生对应题目
    - 是否自动评分
    - 分数 / 满分 / 对错 / 评论
11. 后端归一化结果，写入 `grade_results` 和部分 `grade_questions`。
12. 若存在未自动评分题目，则 submission 状态为 `needs_manual_review`；否则为 `graded`。

### 2.3 当前不是这样工作的内容

- 当前正式链路**不会自动走** `teacher_spec.py`、`student_parsing.py`、`grading.py`、`aggregate.py` 那套旧文本流程。
- 上传官方答案或学生作业时，**不会**再上传到 DashScope，也不会再记录 `qwen_file_id`；正式批改完全依赖**本地文件路径 + 本地图片预处理 + 视觉模型**。
- 批改不是同步接口，不会在一次 HTTP 请求里等待模型调用完成——发起批改的接口只是把 submission 置为 `grading` 并立即返回，真正的批改在后台任务里跑。

## 3. 代码地图

## 3.1 后端核心文件

### `main.py`

后端单文件主入口，承担了大部分 HTTP 路由和业务编排：

- 应用初始化与运行目录创建
- CORS 配置
- JWT 鉴权依赖
- 教师/学生登录与注册入口
- 班级、学生、作业、加入链接管理
- 官方答案与学生提交上传
- 单份/批量批改
- 提交结果与学生作业概览查询

如果你想快速理解项目，先读这个文件。

### `grading_provider.py`

视觉批改供应商接入层，当前正式批改链路的模型调用入口：

- `PROVIDER_CONFIGS`：定义豆包（`doubao`，默认）和 Qwen（`qwen`，备选）两套供应商的 base URL、API Key 环境变量、模型名环境变量
- `get_active_provider_name()`：读取 `GRADING_PROVIDER`（默认 `doubao`）决定当前用哪家
- `build_messages()`：把老师答案页面图片和学生作答页面图片按固定顺序拼进一条 vision 消息
- `call_grading_model()`：调用 OpenAI 兼容接口（`openai` SDK），带重试，解析模型返回的 JSON

刻意不 import `db.py` / `models.py`，避免这一层被 `DATABASE_URL` 之类的强依赖绑住。

### `grading_service.py`

批改流程编排，当前正式批改链路最核心的文件：

- `ensure_answer_page_images()`：把官方答案（docx 或 pdf）渲染成缓存的页面 PNG；docx 会先经 `file_processor.convert_docx_to_pdf` 转成 PDF 再拆页
- `auto_grade_homework()`：整合老师答案图片 + 学生作答图片，调用 `grading_provider.call_grading_model()`，再归一化结果
- `_normalize_vision_result()` / `_coerce_question_for_storage()`：把模型原始 JSON 转成稳定的逐题结构（分数、满分、是否自动评分等）
- `claim_for_grading()`：用 `SELECT ... FOR UPDATE` 把 submission 原子性地置为 `grading`，防止并发批改请求打架；`GRADABLE_STATUSES` 定义哪些状态允许发起批改
- `grade_claimed_submission()` / `run_grading_job()` / `run_grading_batch()`：后台任务真正执行的批改逻辑（供 `main.py` 的 `BackgroundTasks` 调用），失败时把 submission 置为 `failed_grading` 并写入中文错误信息，而不是抛出异常
- `reset_stuck_grading_submissions()`：应用启动时（`main.py` 的 `lifespan`）调用，把重启前卡在 `grading` 状态的 submission 重置为 `failed_grading`

这是最重要的“AI 批改实现文件”。

### `file_processor.py`

统一的文档转图片工具，独立脚本，不依赖项目其他模块：

- `find_soffice()`：探测 LibreOffice 可执行文件（`SOFFICE_PATH` 环境变量 > `libreoffice`/`soffice` on PATH > macOS 默认安装路径）
- `convert_docx_to_pdf()`：调用 LibreOffice headless 模式把 `.docx` 转成 `.pdf`
- `pdf_to_images()` / `process_document()`：用 `PyMuPDF` 把 PDF 逐页渲染成 base64 PNG data URL

本地跑批改（无论是 Web UI 还是 `quick_qwen_grade.py`）在处理 docx 官方答案时都需要系统里能找到 `soffice`，否则会抛出明确的中文报错提示安装方式。

### `qwen_client.py`

DashScope OpenAI-compatible client 封装。当前只被已停用的旧文本/spec 链路（`grading.py`、`teacher_spec.py`、`student_parsing.py`）引用，**不**被当前正式批改链路（`grading_provider.py`/`grading_service.py`）使用——Qwen 作为视觉批改的备选供应商时，走的是 `grading_provider.py` 里独立的 `OpenAI` 客户端构造，不经过这个文件。

### `student_images.py`

学生 PDF 的本地预处理：

- 使用 `PyMuPDF` 打开 PDF
- 每页按 `3x` 缩放渲染为 PNG
- 转为灰度图
- 保存到 `data/tmp/submissions/<submission_id>/`
- 批改后删除临时目录

### `models.py`

SQLAlchemy ORM 模型定义。是理解数据库结构和业务关系的最佳入口。

### `schemas.py`

Pydantic 请求/响应模型，定义了前端依赖的 JSON 契约。

### `auth.py`

认证与密码处理：

- JWT 创建/解析
- 基于 PBKDF2-SHA256 的密码哈希
- 兼容旧 bcrypt 哈希

### `runtime_config.py`

运行期配置入口：

- `APP_DATA_DIR`
- `FRONTEND_BASE_URL`
- `CORS_ALLOW_ORIGINS`

### `db.py` / `database.py`

数据库 engine、session、`Base`。注意 `DATABASE_URL` 在模块导入阶段就是必需的。

### `quick_qwen_grade.py`

一个离线/命令行 smoke 工具：

- 输入一份老师答案 `.docx`
- 输入一份学生作业 `.pdf`
- 直接跑正式视觉批改链路
- 输出 JSON

适合不想启动整套 Web UI 时做单次验证。

## 3.2 前端核心文件

### `frontend/src/App.tsx`

前端路由总入口。当前页面结构：

- `/teacher/login`
- `/teacher/courses`
- `/teacher/students`
- `/teacher/assignments`
- `/teacher/grading`
- `/teacher/submission-status`
- `/teacher/submission-records`
- `/student/login`
- `/student/join/:joinToken`
- `/student`

### `frontend/src/api.ts`

前端对后端接口的统一封装，也是前端契约的集中体现。任何字段变更都应先看这里。

### `frontend/src/auth/*`

教师/学生双会话上下文：

- token 恢复
- 过期自动登出
- localStorage / sessionStorage 持久化
- “单角色会话策略”

单角色会话策略的含义：

- 教师登录会清空学生会话
- 学生登录会清空教师会话

### `frontend/src/teacher/TeacherWorkspaceContext.tsx`

教师工作台的共享状态中心：

- 当前 backend base URL
- 当前选中班级 / 作业
- 学生、作业、提交、状态数据缓存
- 上传官方答案
- 单份/批量批改
- 查看结果 modal
- 轮询刷新提交状态

这是老师端前端逻辑最关键的文件。

### 教师页

- `TeacherCoursesPage.tsx`
  - 后端 URL 切换
  - 班级列表
  - 新建班级
  - 生成并复制学生加入链接
- `TeacherStudentsPage.tsx`
  - 查看班级学生
  - 手动添加学生
- `TeacherAssignmentsPage.tsx`
  - 查看作业
  - 创建作业
- `TeacherGradingPage.tsx`
  - 上传官方答案 `.docx`
  - 批量批改
- `TeacherSubmissionStatusPage.tsx`
  - 查看某作业下每个学生是否提交、是否已批改
- `TeacherSubmissionRecordsPage.tsx`
  - 查看 submission 列表
  - 触发单份批改
  - 查看批改结果 modal

### 学生页

- `StudentJoinPage.tsx`
  - 通过老师分享的 join token 注册进入班级
- `StudentLoginPage.tsx`
  - 已有账号登录
- `StudentUploadPage.tsx`
  - 查看作业概览
  - 选择当前作业
  - 上传或重传 PDF

### 其他组件

- `FileUploadArea.tsx`
  - 通用拖拽上传框
- `SubmissionList.tsx`
  - 老师端提交列表
- `GradeResultModal.tsx`
  - 展示 per-question 批改结果
- `StudentSubmissionPortal.tsx`
  - 旧的/备用的学生提交组件，当前不在主路由树里

## 3.3 已停用但保留的旧链路

下面这些文件仍在仓库里，但当前正式流程不依赖它们：

- `teacher_spec.py`
- `student_parsing.py`
- `grading.py`
- `aggregate.py`

这些模块代表一条旧的“文本/spec 批改链路”，代码中已经明确标记为 `DEPRECATED`。目前保留它们主要是为了：

- 回滚参考
- 历史兼容
- 单独研究旧方案

如果只是修当前线上/主流程，通常不应优先改这些文件。

## 4. 数据模型

数据模型定义在 `models.py`，下面是逻辑关系。

### 4.1 Teacher

- 老师账号
- 字段：`id`, `name`, `email`, `password_hash`, `created_at`

### 4.2 Course

- 一个老师拥有多个班级
- 字段：`teacher_id`, `name`, `description`, `join_token`

`join_token` 用来生成学生加入链接，并且每次重新生成都会使旧 token 失效。

### 4.3 Student

- 学生属于一个班级
- 字段：`course_id`, `name`, `email`, `password_hash`

当前模型不支持一个学生跨多个班级。

### 4.4 Assignment

- 作业属于一个老师和一个班级
- 字段：`title`, `description`, `due_date`, `max_score`

`due_date` 在写入时会被规范化为 UTC naive datetime，返回给前端时序列化为 `...Z`。

### 4.5 AnswerFile

- 一份作业对应一个官方答案文件
- 关键字段：
  - `assignment_id`
  - `original_filename`
  - `file_path`
  - `qwen_file_id`

同一作业重复上传官方答案时，会覆盖已有记录。

### 4.6 Submission

- 学生对某份作业的提交
- 关键字段：
  - `assignment_id`
  - `student_id`
  - `file_path`
  - `qwen_file_id`
  - `status`
  - `error_message`
  - `graded_at`

同一学生对同一作业重复提交时，系统只保留**最新一条记录**，并删除旧本地文件与旧评分结果。

### 4.7 GradeResult

- 一次 submission 的整体批改结果
- 关键字段：
  - `submission_id`
  - `model_name`
  - `raw_json`
  - `total_score`
  - `max_total_score`

`raw_json` 很重要，它保存了归一化后的完整审计数据，尤其是“需要人工复核”的题目。

### 4.8 GradeQuestion

- 逐题结果的扁平化表
- 只存储那些 `score` 和 `is_correct` 都非空的题目

注意：

- 对于 `needs_manual_review` 的题，完整信息存在 `grade_results.raw_json.normalized.questions` 里。
- `grade_questions` 不一定覆盖所有题。

## 5. 状态机与关键业务规则

### 5.1 Submission 状态

项目里实际出现的 submission 状态：

- `uploaded`
  - 文件已成功落盘。上传流程**不再**涉及 DashScope 或任何远程文件 ID——`qwen_file_id` 字段仍在表结构里，但新上传的 submission 始终把它写为 `null`。
- `failed_upload`
  - 保留状态，仍在 `GRADABLE_STATUSES` 里（可被重新批改），但当前上传代码路径不会再主动把 submission 置为这个状态：上传校验失败时会在文件落盘前直接返回 HTTP 错误，不创建 submission 记录。保留它主要是兼容旧数据 / 未来可能的失败场景。
- `grading`
  - 已被 `claim_for_grading()` 原子性地占用，正在后台任务里批改。应用重启时若发现 submission 卡在这个状态，会被 `reset_stuck_grading_submissions()` 重置为 `failed_grading`。
- `graded`
  - 所有题都已自动评分完成，或人工复核已全部处理完（见 §7.6 的 `PUT /submissions/{id}/questions/{question_number}`）。
- `needs_manual_review`
  - 至少有一题无法确认匹配、不适合自动评分，或人工复核尚未处理完。
- `failed_grading`
  - 本地预处理、模型调用或结果入库失败；也会在服务重启导致批改中断时被设置（错误信息固定为“服务重启导致批改中断，请重新发起批改。”）。

### 5.2 官方答案文件格式规则

当前格式要求：

- 文件必须是 `.docx` 或 `.pdf`，且是有效、非空的文件（内容与扩展名要匹配，否则上传时就会被拒绝）。
- **没有任何特殊排版要求**——不需要包含 `"Solution"` 分隔段落，也不需要区分“题目区”和“解答区”。系统只是把整份文件的每一页渲染成图片，交给视觉模型自己做题目匹配和评分。

常见失败原因：

- 空文件
- 损坏的 docx / pdf
- 文件内容与扩展名不匹配（比如把 `.docx` 改名成 `.pdf`）
- docx 转换 PDF 时找不到 LibreOffice（`soffice`），本地/自建部署环境需要单独安装

### 5.3 学生 PDF 规则

- 文件必须是有效 `.pdf`
- PDF 不能为空
- 每页会被导出为灰度 PNG

空 PDF 或损坏 PDF 会在批改时返回统一的 502 错误。

### 5.4 人工复核规则

视觉模型返回里，只要某题：

- `question_match = false`
- 或 `auto_graded = false`
- 或相关评分字段为空

则该题不会被视为完整自动评分，submission 会被置为 `needs_manual_review`。

## 6. 当前正式批改链路细节

这一段对应 `grading_service.py` 的真实实现。批改现在是**异步**的：老师点击发起批改后，接口立即返回 202，下面这些步骤都发生在 FastAPI `BackgroundTasks` 里。

### 6.1 发起批改：占用 submission

`claim_for_grading(db, submission_id)`（`grading_service.py`）：

1. 用 `SELECT ... FOR UPDATE` 锁住这一行，防止并发的批改请求互相打架
2. 只有当前状态在 `GRADABLE_STATUSES = {uploaded, failed_grading, failed_upload, needs_manual_review}` 里才允许转换；否则抛 409
3. 把状态置为 `grading`，清空 `error_message`

`main.py` 的 `POST /submissions/{id}/grade` 和 `POST /assignments/{id}/grade-all` 在请求线程里调用 `claim_for_grading()`，然后把真正的批改通过 `background_tasks.add_task(run_grading_job, ...)` / `run_grading_batch(...)` 丢给后台，自己立即返回 `GradeStartResponse` / `GradeAllStartResponse`（202）。

### 6.2 老师答案预处理（页面图片渲染）

`ensure_answer_page_images(answer_file_id, answer_path)` 会：

1. 检查 `data/teacher/<answer_file_id>/pages/` 下的缓存是否可复用（比较源文件的 mtime + 大小指纹和缓存版本号）
2. 如果答案文件是 `.docx`：先校验是有效 docx，再用 `file_processor.convert_docx_to_pdf()`（需要本机能找到 LibreOffice `soffice`）转成临时 PDF
3. 如果答案文件是 `.pdf`：跳过转换，直接使用
4. 用 `PyMuPDF`（`fitz`，200 DPI）把 PDF 逐页渲染成 `page_1.png`, `page_2.png`, ...
5. 写 `source_meta.json` 记录源文件路径、指纹和缓存版本号，供下次复用判断

不再有“以 `Solution` 分隔题目区/解答区”这一步——整份文档的所有页面都会被当成答案图片交给模型。

### 6.3 学生提交预处理

`export_student_pdf_to_images(submission_id, pdf_path)`（`student_images.py`）会：

1. 打开 PDF
2. 对每页用 `fitz.Matrix(3, 3)` 渲染
3. 写入 `data/tmp/submissions/<submission_id>/page_*.png`

批改结束后（无论成功还是失败），这些学生临时 PNG 都会被 `cleanup_student_tmp_images()` 清理掉。

### 6.4 视觉模型调用

`auto_grade_homework()` 把老师答案页面图片和学生作答页面图片都转成 base64 data URL，交给 `grading_provider.call_grading_model(answer_images, student_images)`：

- 消息里先放全部老师答案页面图片，再放全部学生作答页面图片（不再区分“题目图”/“解答图”两组）
- 调用当前激活供应商（`GRADING_PROVIDER`，默认 `doubao`）对应的 OpenAI 兼容接口，`temperature=0`，失败自动重试最多 3 次
- 系统 prompt 要求模型：
  - 先做题目内容匹配，不依赖题号
  - 只有确认匹配成功时才允许自动评分
  - 匹配失败或证据不足时必须标记人工复核（`auto_graded=false`, `score=null`, `is_correct=null`）
  - 输出必须是严格 JSON，不能有 Markdown 或多余文字

### 6.5 结果归一化

模型返回后，`_normalize_vision_result()` 会：

- 为每题生成稳定的 `question_number`
- 归一化 `question_id`
- 规范 `question_match_confidence`（裁剪到 0~1）
- 处理 `auto_graded` / `is_correct` / `score`（`question_match=false` 时强制 `auto_graded=false`）
- 计算：
  - `total_score`
  - `max_total_score`
  - `auto_graded_count`
  - `manual_review_count`
  - `needs_manual_review`

### 6.6 数据库存储策略

`grade_claimed_submission(db, submission_id)` 会（此时 submission 已经是 `grading` 状态）：

1. 调用 `auto_grade_homework()`
2. 写 `grade_results.raw_json`（保存完整归一化结果，包括需要人工复核的题目）
3. 删除旧的 `GradeQuestion`
4. 只为 `score`/`is_correct` 都非空的题目写新的 `GradeQuestion`
5. 根据结果把 submission 置为 `graded` 或 `needs_manual_review`
6. 若任何步骤失败（`RuntimeError`、`OpenAIError`、DB 异常等），置为 `failed_grading` 并写入中文错误信息——这个函数本身**不抛异常**，所有失败都被捕获并写回 DB，因为它是从后台任务里调用的，没有 HTTP 请求可以返回错误给前端

## 7. HTTP API 速查

这里只列当前主流程真正会用到的接口。

### 7.1 健康检查

- `GET /health`

### 7.2 认证

- `POST /auth/bootstrap-teacher`
  - 仅当系统还没有任何老师账号时可用
- `POST /auth/teacher/login`
- `POST /auth/teacher/entry`
  - 邮箱存在则登录，否则注册
- `POST /auth/student/login`
- `POST /auth/student/entry`
  - 旧式“自动注册/登录”入口；当前主 UI 更推荐 join link 注册

### 7.3 班级与学生

- `POST /teachers/me/courses`
- `GET /teachers/me/courses`
- `DELETE /courses/{course_id}`
  - 级联删除该课程下全部作业、学生、提交与批改结果，不可恢复
- `POST /courses/{course_id}/join-link`
- `GET /courses/join/{join_token}`
- `POST /courses/join/{join_token}/register`
- `GET /courses/{course_id}/students`
- `POST /courses/{course_id}/students`
- `DELETE /courses/{course_id}/students/{student_id}`
  - 级联删除该学生的全部提交与批改结果，不可恢复
- `POST /courses/{course_id}/students/{student_id}/password`
  - 老师重置学生密码（`StudentPasswordResetRequest.new_password`，至少 8 位），重置后学生须用新密码登录

### 7.4 作业

- `POST /courses/{course_id}/assignments`
- `GET /courses/{course_id}/assignments`
- `GET /assignments`
- `GET /students/me/assignments`
- `DELETE /assignments/{assignment_id}`
  - 级联删除该作业下全部提交与批改结果、以及官方答案文件，不可恢复

### 7.5 文件上传

- `POST /assignments/{assignment_id}/solution`
- `POST /teachers/{teacher_id}/assignments/{assignment_id}/solution`
  - legacy path，仍可用
- `POST /assignments/{assignment_id}/submissions`
  - 老师代学生上传
- `POST /assignments/{assignment_id}/submissions/me`
  - 学生本人上传

### 7.6 批改与结果

- `POST /submissions/{submission_id}/grade`
  - 返回 **202**（`GradeStartResponse`），批改本身在后台任务里异步执行，不是同步完成
- `POST /assignments/{assignment_id}/grade-all`
  - 返回 **202**（`GradeAllStartResponse`），同样异步；跳过当前状态不在 `GRADABLE_STATUSES` 里的 submission（即 `graded`/`grading`）
- `GET /assignments/{assignment_id}/submissions`
- `GET /assignments/{assignment_id}/students-status`
- `GET /submissions/{submission_id}/result`
  - 老师查看某份提交的逐题结果
- `PUT /submissions/{submission_id}/questions/{question_number}`
  - 老师人工改分（`QuestionOverrideRequest`: `score` / `is_correct` / 可选 `comment`），会重新计算 `total_score`；当该 submission 不再有题目需要人工复核时，状态自动变为 `graded`
- `GET /students/me/submissions/{submission_id}/result`
  - 学生查看自己某份提交的逐题结果

## 8. 前端实际交互逻辑

### 8.1 教师端

老师登录后进入 `/teacher/*` 工作台。

工作台会长期维护三个关键上下文：

- `backendBaseUrl`
- `selectedCourseId`
- `selectedAssignmentId`

这些值会保存在 `localStorage` 中，刷新页面后会恢复。

当老师切换作业时：

- 会自动加载 submission 列表
- 会自动加载每个学生的提交状态
- 每 10 秒自动轮询一次状态数据

### 8.2 学生端

推荐使用流程：

1. 老师生成加入链接
2. 学生打开 `/student/join/:joinToken`
3. 学生注册后跳去 `/student/login`
4. 登录后进入 `/student`
5. 查看当前课程下所有作业概览
6. 选择作业并上传 PDF

学生端会在作业概览中展示：

- 是否已提交
- 当前 submission 状态
- 若已评分，显示分数
- 若 `needs_manual_review`，显示“自动评分小计”

## 9. 运行目录与文件产物

默认运行目录由 `runtime_config.py` 决定，默认是仓库内 `data/`。

### 9.1 默认目录结构

```text
data/
  solutions/              # 官方答案原始 docx
  submissions/            # 学生提交原始 pdf
  teacher/                # 老师答案图片缓存
  tmp/
    submissions/          # 学生 PDF 临时导图目录
```

### 9.2 关键规则

- 老师图片缓存会长期保留，可复用。
- 学生导图目录是临时目录，批改完成后会尽力删除。
- 测试不会使用真实 `data/`，会把这些路径定向到 pytest 临时目录。

## 10. 环境变量

项目不会自动加载 `.env` 文件。无论本地还是部署环境，都需要手动 export 或平台注入环境变量。

### 10.1 必需变量

#### 后端最少需要

- `DATABASE_URL`
- `AUTH_SECRET_KEY`

注意：`DATABASE_URL` 在 `db.py` 导入时就必须存在，否则应用启动直接报错。

#### 真正调用视觉模型评分时还需要

- `ARK_API_KEY`
  - **默认供应商（豆包/方舟 ARK）必需**。未配置时 `grading_provider.call_grading_model()` 会直接抛出“未配置 ARK_API_KEY，无法调用豆包批改。”
- `DASHSCOPE_API_KEY`
  - 仅当 `GRADING_PROVIDER=qwen`（切到 Qwen 备选供应商）时才需要。注意：这条路径下 `grading_provider.py` 只读取精确的 `DASHSCOPE_API_KEY` 这一个变量名，**不**兼容 `qwen_client.py` 里给旧文本链路用的那些别名（`DASSCOPE_API_KEY` / `DASHSCOPE_APIKEY` / `QWEN_API_KEY` / `OPENAI_API_KEY`）。

### 10.2 常用变量

- `GRADING_PROVIDER`
  - `doubao`（默认）或 `qwen`，选择当前激活的视觉批改供应商
- `DOUBAO_VISION_MODEL`
  - 豆包视觉模型名，默认 `doubao-seed-2-1-turbo-260628`
- `ARK_BASE_URL`
  - 默认是 `https://ark.cn-beijing.volces.com/api/v3`
- `TEACHER_SIGNUP_CODE`
  - 教师注册邀请码；不设置则该校验完全关闭（可选功能，不是所有部署都需要开启）
- `FRONTEND_BASE_URL`
  - 用于生成学生加入链接
- `CORS_ALLOW_ORIGINS`
  - 显式 CORS origin 列表，逗号分隔
  - 不允许使用 `*`
- `APP_DATA_DIR`
  - 运行时文件目录
- `SOFFICE_PATH`
  - 手动指定 LibreOffice `soffice` 可执行文件路径（docx 转 PDF 需要）
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTH_ALGORITHM`
- `PASSWORD_HASH_ITERATIONS`
- `SQLALCHEMY_ECHO`

#### 仅 Qwen 备选供应商相关（`GRADING_PROVIDER=qwen` 时才用得到）

- `QWEN_VISION_MODEL`
  - 视觉模型名，默认 `qwen-vl-max`
- `DASHSCOPE_BASE_URL`
  - 默认是 DashScope OpenAI-compatible URL
- `QWEN_PLUS_MODEL`
  - 仍被 `qwen_client.py` 读取，但 `qwen_client.py` 当前只被已停用的旧文本/spec 链路引用，**不属于**当前正式视觉批改路径

### 10.3 本地辅助变量

- `HOST`
- `PORT`
- `UVICORN_RELOAD`
- `RUN_EXTERNAL_SMOKE`

### 10.4 示例

仓库提供了 `.env.example`，但它只是示例，不会被自动读取。

## 11. 本地运行

## 11.1 启动后端

先准备环境变量：

```bash
export DATABASE_URL=sqlite:///./local_dev.sqlite3
export AUTH_SECRET_KEY='replace-with-a-long-random-secret'
export FRONTEND_BASE_URL='http://localhost:5173'
export ARK_API_KEY='your-real-key'
```

安装依赖并迁移数据库：

```bash
python3 -m pip install -r requirements.txt
alembic upgrade head
```

启动：

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

也可以直接：

```bash
python3 main.py
```

### 11.2 启动前端

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

前端默认后端地址也是 `http://localhost:8000`，但老师端页面支持在 UI 中手动切换 backend base URL。

### 11.3 单文件 smoke 验证

如果不想跑整套 Web UI，可以直接运行：

```bash
python3 quick_qwen_grade.py \
  --answer-docx /absolute/path/to/answer.docx \
  --student-pdf /absolute/path/to/submission.pdf
```

## 12. 测试

测试覆盖度在这个项目里相对重要，因为很多前端契约和中文错误提示被锁死了。

### 12.1 默认测试命令

```bash
python3 -m pytest -q tests
```

### 12.2 覆盖率

```bash
python3 -m pytest -q tests --cov --cov-report=term-missing --cov-report=html
```

### 12.3 可选外部 smoke 测试

```bash
RUN_EXTERNAL_SMOKE=1 \
ARK_API_KEY=<your_real_key> \
python3 -m pytest -q tests/test_external_smoke.py -m external_smoke -o addopts=''
```

`tests/test_external_smoke.py` 现在校验的是 `ARK_API_KEY`（豆包/方舟 ARK，默认供应商），不是 `DASHSCOPE_API_KEY`；只设置 `RUN_EXTERNAL_SMOKE=1` 而不设 `ARK_API_KEY` 会被直接跳过，并提示需要 `ARK_API_KEY`。

### 12.4 测试主要覆盖什么

- 认证与 JWT
- 权限隔离
- 班级加入链接
- 老师/学生上传流程
- submission 覆盖上传
- 评分成功 / 失败 / 人工复核
- 批量批改
- 前端依赖的 JSON 契约
- due_date 时区归一化
- 本地 DOCX/PDF 预处理
- 部署时 runtime / CORS / DB engine 配置

### 12.5 对当前开发很重要的测试结论

- 中文错误消息是契约的一部分。
- 前端依赖接口字段名和 nullability，不能随便改。
- `grade` 接口和 `result` 接口是两个不同契约：
  - `/submissions/{id}/grade` 更轻量
  - `/submissions/{id}/result` 提供 modal 所需完整详情

## 13. 部署

仓库内带 `render.yaml`，默认目标是 Render。

### 13.1 Blueprint 概况

后端现在是 **Docker** 部署，不是 Render 原生 Python runtime。详细原因和完整清单以 [`docs/render_deploy.md`](docs/render_deploy.md) 为准，这里只列要点：

- Web service：`mathhomeworkautomarker-backend`，`runtime: docker`（构建自仓库根目录的 `Dockerfile`），plan `starter`
- 之所以换成 Docker：LibreOffice（docx→PDF 转换需要）不是 pip 包，Render 原生 Python runtime 装不了系统包；`Dockerfile` 基于 `python:3.11-slim` 额外装了 `libreoffice-writer` 和 `fonts-noto-cjk`（缺中文字体会导致转换出的 PDF 里中文变成方块）
- 因为整个应用现在打包成镜像，`render.yaml` 里后端**没有** `buildCommand` / `startCommand`——镜像构建和 `Dockerfile` 里的 `CMD` 取代了两者
- Region：`singapore`
- Persistent disk：挂载到 `/var/data/mathhomeworkautomarker`，`APP_DATA_DIR` 指向这个挂载目录
- `preDeployCommand`：`alembic upgrade head`
- 前端是独立的 Render 静态站点（`runtime: static`），构建命令 `cd frontend && npm ci && npm run build`，发布目录 `frontend/dist`

### 13.2 部署时必须注意

- `ARK_API_KEY` 需要手动配置（默认供应商豆包/方舟必需）
- `DASHSCOPE_API_KEY` 仅当把 `GRADING_PROVIDER` 切到 `qwen` 备选供应商时才需要手动配置
- `FRONTEND_BASE_URL` 建议配置，否则 join link 会指向默认本地地址
- `CORS_ALLOW_ORIGINS` 建议显式配置，不能写 `*`
- 数据库迁移依赖 `DATABASE_URL`

## 14. CI

GitHub Actions 有两个独立的工作流文件：

- `.github/workflows/backend-tests.yml`
- `.github/workflows/frontend-build.yml`

当前 CI 做的事：

- 后端：Python 3.11，安装 `requirements.txt`，安装 `poppler-utils`，运行 `python3 -m pytest -q tests`
- 前端：Node 20，`cd frontend && npm ci && npm run build`，验证前端能正常构建

当前 CI 不做的事：

- 不跑真实豆包/Qwen 视觉模型调用
- 不执行部署

## 15. 已知实现约束与坑点

这些点对继续开发非常重要。

### 15.1 `DATABASE_URL` 是导入时强依赖

`db.py` 在 import 阶段就会读取 `DATABASE_URL`。这意味着：

- 不能先 import 再补环境变量
- 测试里必须尽早注入环境变量

### 15.2 `AUTH_SECRET_KEY` 不能是占位值

占位值会直接触发运行时报错。

### 15.3 CORS 明确拒绝通配符

`CORS_ALLOW_ORIGINS=*` 会抛错，而不是降级放行。

### 15.4 官方答案文件格式已放宽

不再要求老师文档里有 `"Solution"` 分隔行——答案文件只需是有效的 `.docx` 或 `.pdf`，内容和排版都没有特殊要求，系统会把整份文档渲染成页面图片交给视觉模型自己做题目匹配。docx 官方答案在本地/自建部署时仍然需要能找到 LibreOffice（`soffice`）用于转 PDF，这是新的前置条件，不是文档建议。

### 15.5 前端契约比看起来更硬

很多看似可以自由改动的内容其实被测试锁住了，比如：

- 错误响应 `{"detail": "..."}`
- `status` 字段具体值
- `questions` 数组结构
- `due_date` 的 UTC `Z` 序列化

### 15.6 当前学生模型是一对一从属于班级

学生不能同时属于多个班级；如果以后要做多班级学生，需要改数据模型和前端会话逻辑。

### 15.7 老师端前端是强状态工作台

很多页面不自己拉取全部上下文，而是依赖 `TeacherWorkspaceContext`。改老师端行为时，优先从这个 context 着手，而不是只改某个页面组件。

## 16. 如果你是 Claude，建议这样读代码

建议阅读顺序：

1. `main.py`
2. `models.py`
3. `schemas.py`
4. `grading_provider.py`
5. `grading_service.py`
6. `student_images.py`
7. `frontend/src/api.ts`
8. `frontend/src/teacher/TeacherWorkspaceContext.tsx`
9. `frontend/src/App.tsx`
10. `tests/test_grading_flow.py`
11. `tests/test_frontend_acceptance_contracts.py`
12. `tests/test_offline_file_processing.py`

如果你的任务是：

### 改批改逻辑

优先看：

- `grading_provider.py`
- `grading_service.py`
- `file_processor.py`
- `student_images.py`
- `tests/test_grading_flow.py`
- `tests/test_offline_file_processing.py`

### 改接口契约

优先看：

- `schemas.py`
- `main.py`
- `frontend/src/api.ts`
- `tests/test_response_contracts.py`
- `tests/test_frontend_acceptance_contracts.py`

### 改教师端交互

优先看：

- `frontend/src/teacher/TeacherWorkspaceContext.tsx`
- `frontend/src/teacher/pages/*`

### 改学生端交互

优先看：

- `frontend/src/components/StudentJoinPage.tsx`
- `frontend/src/components/StudentLoginPage.tsx`
- `frontend/src/components/StudentUploadPage.tsx`

## 17. 仓库里各类文档的可信度

### 代码优先级最高

最可信的是：

- `main.py`
- `grading_provider.py`
- `grading_service.py`
- `models.py`
- `tests/`

### `docs/` 中的文档请带着版本意识看

- `docs/render_deploy.md`
  - 与当前部署配置基本一致，可参考
- `docs/testing.md`
  - 与当前测试现状基本一致，可参考
- `docs/current_pipeline.md`
  - 标题已说明是“before refactor”的旧说明，不应作为当前正式链路依据
- `docs/pipeline_v2.md`
  - 明确记录的是已停用的旧文本/spec 链路

## 18. 当前项目适合做什么，不适合做什么

### 适合

- 在受控格式下做数学作业自动批改
- 老师班级管理 + 学生加入 + 提交 + 批改闭环
- 做视觉批改实验与提示词迭代
- 用测试保护前后端契约

### 暂时不适合

- 任意格式 Word/图片/PDF 的鲁棒通用解析
- 多课程共享学生账号模型
- 真正多租户 SaaS 级别的权限、审计和运营后台
- 大规模并发批改场景下的专业任务队列（当前是 FastAPI `BackgroundTasks` + 简单的 `SELECT ... FOR UPDATE` 占用锁，够用但不是 Celery/RQ 那种正经任务队列）

> 说明：批改在后台异步执行、前端轮询状态、`claim_for_grading()` 防止并发批改同一份提交，这些已经实现，不再是“暂时不适合”的范围。

## 19. 一句话总结

这是一个以 `FastAPI + React` 为壳、以 `DOCX/PDF 本地预处理 + 豆包（方舟 ARK，默认）/ Qwen（备选）视觉模型` 为核心的数学作业自动批改系统；批改在后台异步执行，前端定时轮询状态；当前正式链路明确、测试较全、前后端契约稳定，官方答案文件格式约束已经放宽（.docx / .pdf 均可，无需特殊排版），旧文本链路只是保留参考，不是主流程。
