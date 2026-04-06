"""
多轮交互信息补全模块：检测用户输入中的信息缺口，构建完整用户画像。
"""

from utils.llm import LLMClient
from utils.json_parser import parse_json_response


class InfoValidator:
    """检测信息缺口并生成补全问题"""

    def __init__(self, api_key):
        self.llm = LLMClient(api_key)

    def check_completeness(self, user_input: str) -> dict:
        """
        评估用户输入的完整性。
        返回: {
            "completeness_score": 0-100,  # 信息完整度
            "critical_missing": [],  # 关键缺失字段
            "optional_missing": [],  # 可选缺失字段
            "analysis": "分析说明"
        }
        """
        prompt = f"""
你是学习需求分析专家。评估以下用户学习需求的完整性。

用户输入：
{user_input}

请判断用户描述中是否包含以下关键信息。严格输出JSON（不要加解释文本）：
{{
  "completeness_score": 65,
  "has_subject": true,
  "has_duration": true,
  "has_daily_hours": true,
  "has_focus_topics": true,
  "has_background": false,
  "has_learning_style": false,
  "has_constraints": false,
  "critical_missing": ["学习背景", "可用时间的灵活性"],
  "optional_missing": ["学习风格偏好"],
  "analysis": "用户明确了学习科目、时长和重点，但未说明前置知识背景，可能导致制定的计划过难或过简。建议补充。"
}}
"""

        raw_result = self.llm.chat(prompt, temperature=0.2)
        fallback = {
            "completeness_score": 50,
            "has_subject": False,
            "has_duration": False,
            "has_daily_hours": False,
            "has_focus_topics": False,
            "has_background": False,
            "has_learning_style": False,
            "has_constraints": False,
            "critical_missing": ["学习科目", "学习时长"],
            "optional_missing": [],
            "analysis": "无法完整解析用户输入。"
        }
        result = parse_json_response(raw_result, fallback)
        return result

    def generate_followup_questions(self, user_input: str, missing_fields: list) -> list:
        """
        基于缺失字段生成后续问题。
        返回: [{"field": "field_name", "question": "具体问题", "priority": "高/中/低"}]
        """
        missing_str = "、".join(missing_fields) if missing_fields else ""

        prompt = f"""
你是学习规划助手。用户已描述了部分学习需求，现在需要补充上述缺失信息。

用户原始输入：
{user_input}

缺失信息：{missing_str}

请生成1-3个简洁、针对性强的追问，帮助用户补充缺失的关键信息。

严格输出JSON数组（不要加解释文本）：
[
  {{
    "field": "learning_background",
    "question": "你在这个领域有什么前置知识吗？比如已经学过的相关课程或实践经验？",
    "priority": "高",
    "hint": "这有助于我们评估计划的难度和节奏"
  }},
  {{
    "field": "learning_style",
    "question": "你的学习风格偏向快速突进还是循序渐进？有时间压力吗？",
    "priority": "高",
    "hint": "不同风格需要不同的任务组织方式"
  }}
]
"""

        raw_result = self.llm.chat(prompt, temperature=0.3)
        fallback = []
        
        try:
            result = parse_json_response(raw_result, fallback)
            if isinstance(result, list):
                return result
            return fallback
        except:
            return fallback

    def integrate_followup_answer(self, original_input: str, followup_qa: list) -> str:
        """
        将跟进问答整合到原始输入中，生成增强后的用户描述。
        followup_qa: [{"field": "...", "question": "...", "answer": "..."}, ...]
        返回: 增强后的用户输入文本
        """
        if not followup_qa:
            return original_input

        qa_block = "\n".join([
            f"Q: {item['question']}\nA: {item['answer']}"
            for item in followup_qa
        ])

        prompt = f"""
你是学习需求综合分析助手。

用户原始输入：
{original_input}

用户后续补充信息（问答形式）：
{qa_block}

请将两部分信息综合成一个更完整、更详细的学习需求描述。
描述应该包含：
1. 明确的学习目标
2. 学习时长和每日时间安排
3. 学习背景和前置知识
4. 学习风格和个人特点
5. 任何时间或环境约束

不要输出JSON，直接输出整合后的自然语言描述。
"""

        integrated = self.llm.chat(prompt, temperature=0.2)
        return integrated.strip()

    def should_continue_interaction(self, completeness_score: int) -> bool:
        """
        根据完整性分数判断是否需要继续多轮交互。
        < 60: 需要多轮补全
        60-85: 可以继续但建议补充关键项
        > 85: 信息充分
        """
        return completeness_score < 85
