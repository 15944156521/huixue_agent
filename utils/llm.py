"""
LLM统一封装模块（DeepSeek）

作用：
1 统一管理DeepSeek API调用
2 避免在各个Agent中重复写client
3 方便未来更换模型
"""

import os

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI


class LLMClient:

    def __init__(self, api_key):
        """
        初始化DeepSeek客户端
        """

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=float(os.getenv("LLM_TIMEOUT", "60")),
        )

        # 默认模型
        self.model = "deepseek-chat"

    def chat(self, prompt, temperature=0.7):
        """
        普通对话调用
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature
            )
            return response.choices[0].message.content
        except (APITimeoutError, APIConnectionError, APIError):
            # Return empty content so upper layers can use fallback data.
            return ""

    def chat_with_system(self, system_prompt, user_prompt, temperature=0.7):
        """
        带system prompt的调用
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature
            )
            return response.choices[0].message.content
        except (APITimeoutError, APIConnectionError, APIError):
            return ""