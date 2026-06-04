# 部署指南

## 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
# 编辑 .env 文件, 填入 DeepSeek API Key:
#   DEEPSEEK_API_KEY=sk-your-key-here

# 3. 启动
python app.py

# 4. 打开浏览器
# http://localhost:8010
```

## 一键部署到 Render (推荐)

Render 免费层无需信用卡，GitHub 推送自动部署。

### 步骤

1. 推送代码到 GitHub
2. 打开 [render.com](https://render.com) → Sign in with GitHub
3. **New Web Service** → 选择仓库
4. Render 自动识别 `render.yaml`:
   - Build: `pip install -r requirements.txt`
   - Start: `python app.py`
5. 设置环境变量: `DEEPSEEK_API_KEY` = 你的API Key
6. 点击 Deploy → 等待 2 分钟

### render.yaml 内容

```yaml
services:
  - type: web
    name: suixing
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    envVars:
      - key: DEEPSEEK_API_KEY
        sync: false
```

## 部署到 Railway

Railway 也支持 GitHub 自动部署:

1. 打开 [railway.app](https://railway.app) → 登录
2. New Project → Deploy from GitHub repo
3. 设置 `DEEPSEEK_API_KEY` 环境变量
4. 自动构建并部署

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DEEPSEEK_API_KEY | - | **必填**, DeepSeek API Key |
| HOST | 0.0.0.0 | 监听地址 |
| PORT | 8010 | 监听端口 |
| LLM_MODEL | deepseek-chat | LLM 模型名 |

## 系统要求

- Python 3.10+
- 内存: 256MB+ (仅Python进程)
- 无需数据库、无需外部服务
- Mock 数据全部内嵌在内存中
