# Pipeline V2 (Archived Legacy Text Pipeline)

## 状态
这份文档描述的是**已停用**的文本/spec 旧链路，仅用于回滚或历史参考。当前正式链路以 `qwen_service.py` 的视觉批改流程为准。

## 旧链路分层
1. **结构层 (`teacher_spec.py`)**
   - 从老师 `docx` 文本块推断题目标签
   - 当前仅保留本地标签猜测与 `qwen-3.5-plus` 补充解析

2. **学生解析层 (`student_parsing.py`)**
   - 从学生 PDF 提取页面文本
   - 旧的模型检索步骤已停用，当前只保留本地候选搜索 fallback

3. **评估层 (`grading.py`)**
   - 逐题评分
   - `numeric/expression` 直接比较
   - `explanation` 走 rubric 评分
   - `graph/mixed` 当前仍以人工复核为主

4. **聚合层 (`aggregate.py`)**
   - 对齐题号
   - 填补缺失题目
   - 汇总最终结果

## 当前正式链路
- 正式入口：`qwen_service.py`
- 当前主方法：老师 `docx` 提图 + 学生 `pdf` 转图 + 视觉模型批改
- 旧文本链路不会在当前主流程中自动执行

## 旧产物位置
- `data/pipeline/teacher_spec/*_teacher_spec.json`
- `data/pipeline/student_answers_raw/*_student_answers_raw.json`
- `data/pipeline/grading_results/*_grading_result.json`
