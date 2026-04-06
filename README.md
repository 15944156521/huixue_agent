# AI 学习助手 - 惠学 Agent

一个基于 LLM 和 LangGraph 的智能学习计划生成和优化系统。

## 功能特性

- 📋 **智能计划生成**：根据用户输入生成个性化学习计划
- 📊 **进度跟踪**：记录学习进度并提供反馈
- 🔄 **动态调整**：根据进度自动优化学习计划
- 🧠 **RAG 检索**：融合知识库进行更精准的规划

## 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行 Streamlit 应用
streamlit run huixue_agent/app.py
```

访问 http://localhost:8501

### 环境配置

创建 `.env` 文件或设置环境变量：

```
DEEPSEEK_API_KEY=your_deepseek_api_key
```

## 项目结构

```
huixue_agent/
├── app.py                    # Streamlit 主应用
├── main.py                   # CLI 演示脚本
├── requirements.txt          # Python 依赖
├── agents/                   # AI Agent 模块
│   ├── plan_agent.py
│   ├── evaluation_agent.py
│   └── optimization_agent.py
├── services/                 # 业务服务
│   ├── study_planner_service.py
│   └── schedule.py
├── rag/                      # RAG 检索模块
├── storage/                  # 数据存储
├── graph/                    # LangGraph 工作流
└── data/                     # 知识库
    └── knowledge/            # 可添加 .md / .txt 文件
```

## 部署到云上

### 使用 Streamlit Cloud（推荐）

1. **上传代码到 GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/huixue_agent.git
   git push -u origin main
   ```

2. **部署到 Streamlit Cloud**
   - 访问 https://streamlit.io/cloud
   - 点击"New app"
   - 选择你的 GitHub repository
   - 选择 `huixue_agent/app.py` 文件
   - 点击"Deploy"

3. **配置环境变量**
   - 在 Streamlit Cloud 应用设置中
   - 添加密钥：`DEEPSEEK_API_KEY` = 你的 API Key
   - 点击保存并重启应用

### 其他部署选项

#### Docker 部署
```bash
docker build -t huixue-agent .
docker run -p 8501:8501 -e DEEPSEEK_API_KEY=your_key huixue-agent
```

#### Railway 部署
1. 连接 GitHub 仓库到 Railway
2. 添加环境变量 `DEEPSEEK_API_KEY`
3. 自动部署

## 配置说明

- **Streamlit 配置**：`.streamlit/config.toml`
- **知识库**：在 `data/knowledge/` 下添加 `.md` 或 `.txt` 文件
- **API Key**：通过环境变量 `DEEPSEEK_API_KEY` 配置

## 技术栈

- Python 3.13
- Streamlit - 前端框架
- LangGraph - AI 工作流编排
- OpenAI / DeepSeek API
- SQLite - 数据存储

## 常见问题

**Q: 部署后找不到知识库文件？**  
A: 上传 GitHub 时确保 `data/knowledge/` 目录及文件已提交

**Q: API Key 不工作？**  
A: 检查 Streamlit Cloud 的密钥是否正确设置为 `DEEPSEEK_API_KEY`

**Q: 如何更新部署的应用？**  
A: Push 到 GitHub，Streamlit Cloud 会自动重新部署

## 许可证

MIT

---

💡 有问题？请提 Issue 或 PR
