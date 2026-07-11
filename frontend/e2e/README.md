# 前端 E2E 冒烟测试

Playwright 裸脚本（非 test-runner），覆盖：教师/学生登录、教师 6 路由加载、学生作业列表与状态中文化、320/375px 无整页横向溢出（CSS Grid min-content 回归保护）、移动端 sticky 操作列可点性、console 错误收集。

## 运行前置

1. 后端（用独立测试库，勿连生产数据）：

```bash
export DATABASE_URL="sqlite:////tmp/e2e-test.db"
export AUTH_SECRET_KEY="local-e2e-secret-0123456789abcdef"
export APP_DATA_DIR="/tmp/e2e-appdata"
python3 -c "from db import engine, Base; import models; Base.metadata.create_all(bind=engine)"
CORS_ALLOW_ORIGINS="http://localhost:5174,http://127.0.0.1:5174" \
  uvicorn main:app --host 127.0.0.1 --port 8000
```

2. 前端：

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --port 5174 --strictPort
```

## 运行

```bash
cd frontend
npm run test:e2e
```

- 测试数据（教师/学生/班级/作业）通过后端 API 幂等种入，重复运行安全。
- 截图输出到 `e2e/screenshots/`（已 gitignore），断言结果写入 `e2e/last-run.json`。
- 退出码：0 全过；1 有断言失败；2 总超时。
- 可用 `FRONTEND_URL` / `BACKEND_URL` 环境变量覆盖默认地址。
