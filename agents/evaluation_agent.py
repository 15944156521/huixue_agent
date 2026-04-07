from utils.llm import LLMClient
from utils.json_parser import parse_json_response


class EvaluationAgent:

    def __init__(self, api_key):
        self.llm = LLMClient(api_key)

    def evaluate(self, learning_topic, rag_context=None):
        rag_block = ""
        if rag_context:
            rag_block = f"""

以下是从本地知识库检索到的参考片段（RAG）。出题时请结合与用户学习内容相关的知识点；若片段无关可忽略：
{rag_context}
"""

        prompt = f"""
你是一名学习评估助手。

根据学习内容生成测试问题，以评估学习效果。

学习内容：
{learning_topic}
{rag_block}

请严格输出JSON（不要加解释文本）：
{{
  "questions": [
    {{
      "id": 1,
      "type": "基础理解",
      "question": "问题内容",
      "reference_answer": "参考答案",
      "check_point": "考察点"
    }},
    {{
      "id": 2,
      "type": "概念理解",
      "question": "问题内容",
      "reference_answer": "参考答案",
      "check_point": "考察点"
    }},
    {{
      "id": 3,
      "type": "应用思考",
      "question": "问题内容",
      "reference_answer": "参考答案",
      "check_point": "考察点"
    }}
  ],
  "focus_summary": "本次检测关注的核心知识点"
}}
"""

        raw_result = self.llm.chat(prompt)
        fallback = {
            "questions": [
                {
                    "id": 1,
                    "type": "基础理解",
                    "question": "请概述今天学习内容中的一个核心概念。",
                    "reference_answer": "能准确描述核心概念并说明作用。",
                    "check_point": "基础概念掌握",
                },
                {
                    "id": 2,
                    "type": "概念理解",
                    "question": "请解释两个相关知识点之间的区别与联系。",
                    "reference_answer": "能从定义、用途和场景说明差异与联系。",
                    "check_point": "概念辨析能力",
                },
                {
                    "id": 3,
                    "type": "应用思考",
                    "question": "请结合一个实际场景说明如何应用今天的知识。",
                    "reference_answer": "能结合场景给出合理分析或解决思路。",
                    "check_point": "知识迁移能力",
                },
            ],
            "focus_summary": "围绕本次学习内容进行基础、理解和应用层面的检测。",
        }
        result = parse_json_response(raw_result, fallback)

        return result