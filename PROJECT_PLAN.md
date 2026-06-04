# 美团AI Hackathon — 随行 SuiXing 开发计划 v2

> **赛道**: 基于OpenClaw的本地生活"全天候私人管家"
> **提交截止**: 2026-06-07
> **最后更新**: 2026-06-02

---

## 一、核心策略: 双轨并行

### 轨道 1: Demo Server (演示用)
一个自建的 FastAPI Web 应用，包含手机模拟器UI + 对话交互。评审打开浏览器就能看到完整演示，一键启动，零外部依赖（除 DeepSeek API）。

### 轨道 2: OpenClaw Workspace (实际框架)
完整的 OpenClaw 工作区文件。如果评审安装了 OpenClaw Gateway，把工作区复制进去就能在飞书/WebChat 中运行。这是"基于OpenClaw框架"的证明。

### 两者关系
```
OpenClaw Workspace (SOUL.md / SKILL.md / scripts)
         ↑ 共享同一套文件
Demo Server  ←  读取workspace文件  ←  拼prompt  ←  调LLM  ←  调脚本
    ↓
浏览器 (手机模拟器UI)
```

---

## 二、提交作品结构

```
buyu-meituan/                         # 提交目录
│
├── README.md                         # ✅ 项目说明 + 快速开始
├── DEMO_SCRIPT.md                    # ✅ 5分钟演示脚本
├── requirements.txt                  # ✅ Python依赖
│
├── app.py                            # ✅ Demo Server 入口
├── server/                           # ✅ Demo Server 核心
│   ├── __init__.py                   # ✅
│   ├── config.py                     # ✅ 配置加载(LLM key等)
│   ├── session.py                    # ✅ 会话状态机 + Agent逻辑
│   ├── llm.py                        # ✅ LLM客户端(DeepSeek)
│   ├── prompts.py                    # ✅ Prompt模板(从workspace文件加载)
│   ├── tools.py                      # ✅ 工具执行器(调scripts)
│   └── event_bus.py                  # ✅ SSE事件推送
│
├── templates/
│   └── index.html                    # ✅ Web UI (手机模拟器)
│
├── openclaw-workspace/               # ✅ OpenClaw 工作区
│   ├── SOUL.md                       # ✅ 管家人设
│   ├── AGENTS.md                     # ✅ 行为规则+工作流
│   ├── USER.md                       # ✅ 用户画像
│   ├── IDENTITY.md                   # ✅ Agent身份
│   ├── MEMORY.md                     # ✅ 长期记忆索引
│   ├── HEARTBEAT.md                  # ✅ 7x24后台任务定义
│   ├── TOOLS.md                      # ✅ 工具配置
│   ├── BOOTSTRAP.md                  # ✅ 首次对话引导
│   ├── anti_hallucination_prompt.md  # ✅ 反幻觉规则(已重写为本地生活领域)
│   ├── memory/                       # ✅ 每日记忆日志
│   └── skills/                       # ✅ 3个核心Skill
│       ├── dining-advisor/           # ✅ Skill 1: 🍜 餐饮顾问
│       │   ├── SKILL.md
│       │   └── scripts/
│       ├── commute-planner/          # ✅ Skill 2: 🚗 出行管家
│       │   ├── SKILL.md
│       │   └── scripts/
│       └── leisure-scout/            # ✅ Skill 3: 🎬 娱乐向导
│           ├── SKILL.md
│           └── scripts/
│
├── mock_backend/                     # ✅ Mock数据 + API
│   ├── mock_data.py                  # ✅ 12餐厅+8活动+天气+路线+单车
│   └── event_engine.py               # ✅ 随机事件引擎
│
├── tests/
│   ├── test_mock_backend.py          # ✅ Mock API测试 (14项)
│   ├── test_skills.py                # ✅ Skill脚本测试 (41项)
│   └── test_e2e.py                   # ✅ 端到端测试 (76项)
│
└── docs/
    └── architecture.png              # TODO: 架构图
```

---

## 三、Demo Server 架构

```
Browser (http://localhost:8010)
    │
    ├── GET  /               → 返回 index.html (手机模拟器)
    ├── POST /api/chat       → 发送消息 → Agent处理 → 返回回复
    ├── GET  /api/events     → SSE 技术面板 (Agent思考过程)
    │
    ▼
Server (app.py + server/)
    │
    ├── 1. 加载workspace文件
    │      SOUL.md → agent persona
    │      AGENTS.md → behavior rules
    │      skills/*/SKILL.md → skill routing
    │
    ├── 2. 会话管理 (server/session.py)
    │      多轮对话上下文
    │      意图路由 → 选择Skill
    │      状态机: idle → intent → searching → presenting
    │
    ├── 3. LLM调用 (server/llm.py)
    │      DeepSeek API (Function Calling)
    │      System prompt = SOUL + AGENTS + SKILL + 反幻觉规则
    │
    ├── 4. 工具执行 (server/tools.py)
    │      调 scripts/*.py
    │      调 mock_backend API
    │
    └── 5. SSE推送 (server/event_bus.py)
           实时推送: agent思考 → 工具调用 → 结果 → 回复
```

---

## 四、分阶段执行计划

### Phase 0: 清理 + Workspace + Mock ✅ 完成
**目标**: 搭建正确的OpenClaw工作区结构和Mock后端

- [x] 旧代码清理, 项目目录重定位
- [x] OpenClaw workspace 文件 (SOUL.md/AGENTS.md/USER.md/IDENTITY.md/MEMORY.md/HEARTBEAT.md/TOOLS.md/BOOTSTRAP.md)
- [x] 反幻觉规则 (anti_hallucination_prompt.md)
- [x] Mock 后端 (mock_data.py + event_engine.py)
- [x] 3个Skill的 SKILL.md + scripts (共8个脚本)

### Phase 1: Demo Server 骨架 ✅ 完成
**目标**: FastAPI 跑起来，加载workspace文件，能返回回复

- [x] `server/config.py` — 配置加载(.env + 路径)
- [x] `server/llm.py` — DeepSeek LLM客户端 (chat + chat_with_tools)
- [x] `server/prompts.py` — 从workspace文件加载prompt (SOUL + AGENTS + anti_hall + USER + skill summary)
- [x] `server/session.py` — 会话状态机 (意图路由 → 工具调用 → 二次LLM → 格式化回复)
- [x] `server/tools.py` — 工具执行器 (5个工具: search_restaurants/check_queue/plan_route/search_activities/get_weather)
- [x] `server/event_bus.py` — SSE事件推送 (thinking/tool_call/tool_result/reply/error)
- [x] `app.py` — FastAPI主入口 (Web UI + Chat API + SSE + Mock API内嵌 + Heartbeat API)
- [x] 系统提示词优化: 强制工具调用、默认area=望京、当前时间注入

**验证**: ✅ `python app.py` → 浏览器打开 → 发送"你好" → Agent回复

### Phase 2: Web UI (手机模拟器) ✅ 完成
**目标**: 手机模拟器界面 + 技术面板

- [x] `templates/index.html` — 手机壳 + 聊天界面 + 技术面板 (CSS全部内嵌)
- [x] 6个预设快捷按钮 (川菜/去798/周末活动/天气/火锅)
- [x] SSE实时接收 (技术面板展示Agent思考过程)
- [x] 消息渲染 (来源标签高亮 + markdown + 打字动画)
- [x] 来源标签样式 (.src-tag)

**验证**: ✅ UI美观，消息流畅，技术面板实时显示

### Phase 3: 三场景全链路打通 ✅ 完成
**目标**: 餐饮/出行/娱乐三个场景都能完整演示

- [x] 场景1 "我想吃火锅" → dining-advisor → search_restaurants → 2家餐厅 + 排队数据 + [美团]标签
- [x] 场景2 "从望京SOHO到798怎么走" → commute-planner → plan_route → 打车/单车/地铁对比 + [高德]标签
- [x] 场景3 "今天天气怎么样" → leisure-scout → get_weather → 温度/天气 + [天气网]标签
- [x] Agent回复中每条数据标注来源标签
- [x] DeepSeek Function Calling工作流验证: tool_call → execute → second LLM → reply

**验证**: ✅ 三个快捷按钮各点一次，完整走通

### Phase 4: 7x24 后台心跳 ✅ 完成
**目标**: 展示后台自主监控能力

- [x] 餐食时段检测 (7-9/11-13/17-19/21-23 自动触发)
- [x] 天气监测 (周末好天气 → 推荐活动)
- [x] 动态事件引擎 (满座/特价菜/排队变化/活动售罄)
- [x] SSE实时推送心跳事件
- [x] Heartbeat API (GET /api/heartbeat/status)

**验证**: ✅ 后台线程触发 → SSE推送至技术面板

### Phase 5: 打磨 + 测试 + 文档 ✅ 完成
**目标**: 提交就绪

- [x] 反幻觉提示词重写: 旅行领域 → 本地生活领域 (大众点评/美团/高德/猫眼/天气网)
- [x] `tests/test_mock_backend.py` — Mock API测试 (14项)
- [x] `tests/test_skills.py` — Skill脚本测试 (41项)
- [x] `tests/test_e2e.py` — 端到端测试 (76项)
- [x] 全量131项测试通过
- [x] Unicode编码问题修复 (Windows GBK → UTF-8)
- [x] System prompt优化 (强制工具调用 + 真实时间注入 + 缓存刷新)
- [x] `DEMO_SCRIPT.md` — 5分钟演示脚本 (Web UI版)
- [x] `README.md` — 安装+启动+架构+测试说明
- [x] 项目状态记忆更新
- [ ] `docs/architecture.png` — 架构图 (可选)
- [ ] 录制演示视频 (备选)

---

## 五、进度追踪

| Phase | 状态 | 内容 |
|-------|------|------|
| Phase 0: 清理+Workspace+Mock | ✅ | 旧代码清理, 8个工作区文件, 3个Skill, Mock后端 |
| Phase 1: Demo Server骨架 | ✅ | config/llm/prompts/session/tools/event_bus + app.py + 提示词优化 |
| Phase 2: Web UI | ✅ | 手机模拟器 + 6个预设按钮 + 技术面板SSE + 打字动画 |
| Phase 3: 三场景打通 | ✅ | 🍜火锅 🚗路线 🌤️天气 全链路LLM+工具调用+来源标注验证 |
| Phase 4: 7x24后台 | ✅ | 心跳线程(meal+weather双监控) + 事件引擎 + SSE实时推送 |
| Phase 5: 打磨+测试+文档 | ✅ | 131项测试 + 反幻觉重写 + Demo脚本 + README更新 |

---

## 六、测试总览

| 测试文件 | 数量 | 覆盖范围 |
|---------|------|---------|
| `test_mock_backend.py` | 14 | Health/Restaurant/Queue/Weather/Activity/Events API |
| `test_skills.py` | 41 | dining-advisor(18) + commute-planner(8) + leisure-scout(15) |
| `test_e2e.py` | 76 | Health/Config/Prompt/Session/Tools/EventBus/Heartbeat/SourceLabels |
| **总计** | **131** | **全部通过, 0失败** |

---

## 七、启动命令 (最终效果)

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 DeepSeek API Key
# 编辑 .env: DEEPSEEK_API_KEY=sk-xxxx

# 3. 一键启动 Demo Server
python app.py

# 4. 打开浏览器
# http://localhost:8010 → 手机模拟器UI
# http://localhost:8010/api/events → SSE技术面板
```

## 八、OpenClaw 兼容性说明

提交的 `openclaw-workspace/` 目录可直接用于 OpenClaw Gateway:

```bash
# 安装 OpenClaw
npm install -g openclaw@latest

# 复制工作区
cp -r openclaw-workspace/* ~/.openclaw/workspace/

# 启动
openclaw gateway --port 18789

# 打开 WebChat
openclaw dashboard
# → http://localhost:18789 → 和 Agent 对话
```

同一套 SOUL.md / SKILL.md / scripts 在两个轨道中都能工作。
