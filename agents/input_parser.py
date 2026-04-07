from utils.llm import LLMClient
from utils.json_parser import parse_json_response


class InputParser:

    def __init__(self, api_key):
        self.llm = LLMClient(api_key)

    def parse(self, user_input):

        prompt = f"""
你是一名学习需求解析助手。

请将用户的学习需求解析为结构化 JSON。

用户输入：
{user_input}

【必须遵守】不要猜测或编造用户未表达的信息：
- duration_days：仅当用户在原文中明确给出学习周期（如「两周」「14天」「一个月」等可换算为整数天）时填写正整数；否则必须填 null（不要默认 7 或 14）。
- daily_hours：仅当用户明确说了每天/每日可学习的小时数时填写正数；否则必须填 null（不要默认 1 或 2）。
- focus_topics：仅当用户明确提到具体章节、知识点、模块名称时填写字符串数组；用户只笼统说「复习某门课」而未提重点时，必须填 []（空数组），不要臆造重点。
- subject：尽量从用户话里归纳出一门课或学习主题；完全无法判断时填 ""。
- target_description：用一两句话客观概括用户已表达的目标，可引用或压缩原文；不要添加用户没说的具体安排。

请严格输出 JSON（不要加解释文本、不要用 markdown 代码块）：
{{
    "subject": "学习科目或空字符串",
    "duration_days": null,
    "daily_hours": null,
    "focus_topics": [],
    "target_description": "用户目标摘要"
}}
"""

        raw_result = self.llm.chat(prompt, temperature=0.2)
        fallback = {
            "subject": "",
            "duration_days": None,
            "daily_hours": None,
            "focus_topics": [],
            "target_description": (user_input or "").strip(),
        }
        parsed_result = parse_json_response(raw_result, fallback)

        return parsed_result


if __name__ == "__main__":

    parser = InputParser(api_key="你的APIKEY")

    result = parser.parse(
        "我想两周复习操作系统，每天3小时，主要看进程和内存管理"
    )

    print(result)