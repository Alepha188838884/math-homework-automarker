# MathHomeworkAutomarker

一个面向中小学数学作业场景的自动批改系统。老师上传题目+标准解答的 `.docx`，学生上传作业 `.pdf`，后端会先做本地图像预处理，再调用 DashScope/Qwen 视觉模型完成按题匹配与评分；若题目匹配不确定，则把对应题目标记为“需要人工复核”。

这份 README 不是营销文档，而是给 Claude 或其他接手该仓库的开发者看的代码导览。内容以当前仓库代码、测试和部署配置为准。

## 1. 项目结论速览

- 当前正式链路是“视觉批改链路”，核心入口在 `qwen_service.py`，不是旧的文本/spec 链路。
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
4. 老师上传一份官方答案 `.docx`。
5. 系统把这份 `.docx` 落盘，并上传到 DashScope 记录 `qwen_file_id`。
6. 学生通过班级加入链接注册，随后登录。
7. 学生上传作业 `.pdf`。
8. 系统把 `.pdf` 落盘，并上传到 DashScope 记录 `qwen_file_id`。
9. 老师在批改中心触发单份批改或批量批改。
10. 后端执行本地预处理：
    - 从老师 `.docx` 中提取“题目图片”和“解答图片”
    - 把学生 `.pdf` 每页渲染成灰度 PNG
11. 后端把这些图片按固定顺序喂给视觉模型。
12. 模型返回严格 JSON：
    - 每题是否匹配到学生对应题目
    - 是否自动评分
    - 分数 / 满分 / 对错 / 评论
13. 后端归一化结果，写入 `grade_results` 和部分 `grade_questions`。
14. 若存在未自动评分题目，则 submission 状态为 `needs_manual_review`；否则为 `graded`。

### 2.3 当前不是这样工作的内容

- 当前正式链路**不会自动走** `teacher_spec.py`、`student_parsing.py`、`grading.py`、`aggregate.py` 那套旧文本流程。
- 上传时虽然仍会把文件上传到 DashScope 并记录 `qwen_file_id`，但正式批改主要依赖**本地文件路径 + 本地图片预处理 + 视觉模型**，而不是直接用 `fileid://` 进行旧式文本批改。

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

### `qwen_service.py`

当前正式批改链路的核心：

- 调 DashScope 上传文件
- 构造视觉模型消息
- 解析模型返回 JSON
- 对每题结果做归一化
- 写入 `GradeResult` / `GradeQuestion`
- 更新 submission 状态

这是最重要的“AI 批改实现文件”。

### `qwen_client.py`

DashScope OpenAI-compatible client 封装：

- 读取 API Key
- 兼容多种环境变量名
- 构造 `OpenAI(base_url=...)`
- 基础 JSON 解析和通用调用辅助

### `teacher_images.py`

老师答案 `.docx` 的本地图片提取缓存逻辑：

- 读取 Word 中的嵌入图片
- 以段落中的 `"Solution"` 为分隔线
- 分隔线前的图片视为题目图
- 分隔线后的图片视为解答图
- 转为灰度 PNG
- 缓存到 `data/teacher/<answer_file_id>/...`

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
  - 上传成功，且文件已成功上传到 DashScope
- `failed_upload`
  - 文件本地落盘成功，但上传到 DashScope 失败
- `grading`
  - 正在批改
- `graded`
  - 所有题都已自动评分
- `needs_manual_review`
  - 至少有一题无法确认匹配或不适合自动评分
- `failed_grading`
  - 本地预处理、模型调用或结果入库失败

### 5.2 官方答案 DOCX 格式规则

当前格式要求非常关键：

- 文件必须是有效 `.docx`
- 文档内必须存在一行包含 `"Solution"` 的段落
- `Solution` 之前的嵌入图片视为“题目图”
- `Solution` 之后的嵌入图片视为“解答图”

常见失败原因：

- 空 docx
- 损坏的 docx
- 没有 `Solution` 分隔行
- `Solution` 前没有题目图片
- `Solution` 后没有解答图片

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

这一段对应 `qwen_service.py` 的真实实现。

### 6.1 老师答案预处理

`ensure_teacher_images(answer_file_id, docx_path)` 会：

1. 检查缓存是否可复用
2. 读取 `.docx`
3. 以 `"Solution"` 分隔题目区和解答区
4. 从 paragraph run 中提取嵌入图片
5. 转灰度 PNG
6. 写入：
   - `data/teacher/<answer_file_id>/questions/q_*.png`
   - `data/teacher/<answer_file_id>/solutions/s_*.png`
7. 写 `source_meta.json` 记录源文件指纹与 extractor version

### 6.2 学生提交预处理

`export_student_pdf_to_images(submission_id, pdf_path)` 会：

1. 打开 PDF
2. 对每页用 `fitz.Matrix(3, 3)` 渲染
3. 转灰度 PNG
4. 写入 `data/tmp/submissions/<submission_id>/page_*.png`

批改结束后，这些学生临时 PNG 会被清理掉。

### 6.3 视觉模型输入顺序

模型消息固定按三组图片输入：

1. 老师题目图
2. 老师解答图
3. 学生作答图

系统 prompt 要求模型：

- 先做题目内容匹配，不依赖题号
- 只有确认匹配成功时才允许自动评分
- 匹配失败或证据不足时必须标记人工复核
- 输出必须是严格 JSON

### 6.4 结果归一化

模型返回后，后端会：

- 为每题生成稳定的 `question_number`
- 归一化 `question_id`
- 规范 `question_match_confidence`
- 处理 `auto_graded` / `is_correct` / `score`
- 计算：
  - `total_score`
  - `max_total_score`
  - `auto_graded_count`
  - `manual_review_count`
  - `needs_manual_review`

### 6.5 数据库存储策略

`grade_one_submission()` 会：

1. 先把 submission 置为 `grading`
2. 调用 `auto_grade_homework()`
3. 写 `grade_results.raw_json`
4. 删除旧的 `GradeQuestion`
5. 只为可自动评分题目写新的 `GradeQuestion`
6. 根据结果把 submission 置为：
   - `graded`
   - 或 `needs_manual_review`
7. 若任何步骤失败，则置为 `failed_grading`

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
- `POST /courses/{course_id}/join-link`
- `GET /courses/join/{join_token}`
- `POST /courses/join/{join_token}/register`
- `GET /courses/{course_id}/students`
- `POST /courses/{course_id}/students`

### 7.4 作业

- `POST /courses/{course_id}/assignments`
- `GET /courses/{course_id}/assignments`
- `GET /assignments`
- `GET /students/me/assignments`

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
- `POST /assignments/{assignment_id}/grade-all`
- `GET /assignments/{assignment_id}/submissions`
- `GET /assignments/{assignment_id}/students-status`
- `GET /submissions/{submission_id}/result`

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

#### 真正调用 DashScope/Qwen 评分时还需要

- `DASHSCOPE_API_KEY`

代码还兼容以下别名：

- `DASSCOPE_API_KEY`
- `DASHSCOPE_APIKEY`
- `QWEN_API_KEY`
- `OPENAI_API_KEY`

### 10.2 常用变量

- `FRONTEND_BASE_URL`
  - 用于生成学生加入链接
- `CORS_ALLOW_ORIGINS`
  - 显式 CORS origin 列表，逗号分隔
  - 不允许使用 `*`
- `APP_DATA_DIR`
  - 运行时文件目录
- `QWEN_VISION_MODEL`
  - 视觉模型名
- `QWEN_PLUS_MODEL`
  - 辅助模型名
- `DASHSCOPE_BASE_URL`
  - 默认是 DashScope OpenAI-compatible URL
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTH_ALGORITHM`
- `PASSWORD_HASH_ITERATIONS`
- `SQLALCHEMY_ECHO`

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
export DASHSCOPE_API_KEY='your-real-key'
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
QWEN_VISION_MODEL=<your_vision_model> \
DASHSCOPE_API_KEY=<your_real_key> \
python3 -m pytest -q tests/test_external_smoke.py -m external_smoke -o addopts=''
```

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

- Web service：`mathhomeworkautomarker-backend`
- Region：`singapore`
- Persistent disk：挂载到 `/var/data/mathhomeworkautomarker`
- `APP_DATA_DIR` 指向这个挂载目录
- `preDeployCommand`：`alembic upgrade head`
- `startCommand`：`uvicorn main:app --host 0.0.0.0 --port $PORT`

### 13.2 部署时必须注意

- `DASHSCOPE_API_KEY` 需要手动配置
- `FRONTEND_BASE_URL` 建议配置，否则 join link 会指向默认本地地址
- `CORS_ALLOW_ORIGINS` 建议显式配置，不能写 `*`
- 数据库迁移依赖 `DATABASE_URL`

## 14. CI

GitHub Actions 文件在 `.github/workflows/backend-tests.yml`。

当前 CI 做的事：

- Python 3.11
- 安装 `requirements.txt`
- 安装 `poppler-utils`
- 运行 `python3 -m pytest -q tests`

当前 CI 不做的事：

- 不跑真实 DashScope/Qwen 调用
- 不验证前端构建
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

### 15.4 老师 DOCX 强依赖 `Solution` 分隔行

这是当前格式约束，不是文档建议。缺少这行，正式批改会直接失败。

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
4. `qwen_service.py`
5. `teacher_images.py`
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

- `qwen_service.py`
- `teacher_images.py`
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
- `qwen_service.py`
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
- 复杂人工复核工作流
- 异步任务队列、后台任务追踪、并发批改治理
- 真正多租户 SaaS 级别的权限、审计和运营后台

## 19. 一句话总结

这是一个以 `FastAPI + React` 为壳、以 `DOCX/PDF 本地预处理 + DashScope/Qwen 视觉模型` 为核心的数学作业自动批改系统；当前正式链路明确、测试较全、前后端契约稳定，但文件格式约束严格，且旧文本链路只是保留参考，不是主流程。
