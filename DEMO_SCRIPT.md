# Demo 脚本 — 随行 SuiXing 本地生活管家

## Demo 信息
- **作品**: 随行 SuiXing
- **赛道**: OpenClaw 本地生活"全天候私人管家"
- **时长**: 5分钟
- **启动**: `python app.py` → http://localhost:8010

---

## 演示流程

### 0:00-0:30 | 开场 (展示Web UI)
打开浏览器 → 展示手机模拟器界面:
- 左侧: 手机壳 + 聊天界面 + 快捷按钮
- 右侧: SSE 技术面板 (实时Agent思考过程)

> "SuiXing 是一个基于 OpenClaw 的本地生活管家。用户通过手机聊天，Agent 7x24小时后台运行，主动感知需求。"

### 0:30-1:30 | 场景1: 餐饮推荐 (dining-advisor)
点击快捷按钮"🍲 火锅" 或输入"帮我推荐火锅，要排队少的":
- 技术面板显示: thinking → tool_call: search_restaurants → tool_result → reply
- Agent回复: 展示2家火锅店 + 实时排队数据 + [美团]来源标签
- 聊天界面展示: 海底捞(排队1桌) vs 后院火锅(排队15桌)

> "Agent自动调用了 search_restaurants 工具，获取Mock API返回的动态数据，每条数据标注了来源."

### 1:30-2:30 | 场景2: 出行规划 (commute-planner)
点击快捷按钮"🚗 去798" 或输入"从望京SOHO到798怎么走":
- 技术面板显示: plan_route tool call
- Agent回复: 打车/单车/地铁 三方案对比 + [高德]标签
- 展示实时路况 + 价格估算

> "commute-planner 调用高德路线API，返回3种出行方式的时长和价格对比."

### 2:30-3:30 | 场景3: 周末活动 (leisure-scout)
点击快捷按钮"🎬 周末活动" 或输入"周末有什么好玩的":
- 技术面板显示: get_weather + search_activities 双工具调用
- Agent回复: 天气信息 + 活动推荐 + [天气网][猫眼]标签
- 展示: 电影排片 + 展览 + 骑行路线

> "leisure-scout 同时查询天气和活动，根据天气条件自动推荐室内/室外活动."

### 3:30-4:30 | 7x24 后台心跳演示
展示右侧技术面板的 heartbeat 事件:
- 整点餐食提醒: "⏰ 晚餐时间到！可触发 dining-advisor"
- 周末天气监测: "周末好天气！可触发 leisure-scout"
- 动态事件: 餐厅排队变化/特价菜/满座提醒

> "3个后台线程持续监控: 餐食时段触发、天气每小时更新、排队状态每30秒刷新."

### 4:30-5:00 | 架构总结
切换到代码视图:
> "3个核心技术亮点:"
> "1. OpenClaw原生工作区: SOUL.md + SKILL.md + HEARTBEAT.md"
> "2. DeepSeek Function Calling: 工具调用 → Mock API → 数据格式化 → 来源标注"
> "3. 动态Mock沙盒: 12餐厅+8活动+随机事件引擎，非静态JSON"
> "4. 131项自动化测试: Mock API 14 + Skill 41 + E2E 76"

---

## 演示检查清单

- [ ] `python app.py` 启动成功
- [ ] 浏览器打开 http://localhost:8010
- [ ] 手机模拟器界面正常
- [ ] SSE技术面板有事件流
- [ ] 4个快捷按钮各点一次，完整走通
- [ ] 技术面板显示 tool_call → tool_result → reply 流程
- [ ] 回复中包含来源标签 ([美团][高德][天气网])
- [ ] http://localhost:8010/api/health 返回 ok

## 预设快捷按钮

| 按钮 | 触发Skill | 预期行为 |
|------|----------|---------|
| 🍜 想吃川菜 | dining-advisor | 搜索望京川菜 → 返回餐厅列表 |
| 🚗 去798 | commute-planner | 规划路线 → 3种方式对比 |
| 🎬 周末活动 | leisure-scout | 查天气+活动 → 推荐方案 |
| 🌤️ 查天气 | leisure-scout | 天气数据 + 活动建议 |
| 🍲 火锅 | dining-advisor | 搜索火锅 → 对比排队情况 |

## 兜底方案

- **LLM不可用**: Agent自动使用回退回复 (启发式匹配)
- **Mock API异常**: 脚本超时30s自动返回错误
- **网络问题**: 前端显示"网络错误"提示
