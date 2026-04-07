from openai import OpenAI

client = OpenAI(
    api_key="sk-f2ea0277b95141aba33bd194d4dee28b",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "请帮我制定一个7天的Python学习计划"}
    ]
)

print(response.choices[0].message.content)