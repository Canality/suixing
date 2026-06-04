# 随行 SuiXing — 技术架构

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web UI (手机模拟器)                     │
│  ┌──────────┐  ┌───────────┐  ┌────────────────────┐   │
│  │ 对话界面  │  │ 沙盒面板   │  │ 技术面板(SSE实时)   │   │
│  └────┬─────┘  └─────┬─────┘  └────────┬───────────┘   │
│       │              │                 │                │
│  POST /api/chat  GET /api/sandbox  GET /api/events(SSE) │
└───────┼──────────────┼─────────────────┼────────────────┘
        │              │                 │
┌───────┼──────────────┼─────────────────┼────────────────┐
│       ▼              ▼                 ▼                │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐           │
│  │ Session │  │ Event    │  │ Proactive    │           │
│  │ ReAct   │  │ Engine   │  │ Brain (LLM)  │           │
│  │ Loop    │  │ (30s)    │  │ (30s)        │           │
│  └────┬────┘  └────┬─────┘  └──────┬───────┘           │
│       │            │               │                    │
│       ▼            ▼               ▼                    │
│  ┌──────────────────────────────────────┐              │
│  │         DeepSeek API (LLM)           │              │
│  └──────────────────────────────────────┘              │
│                                                         │
│  ┌──────────────────────────────────────┐              │
│  │         Mock Backend (动态沙盒)       │              │
│  │  ┌──────────┐ ┌──────────┐ ┌──────┐ │              │
│  │  │ Restaurant│ │ Weather  │ │Venue │ │              │
│  │  │ State (12)│ │ State    │ │State │ │              │
│  │  └──────────┘ └──────────┘ └──────┘ │              │
│  │  ┌──────────┐ ┌──────────┐ ┌──────┐ │              │
│  │  │ Activity │ │ Bike     │ │ Life │ │              │
│  │  │ State (8)│ │ State    │ │Events│ │              │
│  │  └──────────┘ └──────────┘ └──────┘ │              │
│  │  ┌──────────┐ ┌──────────────────┐   │              │
│  │  │ Mega     │ │ Story Chains    │   │              │
│  │  │ Events   │ │ (延时剧情)       │   │              │
│  │  └──────────┘ └──────────────────┘   │              │
│  └──────────────────────────────────────┘              │
│                                                         │
│         FastAPI Server (app.py)                         │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Session & ReAct 循环 (`server/session.py`)

每个用户对话遵循 ReAct 模式:
```
用户消息 → LLM判断 → 工具调用 → 执行 → 结果返回LLM → 继续/回复
         └──────────── 最多5轮 ────────────┘
```

- 工具去重: 10秒窗口内相同调用不重复执行
- 历史管理: 智能截断，保证 tool_call/tool_result 不拆散

### 2. Prompt 三层架构 (`server/prompts.py`)

| 层 | 内容 | TTL |
|----|------|-----|
| Layer 1 | SOUL + 反幻觉 + 工具说明 + 行为规则 | 5min |
| Layer 2 | 用户画像摘要 | 30min |
| Layer 3 | 按需查询 (get_user_profile) | 实时 |

### 3. 用户记忆 (`server/memory.py`)

- 持久化: `openclaw-workspace/USER.md` (Markdown)
- 字段分类: 食/衣/住/行/娱/状态
- 追加型字段: cuisines_liked, sports, wishlist (自动合并)
- 覆盖型字段: budget, home, work

### 4. 主动通知 (`server/proactive.py`)

三级事件分类 + LLM自主判断:

| 类别 | 规则 | 示例 |
|------|------|------|
| 个人事务 | 一律提醒 | 加班、生病、家人消息 |
| 环境变化 | 仅与确认计划冲突时提醒 | 天气变化、场馆关闭 |
| 机遇事件 | 稀有度节流 + 6类开关 | 退票、特价、空桌 |

### 5. 沙盒引擎 (`mock_backend/`)

见 [SANDBOX.md](SANDBOX.md)

## 数据流

### 用户对话流
```
用户输入 → /api/chat → Session.handle_message()
  → build_system_prompt() (profile + rules)
  → chat_with_tools() (DeepSeek Function Calling)
  → execute_tool_call() (subprocess → HTTP → Mock API)
  → 结果返回 LLM → 生成回复
  → 更新 proactive context
```

### 主动通知流
```
Event Engine (30s tick)
  → Mock State 更新
  → 事件写入 _events_log
ProactiveBrain (30s check)
  → 读取 events + profile + context
  → 三级分类 + 频次过滤
  → LLM自主判断 → NOTIFY / SILENT
  → SSE 推送 → Web UI
```

## 技术选型

| 选择 | 理由 |
|------|------|
| FastAPI | 异步支持 + SSE 原生支持 |
| DeepSeek | Function Calling 原生支持 |
| 子进程执行 Skill | 隔离 Skill 脚本，不影响主进程 |
| Mock 内嵌 | 单文件部署，无需外部依赖 |
| SSE | 单向推送，适合通知场景 |