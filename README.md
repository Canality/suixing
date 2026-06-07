# 随行 SuiXing — 本地生活 AI 管家

> **美团 AI Hackathon 2026** | OpenClaw 赛道 | 作品提交

**不用在美团/大众点评/高德/猫眼之间来回切换。跟"随行"说句话，它帮你查天气、找餐厅、规划路线、推荐活动，7x24 小时主动盯着变化，有情况立刻通知你。**

---

## Demo 访问

### 方式一: ngrok 公网隧道 (推荐，最简单)

```bash
# 终端1: 启动服务
python app.py

# 终端2: 启动公网隧道 → 获取 https://xxxx.ngrok-free.app 地址
ngrok http 8010
```

> 或一键启动: `.\start_public.ps1` (PowerShell)

### 方式二: Docker 部署

```bash
docker build -t suixing .
docker run -p 8010:8010 -e DEEPSEEK_API_KEY=sk-your-key suixing
```

| 入口 | 地址 |
|------|------|
| Web UI | `http://<host>:8010` |
| API 健康检查 | `http://<host>:8010/api/health` |
| SSE 技术面板 | `http://<host>:8010/api/events` |

---

## 功能全景

| 模块 | 能力 | 数据来源 |
|------|------|---------|
| 🍜 美食管家 | 搜索餐厅、实时排队、取号、口味匹配、群投票 | [美团] [大众点评] |
| 🚗 出行管家 | 多方式路线规划(打车/单车/地铁)、费用估算、导航链接 | [高德] |
| 🎬 娱乐管家 | 电影/展览/演出/户外活动搜索、天气联动推荐 | [猫眼] [大麦] |
| 🌤️ 天气监控 | 实时天气 + 分时段预报 + 活动建议 | [天气网] |
| 🔔 主动通知 | 三级事件分类 + LLM 自主判断推送 + 6 类机遇开关 | — |
| 🧠 用户记忆 | 口味/忌口/预算/住址持久化 + 每日日志 | — |
| 👁️ 长时监控 | Watchdog 条件监控 + 触发时 LLM 主动推理 + 跨 Skill 协同 | — |

---

## 评分项对照

| 评分维度 | 对应实现 | 关键亮点 |
|----------|---------|---------|
| **创新性** | 🧠 三级主动通知大脑 (`proactive.py`) | 个人/环境/机遇三级过滤 + 稀有度节流 (urgent→每次推, common→5次推1次)，不做信息垃圾推送器 |
| **完整性** | 🔄 端到端闭环 Skill | 餐饮: 搜索→排队→取号→监控触发→叫车联动；出行: 查天气→规划路线→生成导航链接→天气监控；102 项 Skill + E2E 测试覆盖 |
| **技术深度** | 🏙️ 高保真动态城市沙盒 | 非静态 JSON — 每30s Tick 更新排队/天气/票源/单车站，3个大型城市事件(马拉松/音乐节)触发跨域连锁反应 |
| **实用性** | 🔗 多源数据 + 反幻觉 + 记忆 | 一次对话查美团/高德/猫眼/天气网，14条反幻觉规则，来源强制标注，用户偏好持久化 + 每日记忆日志 |
| **用户体验** | 📱 手机模拟器 + SSE 技术面板 | 完整 Web UI，实时显示 Agent 思考→工具调用→结果→回复链路，沙盒事件可视化，机遇开关可配置 |

---

## 四大核心创新

### 1. 🧠 三级主动通知大脑 (Proactive Brain)

区别于被动的一问一答，随行实现了 **"个人事务 / 环境变化 / 机遇事件"** 三级过滤机制：

| 类别 | 推送规则 | 示例 |
|------|---------|------|
| 🔴 个人事务 | 一律提醒 | 加班、家人消息、生日提醒 |
| 🟡 环境变化 | 仅与确认计划冲突时提醒 | 天气突变影响骑行计划、场馆关闭 |
| 🟢 机遇事件 | 稀有度节流 + 6 类独立开关 | 有人退票、热门餐厅空桌、限时折扣 |

**创新点**: 引入 **RarityTracker 稀有度节流算法** — `urgent` 每次都推，`rare` 首次必推后续每 3 次推 1 次，`common` 每 5 次推 1 次。保证管家贴心而不骚扰。

### 2. 🏙️ 高保真动态城市沙盒 (Tick-based Dynamic Sandbox)

Mock 后端**不是静态 JSON**，而是一个每 30 秒"心跳"一次的生存系统：

- 餐厅排队自然流逝、随机"满座"和"空桌"
- 天气每 5 tick 变化一次，包含 6 个时段预报
- 场馆可能因天气关闭、地铁可能延误、单车站可能骑空
- 3 个大型城市事件 (马拉松封路 → 网约车停运 → 外卖延时 → 观赛特餐)
- 22 种个人生活事件 + 4 个记忆彩蛋 (去过 3 次川菜 → 解锁隐藏菜单)

### 3. 🔗 深层意图拆解 (Intent Deconstruction)

用户说"想骑行" → 管家自动拆解为:
1. `get_weather` — 天气是否允许？
2. `search_activities` — 附近有什么路线？
3. `plan_route` + `generate_route_link` — 规划路线 + 生成高德导航链接
4. `create_watch` — 创建天气反向监控（天气好也监控，防止变天）

用户一句话，管家自动执行 4 步工具链，用户无感知。

### 4. 🔄 端到端闭环 Skill

每个 Skill 覆盖从"想"到"做"的全链路：
- **dining-advisor**: 搜索 → 排队查询 → 取号 → 排队监控 → 快到时联动打车
- **commute-planner**: 路线规划 → 多方式对比 → 导航链接 → 实时路况
- **leisure-scout**: 天气 → 活动搜索 → 室内/室外推荐 → 票源监控

---

## 评委验收用例

> 在 Web UI 聊天框中依次输入以下用例，观察右侧 SSE 技术面板验证工具调用链路。
> 每个用例对应一项核心创新，共 **6 个场景 60 分**。

### 场景 1: 意图拆解 — 一句话触发多工具链 (10 分)

验证 **深层意图拆解** 能力。

**输入:** `周末想去骑行，帮我看看天气和路线`

**观察 SSE 面板 — 应依次出现 ≥4 次工具调用:**

| 顺序 | 工具 | 作用 |
|------|------|------|
| 1 | `get_weather` | 天气是否允许户外骑行 |
| 2 | `search_activities` | 查找附近骑行路线 |
| 3 | `plan_route` / `generate_route_link` | 路线规划 + 高德导航链接 |
| 4 | `create_watch` | 创建天气反向监控（天气好也监控，防变天） |

**评分:** 触发 ≥3 个工具 (5 分) → +自动创建监控 (3 分) → +回复含导航链接 (2 分)

> 💡 用户只说了一句话，管家自动拆解为 4 步工具链。普通 chatbot 只会回答"天气不错"。

---

### 场景 2: 跨 Skill 协同 — 吃饭+电影一键安排 (10 分)

验证 **端到端闭环 Skill** 和跨域联动能力。

**输入:** `帮我安排今晚: 先吃饭再看电影`

**观察:**

| 预期行为 | 验证点 |
|---------|-------|
| 先调用 `search_restaurants` 推荐餐厅 | 返回望京附近餐厅 + `[美团]` 标签 |
| 再调用 `search_activities` (category=电影) | 返回近期电影排片 + `[猫眼]` 标签 |
| 回复中串联两个推荐 | 如"先吃川菜，再看科幻，都在望京凯德MALL附近" |
| 可能暗含路线建议 | 标注距离/步行时间 |

**评分:** 两工具均调用 (4 分) → 推荐有逻辑串联 (3 分) → 含来源标签 (3 分)

> 💡 用户不用在美团和猫眼之间切换。一个对话完成跨域规划，这才是管家的价值。

---

### 场景 3: 主动监控 — 排队快到了自己通知你 (10 分)

验证 **Watchdog 长时监控** 和主动推送能力。

**Step 1 — 输入:** `帮我看看望京的火锅店，排队少的`

观察 Agent 返回火锅店列表 + 实时排队数据。

**Step 2 — 输入:** `帮我在后院火锅取个号`

观察 Agent 取号成功 + 返回排队号码。

**Step 3 — 验证后台监控已创建:**

访问 `http://<host>:8010/api/watch/list`，应看到类似:
```json
{"tasks": [{"target_name": "后院·川渝火锅", "condition": "queue_length <= ...", "status": "active"}]}
```

**Step 4 — 等待沙盒触发:**

观察左上角 🎲 沙盒事件面板。当 `queue_update` 事件导致排队数降到阈值以下时:
- 右侧 SSE 面板显示 `watch_triggered_raw` → `watch_triggered`
- Agent 主动推送消息告知用户

**评分:** 取号成功 (2 分) → API 可查到监控 (3 分) → 条件触发时 SSE 有通知 (5 分)

> 💡 普通 chatbot 取完号就结束了。随行在后台持续盯着排队进度，快到了主动通知你。这才是 7x24 管家。

---

### 场景 4: 环境变化关怀 — 天气变了我通知你 (10 分)

验证 **Proactive Brain 三级通知** 的环境变化感知能力。

**Step 1 — 输入:** `记住我周六下午习惯去温榆河骑行，怕下雨`

观察 Agent 调用 `remember` 记录骑行偏好。

**Step 2 — 输入:** `明早想去奥森公园骑行`

观察 Agent 查天气 → 确认晴朗 → 推荐路线 → **自动创建天气监控**。

**Step 3 — 观察 SSE 面板:**

后台心跳线程每 30s 检查天气。观察 SSE 面板中的 `heartbeat_weather` 事件。如果天气变为雨天，ProactiveBrain 检测到与活跃计划冲突 → 主动推送替代方案。

**评分:** 正确记录偏好 (2 分) → 第 2 步含路线推荐 (2 分) → 自动创建天气监控 (3 分) → 天气变化时主动推送 (3 分)

> 💡 管家不只是回答"天气好"，而是"天气好我推荐，但万一下雨我第一个告诉你，还帮你找好室内备选"。正是环境变化过滤的价值。

---

### 场景 5: 机遇捕捉 — 有人退票了 (10 分)

验证 **机遇事件 + 稀有度节流** 机制。

**Step 1 — 输入:** `想看脱口秀开放麦，还有票吗`

观察 Agent 查询活动状态。如果返回 `sold_out`，Agent 应自动创建票源监控并回复"有票立刻通知你"。

**Step 2 — 观察沙盒事件面板 (左上角 🎲):**

沙盒每 5s 刷新，约 5% 概率触发 `ticket_released` (退票事件)。观察事件面板中的绿色 `🟢 机遇` 标签事件。

**Step 3 — 触发时:**

- SSE 面板显示 `watch_triggered` 事件
- Agent 主动推送: "小明，刚才有人退了 1 张脱口秀的票！"

**评分:** 售罄后自动创建监控 (3 分) → 沙盒事件面板可见 (2 分) → 触发时主动推送 (3 分) → 推送含行动指引 (2 分)

> 💡 管家在后台安静守候那个 5% 概率的退票事件，触发瞬间推送。不骚扰用户，只在"机遇"来临时出手。

---

### 场景 6: 记忆驱动 — 越用越懂你 (10 分)

验证 **用户记忆系统** 的个性化能力。

**Step 1 — 输入:** `记住我喜欢吃川菜和日料，人均预算不超过100元，家在望京SOHO`

观察 Agent 调用 ≥3 次 `remember`，分别记录口味/预算/地址。

**Step 2 — 输入:** `帮我推荐附近好吃的`

**观察 — 回复应体现记忆过滤:**

| 验证点 | 说明 |
|--------|------|
| 菜系偏向川菜/日料 | 自动过滤火锅/湘菜/粤菜等 |
| 价格 ≤ 100 | 过滤海底捞(¥130)、鮨鲜(¥180) |
| 优先望京区域 | 排在酒仙桥餐厅前面 |
| 个性化表达 | "根据你的口味偏好，推荐以下..." |

**Step 3 — 输入:** `从我家去胖妹面庄怎么走`

观察 Agent 使用记忆中的"望京SOHO"作为出发地，无需再次询问。

**评分:** 偏好正确记录 (3 分) → 推荐结果体现过滤 (3 分) → 自动引用记忆地址 (2 分) → 个性化表达 (2 分)

> 💡 每次都重新问"你在哪？喜欢什么？预算多少？"那不叫管家。记住你的偏好、自动应用、无缝体验 —— 这才是私人管家。

---

| 场景 | 验证的核心创新 | 满分 |
|------|---------------|------|
| 场景 1: 意图拆解 | 深层意图拆解 | 10 |
| 场景 2: 跨 Skill 协同 | 端到端闭环 Skill | 10 |
| 场景 3: 主动监控 | Watchdog 长时监控 | 10 |
| 场景 4: 环境变化关怀 | Proactive Brain 三级通知 | 10 |
| 场景 5: 机遇捕捉 | 机遇事件 + 稀有度节流 | 10 |
| 场景 6: 记忆驱动 | 用户记忆系统 | 10 |
| **总分** | | **60** |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI + Uvicorn |
| LLM | DeepSeek Chat (Function Calling) |
| 前端 | 单页 HTML/CSS/JS (无框架依赖) |
| 实时推送 | SSE (Server-Sent Events) |
| 容器化 | Docker + Sealos (Kubernetes) |
| 外部依赖 | 无数据库、无外部服务 — Mock 数据全部内嵌 |

---

## 项目结构

```
meituan-travel-assistant/
│
├── app.py                        # FastAPI 入口 (Web UI + Chat API + Mock API)
├── requirements.txt              # Python 依赖
├── Dockerfile                    # 容器构建
├── render.yaml                   # Render.com 部署配置
│
├── server/                       # 核心引擎
│   ├── config.py                 # 环境变量 + 路径加载
│   ├── llm.py                    # DeepSeek API 封装 (chat + function calling)
│   ├── prompts.py                # 三层 Prompt 架构 (5min/30min/实时缓存)
│   ├── session.py                # 会话管理 + ReAct 循环 (最多 5 轮工具调用)
│   ├── tools.py                  # 9 个工具定义 + 执行调度
│   ├── proactive.py              # LLM 主动通知引擎 (三级事件分类)
│   ├── watchdog.py               # 条件监控引擎 (程序化条件匹配)
│   ├── memory.py                 # 用户画像读写 (USER.md 持久化)
│   ├── event_bus.py              # SSE 事件总线
│   └── opportunity_config.py     # 机遇事件 6 类开关
│
├── mock_backend/                 # 动态沙盒
│   ├── mock_data.py              # 12 餐厅 + 8 活动 + 路线 + 单车 + 天气
│   ├── event_engine.py           # 每 30s 状态变化引擎
│   ├── mega_events.py            # 3 个大型城市事件 (连锁反应)
│   └── life_events.py            # 22 种生活事件 + 4 个记忆彩蛋
│
├── openclaw-workspace/           # OpenClaw 工作区 (可与 Gateway 直接使用)
│   ├── SOUL.md                   # Agent 人设 + 核心原则
│   ├── AGENTS.md                 # 行为规则 + 工作流
│   ├── anti_hallucination_prompt.md  # 14 条反幻觉规则
│   ├── USER.md                   # 用户画像 (运行时动态更新)
│   ├── memory/                   # 每日对话日志
│   └── skills/                   # 3 个核心 Skill
│       ├── dining-advisor/       # 🍜 美食管家
│       ├── commute-planner/      # 🚗 出行管家
│       └── leisure-scout/        # 🎬 娱乐向导
│
├── deploy/
│   └── sealos.yaml               # Kubernetes 部署 (Deployment + Service + Ingress)
│
├── templates/
│   └── index.html                # Web UI (手机模拟器 + 聊天 + SSE 面板)
│
└── tests/                        # 153 项测试
    ├── test_mock_backend.py      # Mock API 测试 (14 项)
    ├── test_skills.py            # Skill 脚本测试 (41 项)
    ├── test_memory.py            # 用户记忆测试 (25 项)
    └── test_e2e.py               # 端到端测试 (76 项)
```

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key (从 https://platform.deepseek.com/api_keys 获取)

# 3. 一键启动
python app.py
# → Web UI:    http://localhost:8010
# → API:       http://localhost:8010/api/health
# → SSE 面板:  http://localhost:8010/api/events
```

---

## 部署指南

### 方式一: Docker

```bash
docker build -t suixing .
docker run -p 8010:8010 -e DEEPSEEK_API_KEY=sk-your-key suixing
```

### 方式二: Sealos (Kubernetes)

```bash
# 1. 创建 Secret (替换为你的 API Key)
kubectl create secret generic suixing-secret \
  --from-literal=DEEPSEEK_API_KEY=sk-your-key

# 2. 部署
kubectl apply -f deploy/sealos.yaml

# 3. 查看状态
kubectl get pods -l app=suixing
kubectl get ingress suixing
```

### 方式三: Render.com

项目根目录包含 `render.yaml`，推送到 GitHub 后在 Render 一键部署。详见 [DEPLOY.md](DEPLOY.md)。

---

## 文档索引

| 文档 | 内容 | 面向 |
|------|------|------|
| [README.md](README.md) | 项目概览、快速开始、部署 | 所有人 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构、数据流、设计决策 | 评委/开发者 |
| [SANDBOX.md](SANDBOX.md) | 沙盒事件系统设计 (三级分类 + 连锁 + 彩蛋) | 评委/开发者 |
| [DEPLOY.md](DEPLOY.md) | 部署指南 (Docker/Sealos/Render) | 运维 |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 5 分钟演示脚本 + 检查清单 | 演示者 |
| [TEST_CASES.md](TEST_CASES.md) | 评委验收用例 (3 演示剧本 + 7 系统用例, 100 分) | 评委 |
| [TEST_SUITE.md](TEST_SUITE.md) | 自动化测试覆盖总览 (153 项) | 评委 |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | 开发计划 + 进度追踪 | 开发者 |
| [openclaw-workspace/](openclaw-workspace/) | OpenClaw 工作区完整文件 | OpenClaw 用户 |

---

## 测试

共 **153 项测试，全部通过，0 失败**。

| 文件 | 数量 | 覆盖 |
|------|------|------|
| `tests/test_mock_backend.py` | 14 | Health / Restaurant / Queue / Weather / Activity / Events API |
| `tests/test_skills.py` | 41 | dining-advisor(18) + commute-planner(8) + leisure-scout(15) |
| `tests/test_memory.py` | 22 | Profile 读写 / Layer2 摘要 / Layer3 查询 / 缓存 TTL |
| `tests/test_e2e.py` | 76 | Health / Config / Prompt / Session / Tools / EventBus / Heartbeat |

```bash
# 运行全部测试 (需先启动 Server: python app.py)
python tests/test_memory.py           # 纯单元测试，无需 Server
python tests/test_mock_backend.py     # 需 Server 运行
python tests/test_skills.py           # 需 Server 运行
python tests/test_e2e.py              # 需 Server 运行
```

---

## OpenClaw 兼容

`openclaw-workspace/` 目录可直接用于 OpenClaw Gateway:

```bash
npm install -g openclaw@latest
cp -r openclaw-workspace/* ~/.openclaw/workspace/
openclaw gateway --port 18789
# → http://localhost:18789 → 在飞书/WebChat 中与 Agent 对话
```

---

*SuiXing v2.0 — Built for 美团 AI Hackathon 2026 | Author: Canaan*
