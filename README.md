# 随行 SuiXing — 基于 OpenClaw 的本地生活"全天候私人管家"

> 美团AI Hackathon 2026 | OpenClaw 赛道 | 提交作品

## 项目简介

**SuiXing(随行)** 是一个基于 OpenClaw 框架的本地生活 AI 管家。用户通过手机Web UI与管家交互，Agent 7x24小时后台运行，主动感知用户需求 — 餐食时段推荐餐厅、排队快到时提醒出发、周末好天气建议户外活动。

### 核心特点

1. **双轨架构**: Demo Server (一键启动Web演示) + OpenClaw Workspace (证明框架兼容)
2. **主动感知**: 心跳机制 + 餐食/天气双线程监控 → 管家式主动服务
3. **反幻觉体系**: 来源标注 + 工具调用验证 + 动态Mock数据
4. **三场景全链路**: 餐饮推荐+排队 → 出行规划 → 天气+活动推荐

## 快速开始

### 一键启动 Demo

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 DeepSeek API Key
# 编辑 .env 文件: DEEPSEEK_API_KEY=sk-xxxx

# 3. 启动 Demo Server
python app.py

# 4. 打开浏览器
# http://localhost:8010 → 手机模拟器UI
# http://localhost:8010/api/events → SSE 技术面板
```

### Demo 手机模拟器

Web UI 包含:
- 手机壳模拟界面，6个预设场景按钮
- 实时对话 + 打字动画
- 右侧SSE技术面板: Agent思考 → 工具调用 → 结果 → 回复
- 一键测试: 火锅推荐/去798/周末活动/查天气

## 项目结构

```
meituan-travel-assistant/
├── app.py                        # Demo Server 入口 (一键启动)
├── server/                       # Demo Server 核心
│   ├── config.py                 # 配置加载 + 环境变量
│   ├── session.py                # 会话状态机 + Agent逻辑
│   ├── llm.py                    # LLM客户端 (DeepSeek)
│   ├── prompts.py                # Prompt模板 (从workspace加载)
│   ├── tools.py                  # 工具执行器 (调scripts)
│   └── event_bus.py              # SSE事件推送
├── templates/
│   └── index.html                # Web UI (手机模拟器 + 技术面板)
├── openclaw-workspace/           # OpenClaw 工作区
│   ├── SOUL.md                   # 管家人设
│   ├── AGENTS.md                 # 行为规则+工作流
│   ├── USER.md                   # 用户画像
│   ├── HEARTBEAT.md              # 7x24后台任务
│   ├── anti_hallucination_prompt.md  # 反幻觉规则
│   ├── memory/                   # 每日记忆日志
│   └── skills/
│       ├── dining-advisor/       # 🍜 餐饮顾问
│       ├── commute-planner/      # 🚗 出行管家
│       └── leisure-scout/        # 🎬 娱乐向导
├── mock_backend/                 # 动态模拟数据
│   ├── mock_data.py              # 12餐厅+8活动+天气+路线+单车
│   └── event_engine.py           # 随机事件引擎
├── shared-scripts/               # 共享工具脚本
│   ├── heartbeat_runner.py       # 7x24监控执行器
│   ├── feishu_bot.py             # 飞书卡片推送
│   └── coupons.json              # 优惠券数据
├── tests/                        # 测试 (131项)
│   ├── test_mock_backend.py      # Mock API 测试 (14项)
│   ├── test_skills.py            # Skill脚本测试 (41项)
│   └── test_e2e.py               # 端到端测试 (76项)
├── DEMO_SCRIPT.md                # 5分钟演示脚本
├── PROJECT_PLAN.md               # 开发计划
└── requirements.txt
```

## 三个核心 Skill

| Skill | 功能 | 工具 |
|-------|------|------|
| **dining-advisor** | 餐厅搜索、排队取号、排队监控 | search_restaurants, check_queue |
| **commute-planner** | 路径规划、打车预估、单车推荐 | plan_route |
| **leisure-scout** | 天气查询、活动推荐、电影演出 | get_weather, search_activities |

## 7x24 后台心跳

1. **餐食监控**: 7:00/11:30/17:30/21:00 触发 → SSE推送提醒
2. **天气监控**: 每天检查 → 周末好天气推荐户外活动
3. **动态事件**: 每30秒更新餐厅排队/活动状态/单车数量

## 测试

```bash
# Mock API 测试 (需先启动server)
python tests/test_mock_backend.py

# Skill脚本测试
python tests/test_skills.py

# 端到端测试
python tests/test_e2e.py

# 全量: 14 + 41 + 76 = 131 tests
```

## OpenClaw 兼容

`openclaw-workspace/` 目录可直接用于 OpenClaw Gateway:

```bash
cp -r openclaw-workspace/* ~/.openclaw/workspace/
openclaw gateway --port 18789
```

## 提交信息

- **赛道**: 命题赛道 1 — 基于OpenClaw的本地生活"全天候私人管家"
- **作品名称**: 随行 SuiXing
- **版本**: v2.0.0
- **提交截止**: 2026-06-07
