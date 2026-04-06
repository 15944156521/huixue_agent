from utils.llm import LLMClient
from utils.json_parser import parse_json_response


class InputParser:

    def __init__(self, api_key):
        self.llm = LLMClient(api_key)

    def parse(self, user_input):

        prompt = f"""
你是一名学习需求解析助手。

请将用户的学习需求解析为结构化JSON。

用户输入：
{user_input}

请严格输出JSON（不要加解释文本）：
{{
    "subject": "学习科目",
    "duration_days": 14,
    "daily_hours": 3,
    "focus_topics": ["重点1", "重点2"],
    "target_description": "用户目标摘要",
    "background": "学习背景",
    "learning_style": "学习风格（快速突进/循序渐进）",
    "constraints": "时间或其他约束"
}}
"""

        raw_result = self.llm.chat(prompt, temperature=0.2)
        fallback = {
            "subject": "",
            "duration_days": 7,
            "daily_hours": 1.0,
            "focus_topics": [],
            "target_description": user_input,
            "background": "",
            "learning_style": "平衡",
            "constraints": "",
        }
        parsed_result = parse_json_response(raw_result, fallback)

        return parsed_result

    def parse_enriched(self, integrated_description: str) -> dict:
        """
        解析多轮交互后的增强用户描述。
        返回完整的用户画像。
        """
        return self.parse(integrated_description)


if __name__ == "__main__":

    parser = InputParser(api_key="你的APIKEY")

    result = parser.parse(
        "我想两周复习操作系统，每天3小时，主要看进程和内存管理"
    )

    print(result)