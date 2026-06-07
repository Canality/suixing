# 部署指南

---

## 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env, 填入 DeepSeek API Key:
#   DEEPSEEK_API_KEY=sk-your-key-here

# 3. 启动
python app.py

# 4. 打开浏览器
# http://localhost:8010
```

---

## 方式一: Docker 部署

```bash
# 构建镜像
docker build -t suixing .

# 运行容器
docker run -d -p 8010:8010 \
  -e DEEPSEEK_API_KEY=sk-your-key-here \
  --name suixing \
  suixing

# 验证
curl http://localhost:8010/api/health
```

### 推送到镜像仓库

```bash
docker tag suixing docker.io/<your-username>/suixing:latest
docker push docker.io/<your-username>/suixing:latest
```

---

## 方式二: Sealos (Kubernetes) 部署

Sealos 是一个 Kubernetes 发行版，支持一键部署。

### 前置准备

1. 已有 Sealos 集群或 [sealos.io](https://sealos.io) 账号
2. 镜像已推送到可访问的镜像仓库

### 部署步骤

```bash
# 1. 创建 Secret (替换为你的 API Key)
kubectl create secret generic suixing-secret \
  --from-literal=DEEPSEEK_API_KEY=sk-your-key-here

# 2. 应用部署配置
kubectl apply -f deploy/sealos.yaml

# 3. 查看部署状态
kubectl get pods -l app=suixing
kubectl get svc suixing
kubectl get ingress suixing

# 4. 获取访问地址
kubectl get ingress suixing -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

### 部署文件说明 (`deploy/sealos.yaml`)

| 资源 | 说明 |
|------|------|
| Secret | 存储 DEEPSEEK_API_KEY |
| Deployment | 1 副本，256Mi-512Mi 内存，liveness + readiness 探针 |
| Service | 端口 8010 |
| Ingress | 外部访问入口 (修改 host 为实际域名) |

> 部署前请将 `sealos.yaml` 中 Ingress 的 `host` 字段改为实际域名，Secret 中的 API Key 改为真实值。

---

## 方式三: Render.com (免费层)

Render 免费层无需信用卡，GitHub 推送自动部署。

### 步骤

1. 推送代码到 GitHub
2. 打开 [render.com](https://render.com) → Sign in with GitHub
3. **New Web Service** → 选择仓库
4. Render 自动识别 `render.yaml`:
   - Build: `pip install -r requirements.txt`
   - Start: `python app.py`
5. 设置环境变量: `DEEPSEEK_API_KEY` = 你的 API Key
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

---

## 环境变量

| 变量 | 默认值 | 必填 | 说明 |
|------|--------|------|------|
| `DEEPSEEK_API_KEY` | - | 是 | DeepSeek API Key |
| `HOST` | `0.0.0.0` | 否 | 监听地址 |
| `PORT` | `8010` | 否 | 监听端口 |
| `LLM_MODEL` | `deepseek-chat` | 否 | LLM 模型名 |
| `LLM_BASE_URL` | `https://api.deepseek.com` | 否 | LLM API 地址 |

---

## 系统要求

- Python 3.10+
- 内存: 256MB+ (仅 Python 进程)
- 无需数据库、无需外部服务
- Mock 数据全部内嵌在内存中
