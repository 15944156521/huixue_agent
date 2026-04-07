# RAG 与 LangGraph 说明

## RAG（检索增强生成）

- **知识库位置**：`data/knowledge/` 下的 `.md` / `.txt` 文件，按空行分段为检索块。
- **检索方式**：轻量 **BM25**（`rag/bm25.py` + `rag/retriever.py`），无需向量模型与 embedding API；中文查询通过「整段 + 单字」混合 token，提高命中率。
- **注入点**：
  - 学习计划：`PlanAgent.generate_plan(..., rag_context=...)`，由 LangGraph 在 `retrieve` 节点后注入。
  - 学习检测：`EvaluationAgent.evaluate(..., rag_context=...)`，在 `StudyPlannerService.generate_evaluation` 中按当前进度上下文检索后注入。
  - 动态调整：`OptimizationAgent.optimize(..., rag_context=...)`，由 LangGraph 在调整工作流中检索后注入。

## LangGraph（工作流编排）

- **计划生成图**（`graph/workflows.py` → `build_plan_workflow`）：`parse` → `retrieve` → `plan` → END。  
  对应原顺序：解析目标 → RAG 检索 → 生成计划。
- **动态调整图**（`build_adjust_workflow`）：`retrieve` → `optimize` → END。  
  将计划摘要、进度、检测摘要拼成查询，检索后交给优化智能体。

## 依赖

- `langgraph`（见 `requirements.txt`）

安装：

```bash
pip install -r requirements.txt
```

## 前端展示

在 `app.py` 中，「学习计划生成」「重新生成计划」成功后，以及「学习进度反馈」生成检测题后、「学习检测」页展示题目上方，均提供 **折叠区「本次检索到的知识片段」**，便于对照 RAG 是否命中知识库。

## 日历与每日任务（系统时钟）

- 数据库 `study_plans.plan_start_date` 表示 **计划 Day 1 对应的自然日**；`daily_tasks[].day` 按「起始日 + (day−1) 天」映射到日历。
- 使用 **`date.today()`** 作为系统今日；侧边栏展示今日与「当前第几天」。
- 对 **[起始日, 今日)** 内、且仍在计划天数范围内的每个自然日：无进度记录视为 **缺勤**；有记录且完成率低于 **50%** 视为 **未达标**。首页与侧栏会提醒。
- 进度提交时通过 **「本条进度对应的日期」** 写入 `progress_logs.study_date`，支持补录昨天。
- **动态调整** 会把 `calendar_context`（含缺勤列表）交给优化智能体；若从未提交进度但已存在缺勤，也可用合成进度触发调整。
- 调度逻辑见 `services/schedule.py`，快照接口为 `StudyPlannerService.get_schedule_snapshot`。
