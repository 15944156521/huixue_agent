from utils.llm import LLMClient
from utils.json_parser import parse_json_response


class OptimizationAgent:

    def __init__(self, api_key):
        self.llm = LLMClient(api_key)

    def optimize(self, learning_status, rag_context=None):
        rag_block = ""
        if rag_context:
            rag_block = f"""

以下是从本地知识库检索到的参考片段（RAG）。调整后续任务时可参考其中薄弱知识点进行补强；若片段无关可忽略：
{rag_context}
"""

        prompt = f"""
你是一名学习策略优化助手。

根据学习进度给出学习计划调整建议。

学习状态：
{learning_status}
{rag_block}

请严格输出JSON（不要加解释文本）：
{{
  "off_track": true,
  "analysis": "偏差分析",
  "adjustments": [
    {{
      "type": "time_or_task",
      "action": "具体调整动作",
      "reason": "调整原因"
    }}
  ],
  "updated_daily_tasks": [
    {{
      "day": 1,
      "task": "调整后的任务",
      "estimated_hours": 2
    }}
  ],
  "reminders": ["提醒1", "提醒2"]
}}

请结合以下信息综合判断：
1. 学习进度完成率和偏差原因
2. 最近一次学习检测结果，如分数、掌握程度、薄弱点
3. learning_status 中的 calendar_context：系统今日日期、计划起始日、当前第几天、缺勤日、未达标日；请据此压缩或顺延后续 daily_tasks
4. 后续任务应优先补弱项，再安排新任务
"""

        raw_result = self.llm.chat(prompt)
        fallback = {
            "off_track": bool(learning_status.get("is_off_track", False)),
            "analysis": "根据当前进度给出常规优化建议。",
            "adjustments": [],
            "updated_daily_tasks": [],
            "reminders": [],
        }
        result = parse_json_response(raw_result, fallback)

        return result