# 随行 SuiXing — 本地生活 AI 管家

> 美团AI Hackathon 2026 | OpenClaw 赛道

## 一句话介绍

**不用在美团/大众点评/高德/猫眼之间来回切换。跟随行说句话，它帮你查天气、找餐厅、规划路线、推荐活动，7x24小时主动盯着变化，有情况立刻通知你。**

---

## 功能全景

| 模块 | 能力 | 数据来源 |
|------|------|---------|
| 🍜 美食管家 | 搜索餐厅、取号排队、口味匹配 | [美团] [大众点评] |
| 🚗 出行管家 | 路线规划、多方式对比、导航链接 | [高德] |
| 🎬 娱乐管家 | 活动搜索、电影票、展览票、骑行 | [猫眼] [大麦] |
| 🌤 天气监控 | 实时天气 + 分时段预报 | [天气网] |
| 🔔 主动通知 | 三级事件分类 + LLM自主判断推送 | — |
| 🧠 用户记忆 | 偏好/忌口/预算/住址持久化 | — |

## 架构亮点

- **7x24 后台运行**: 事件引擎每30秒更新沙盒状态，LLM 主动判断是否通知
- **三级事件系统**: 个人事务(一律提醒) / 环境变化(仅冲突时提醒) / 机遇事件(稀有度节流+6类开关)
- **跨域连锁沙盒**: 大型城市事件(马拉松/音乐节) + 记忆彩蛋
- **多源数据整合**: 一次对话查多个平台，标注来源
- **反幻觉**: 工具调用验证 + 来源标注 + 禁止编造

## 项目结构

```
meituan-travel-assistant/
├── app.py                  # FastAPI 入口
├── server/                 # 核心引擎
│   ├── session.py          # 会话管理 + ReAct循环
│   ├── llm.py              # DeepSeek API 封装
│   ├── prompts.py          # 三层Prompt架构
│   ├── proactive.py        # LLM主动通知引擎(三级分类)
│   ├── watchdog.py         # 条件监控引擎
│   ├── memory.py           # 用户画像持久化
│   ├── tools.py            # 工具执行器
│   └── opportunity_config.py  # 机遇事件开关
├── mock_backend/           # 动态沙盒
│   ├── mock_data.py        # 33+商户数据
│   ├── event_engine.py     # 状态变化引擎
│   ├── mega_events.py      # 大型城市事件(马拉松等)
│   └── life_events.py      # 生活事件 + 隐藏彩蛋
├── templates/index.html    # Web UI(手机模拟器+沙盒面板+技术面板)
├── tests/                  # 131项测试
└── ARCHITECTURE.md         # 技术架构文档
```

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 编辑填入 DEEPSEEK_API_KEY
python app.py          # → http://localhost:8010
```

## 文档索引

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构、数据流、设计决策 |
| [SANDBOX.md](SANDBOX.md) | 沙盒事件系统设计(三级分类+连锁+彩蛋) |
| [DEPLOY.md](DEPLOY.md) | 部署指南(Render/Railway) |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 演示脚本 |

## 测试

```bash
python tests/test_mock_backend.py  # 14 项
python tests/test_skills.py        # 41 项 (需server运行)
python tests/test_e2e.py           # 76 项 (需server运行)
```

---

*SuiXing v2.0 — Built for 美团 AI Hackathon 2026*
