from utils.llm import LLMClient
from utils.json_parser import parse_json_response


class PlanAgent:

    def __init__(self, api_key):
        self.llm = LLMClient(api_key)

    def generate_plan(self, parsed_goal, rag_context=None):
        rag_block = ""
        if rag_context:
            rag_block = f"""

以下是从本地知识库检索到的参考片段（RAG）。请优先结合与用户目标相关的片段制定计划；若片段无关可忽略：
{rag_context}
"""

        prompt = f"""
你是一名学习规划专家。

根据以下学习目标生成学习计划。

学习目标：
{parsed_goal}
{rag_block}

请严格输出JSON（不要加解释文本）：
{{
  "summary": "整体学习安排概述",
  "stages": [
    {{
      "name": "阶段名称",
      "days": "第1-3天",
      "focus": ["重点主题1", "重点主题2"]
    }}
  ],
  "daily_tasks": [
    {{
      "day": 1,
      "task": "当天任务",
      "estimated_hours": 2
    }}
  ],
  "milestones": ["里程碑1", "里程碑2"]
}}
"""

        raw_result = self.llm.chat(prompt)
        fallback = {
            "summary": "已根据目标生成基础学习计划。",
            "stages": [],
            "daily_tasks": [],
            "milestones": [],
        }
        result = parse_json_response(raw_result, fallback)

        return result