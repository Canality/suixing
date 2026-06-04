---
name: commute-planner
description: "出行管家：路径规划、打车预估、单车推荐、实时路况。触发词：去/路/打车/单车/骑行/通勤/怎么走/多远"
metadata:
  openclaw:
    emoji: "🚗"
    triggers:
      - "去|到|怎么去"
      - "打车|叫车"
      - "单车|骑行|骑车"
      - "通勤|上班|回家"
      - "路线|路况|多远"
---

# 出行管家

**触发条件**: 用户需要出行规划(路径/打车/单车/路况)

## 工作流

### 1. 路径规划
```
python skills/commute-planner/scripts/route_planner.py \
    --origin "望京SOHO" \
    --destination "798艺术区"
```
返回多条路线: 打车/地铁/单车, 含实时路况和预估价格。

### 2. 打车预估
```
python skills/commute-planner/scripts/ride_hailing.py \
    --origin "望京SOHO" \
    --destination "三里屯" \
    --mode 打车
```

### 3. 单车推荐
```
python skills/commute-planner/scripts/bike_routes.py \
    --area 望京 \
    --style commute  # commute | leisure
```

## 回复格式
使用飞书卡片(commute_card):
- 路线摘要(方式+时长+价格)
- 多个选项按时间排序
- 实时路况标识(畅通/正常/拥堵)
- 按钮: 开始导航 / 切换出行方式 / 查看单车站点

## 连锁动作(HEARTBEAT触发)
排队快到时 → 自动规划打车路线 → 推送"现在出发刚好"
