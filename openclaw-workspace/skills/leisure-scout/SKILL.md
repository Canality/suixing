---
name: leisure-scout
description: "娱乐向导：天气查询、活动推荐、电影演出、优惠发现、周末去处。触发词：玩/无聊/天气/活动/电影/周末/展览/演出/骑行/运动"
metadata:
  openclaw:
    emoji: "🎬"
    triggers:
      - "玩|无聊|干嘛"
      - "天气|下雨|热|冷"
      - "电影|演出|展览|活动|周末"
      - "骑行|运动|密室|脱口秀"
      - "优惠|特价|打折"
---

# 娱乐向导

**触发条件**: 用户问天气/活动/电影/周末安排, 或HEARTBEAT天气监控触发

## 工作流

### 1. 天气查询
```
python skills/leisure-scout/scripts/weather_fetcher.py
```
返回当前天气 + 活动建议。

### 2. 活动搜索
```
python skills/leisure-scout/scripts/activity_scraper.py \
    --category <电影|展览|户外|运动|演出|市集|密室> \
    --area <区域> \
    --max-price <上限>
```

### 3. 凑单优化(活动优惠)
```
python skills/leisure-scout/scripts/upsell_engine.py \
    --spend <当前消费> \
    --category activity
```

## 天气→活动映射
| 天气 | 推荐活动 |
|------|---------|
| 晴/多云, 20-28°C | 户外骑行、公园、市集、露天电影 |
| 晴, >32°C | 室内商场、电影院、密室逃脱 |
| 雨 | 电影院、展览、脱口秀、火锅(联动dining) |
| 霾(AQI>100) | 室内活动, 提醒戴口罩 |
| 周末+好天气 | 温榆河骑行、798展览、望京市集 |

## 回复格式
使用飞书卡片(leisure_card):
- 天气摘要 + 活动建议
- 活动列表(名称+价格+距离+评分)
- 活动状态(可订/售罄)
- 按钮: 查看详情 / 购票(模拟) / 分享给朋友

## 连锁动作
周末好天气 → 推荐户外活动 → 检查单车可用性 → 推送路线
