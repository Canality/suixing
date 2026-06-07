# 测试套件总览

> 随行 SuiXing — 全部 153 项测试，0 失败

---

## 测试总览

| 文件 | 数量 | 类型 | 依赖 |
|------|------|------|------|
| `test_memory.py` | 22 | 单元测试 | 无 (纯 Python) |
| `test_mock_backend.py` | 14 | 集成测试 | Server 运行在 localhost:8010 |
| `test_skills.py` | 41 | 集成测试 | Server 运行在 localhost:8010 |
| `test_e2e.py` | 76 | 端到端测试 | Server 运行在 localhost:8010 |
| **总计** | **153** | | |

---

## 各文件详细覆盖

### test_memory.py (25 项) — 用户记忆系统

| 模块 | 数量 | 测什么 |
|------|------|--------|
| Profile 读写 | 7 | load_profile 返回结构、food/residence/transport/weather/entertainment 域完整性 |
| remember 追加型 | 4 | cuisines_liked 追加合并、wishlist 追加、重复值去重 |
| remember 覆盖型 | 4 | name/home/work/budget 字段覆盖 |
| Layer 2 摘要 | 5 | get_summary 包含用户名/位置/口味/预算 |
| Layer 3 查询 | 3 | get_detail 查询餐厅/愿望单/预算 |
| 缓存 TTL | 1 | 摘要缓存过期逻辑 |
| 每日日志 | 1 | 日志写入 memory/YYYY-MM-DD.md |

### test_mock_backend.py (14 项) — Mock API

| 模块 | 数量 | 测什么 |
|------|------|--------|
| Health | 1 | `/api/health` 返回 ok |
| Restaurant | 4 | 搜索返回结果、字段完整性、动态排队状态、match_score 排序 |
| Detail | 2 | 餐厅详情 + 动态状态 |
| Queue | 1 | 排队状态查询 |
| Weather | 3 | 温度、天气状况、活动建议 |
| Activities | 2 | 分类搜索、动态状态 |
| Events | 1 | 随机事件返回 |

### test_skills.py (41 项) — Skill 脚本

| Skill | 数量 | 测什么 |
|-------|------|--------|
| dining-advisor | 18 | restaurant_search: 正常搜索/空结果/标签搜索/字段校验/来源标签/排序 |
| | | queue_monitor: 排队查询/取号/无需排队 |
| commute-planner | 8 | route_planner: 字段校验/最快最便宜/来源标签/排序 |
| leisure-scout | 15 | weather_fetcher: 基础/活动提示/字段校验 |
| | | activity_scraper: 分类过滤/售罄排序/来源标签 |

### test_e2e.py (76 项) — 端到端

| 模块 | 数量 | 测什么 |
|------|------|--------|
| Health | 5 | 健康检查 + 系统信息 + Skill 列表 |
| Config | 15 | API Key 配置/路径/工作区文件(SOUL/AGENTS/anti_hallucination/USER/SKILL.md)/脚本目录 |
| Prompt | 7 | System prompt 内容/长度/包含关键元素(SuiXing/反幻觉/Skill/来源标签) |
| Session | 9 | 创建/获取/区分/回退回复 |
| Tools | 14 | 全部 9 个工具存在 + search_restaurants/check_queue/plan_route/search_activities/get_weather 执行 + 未知工具报错 + create_watch/remember/get_user_profile |
| Event Bus | 8 | 订阅/发送/事件类型/时间戳/取消订阅 |
| Heartbeat | 5 | 字段完整性 |
| Session Reset | 2 | 重置成功 |
| Source Labels | 3 | 天气 API 包含 source_label |

---

## 运行测试

### 快速运行

```bash
# 终端 1: 启动 Server
python app.py

# 终端 2: 依次运行
python tests/test_memory.py
python tests/test_mock_backend.py
python tests/test_skills.py
python tests/test_e2e.py
```

### 一键运行全部 (PowerShell)

```powershell
python app.py;        # 先启动 Server
python tests/test_memory.py;
python tests/test_mock_backend.py;
python tests/test_skills.py;
python tests/test_e2e.py
```

### 一键运行全部 (Bash)

```bash
python tests/test_memory.py && \
python tests/test_mock_backend.py && \
python tests/test_skills.py && \
python tests/test_e2e.py
```

---

## 测试结果示例

```
Mock Backend 测试: 14 通过, 0 失败
Skill 脚本测试:   41 通过, 0 失败
Memory 测试:      25 通过, 0 失败
端到端测试:       76 通过, 0 失败
─────────────────────────────
总计:            153 通过, 0 失败 ✅
```
