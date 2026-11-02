# LOOP_OPTIMIZATION.md — MathHomeworkAutomarker

> 循环优化审计 · 2026-07-12 · 基于 Claude Code 循环分类法（turn-based / /goal / /loop / /schedule / 主动式 routine）

## 项目概览与阶段

中小学数学作业自动批改系统（FastAPI + React，Render 部署），当前处于**活跃开发期**：多供应商重构三步走的第一步（豆包验证）已通过首轮真实批改，等人工核对后进入第二步 `grading_provider` 重构。这是桌面上自动化基础最好的项目：61 个后端 pytest、GitHub Actions CI（backend-tests.yml）、16 断言的前端 E2E 冒烟（`npm run test:e2e`）、独立验证 CLI（`validate_providers.py`）。

## 循环机会映射

| 任务 | 当前手动流程 | 推荐循环类型 | 具体命令 / prompt | 停止条件 | token 成本备注 |
|---|---|---|---|---|---|
| 第二步 grading_provider 重构 | 人工分配子代理写码→审查→跑测试，多轮往返 | **/goal** | `/goal 新建 grading_provider.py/grading_service.py 并改 main.py 接入，废弃 teacher_images.py/student_images.py/qwen_client.py；完成判据：python3 -m pytest -q tests 全绿（≥61 passed）且 cd frontend && npm run test:e2e 16 断言全过` | 测试全绿，或 turn cap 25 | 写码路由 Sonnet 子代理（CLAUDE.md §5），主会话只验收；测试是硬判据，无需人在环 |
| 改动后回归验证 | 每次改完手动跑 pytest + 手动起 dev server 点页面 | **skill 内脚本**（先于任何循环） | 新建 `.claude/skills/verify/SKILL.md`：编码 STATE.md 里已验证的坑——dev server 必须非沙箱 Bash、测试端口 5174 + `CORS_ALLOW_ORIGINS`、E2E 复用 storageState（`/auth/*` 有 10 次/60s 限流）、建表用 `Base.metadata.create_all` | 一次性建设 | 脚本化后每次验证近零 token；这是所有后续循环的地基 |
| push 后盯 GitHub Actions | push 后人工刷新 Actions 页面 | **/loop**（短期） | `/loop 5m gh run watch 或 gh run list -L1 --json status,conclusion，失败则读日志并总结原因` | CI 转绿或明确失败原因已报告 | 纯 `gh` 命令轮询，几乎零 token；CI 单次约 3-5 分钟，5m 间隔匹配 |
| 供应商批量验证（夜间批次） | 2026-07-12 夜间批次是一次性人工授权执行 | **/schedule + /goal 复合** | `/schedule 每晚 23:00：source .env.local 后对 data/submissions/ 新增样本跑 validate_providers.py --providers doubao，生成 review-doubao.html 追加核对行；完成判据：结果 JSON 落盘且 HTML 更新` | 每晚一次性运行结束；无新样本则直接退出 | 豆包 API 花的是方舟额度不是 Claude token；Claude 侧只是编排脚本，选 Haiku/Sonnet 级 routine 即可。⚠️ 判分质量核对仍是人工 gate，循环只负责把核对材料备好 |
| 第三步 Render 部署验证 | 计划中：改 Dockerfile 后人工盯部署 | **/loop**（部署当天） | `/loop 3m curl -sf https://<render-url>/健康检查端点，失败读 Render 日志` | 健康检查通过或部署失败已定位 | 到第三步再建；Render 免费实例冷启动慢，间隔别低于 3m |

## 优先级排名

**第一优先：verify skill（SKILL.md）。** 理由：STATE.md 里已经积累了 4 条用血泪换来的验证约束（非沙箱 dev server、限流、端口、storageState），但它们只存在于会话记忆里——任何 /goal 循环若不知道这些坑，E2E 会因限流假失败，循环就会在错误信号上空转烧 token。先把验证流程固化成 skill + 脚本，紧接着第二步重构就能安全地用 /goal 跑。

## 前置条件

1. **人工核对 gate 未过**：`review-doubao.html` 的豆包判分核对只有你能做，这是主线继续的前提（STATE.md 验收清单第 1 条）。
2. **仓库状态**：4 个 commit 未 push；工作区有一次性验证产物（`validate_results_night.json`、`review-doubao.html`、多个 `tmp_probe*.db`）——启动 /goal 重构前先处理，否则测试判据会被脏状态污染。
3. verify skill 建好并单独跑通一次，才能作为 /goal 的停止判据。
