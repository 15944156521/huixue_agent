# huixue_agent

AI 学习助手：Streamlit 前端 + DeepSeek API + LangGraph 编排 + 本地 BM25 RAG（`data/knowledge/`）。

## 运行

```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY=你的密钥
streamlit run app.py
```

数据库与知识库在首次运行时会写入 `data/`。
