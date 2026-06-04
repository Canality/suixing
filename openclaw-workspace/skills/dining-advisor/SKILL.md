---
name: dining-advisor
description: "餐饮顾问：餐厅推荐、排队取号监控、外卖点单、群投票决策、拼单凑单。触发词：吃/饿/餐厅/外卖/火锅/川菜/排队/取号/拼单"
metadata:
  openclaw:
    emoji: "🍜"
    triggers:
      - "吃"
      - "饿"
      - "餐厅"
      - "外卖"
      - "火锅|川菜|日料|烤肉|涮肉|湘菜"
      - "排队"
      - "取号"
      - "拼单|凑单"
---

# 餐饮顾问

**触发条件**: 用户提到吃/饿/餐厅/外卖/排队/取号/拼单, 或到了餐食时段(由HEARTBEAT触发)

**加载完整指令**: 触发后立即 `Read skills/dining-advisor/SKILL.md` (本文件)

## 工作流

### 1. 餐厅搜索
用户表达"想吃什么"时:
```
python skills/dining-advisor/scripts/restaurant_search.py \
    --area <用户所在区域> \
    --cuisine <菜系> \
    --max-price <预算上限> \
    --meal-period <breakfast|lunch|dinner|latenight>
```
脚本调用 Mock API (http://localhost:8010/api/restaurants) 返回JSON结果。

### 2. 排队取号
用户选定餐厅后:
```
python skills/dining-advisor/scripts/queue_monitor.py \
    --action take \
    --restaurant-id <id>
```
持续监控:
```
python skills/dining-advisor/scripts/queue_monitor.py \
    --action check \
    --restaurant-id <id>
```

### 3. 群投票
多人决定去哪儿吃时:
```
python skills/dining-advisor/scripts/group_voting.py init \
    --options '[{"label":"火锅","emoji":"🍲"},{"label":"川菜","emoji":"🌶️"},{"label":"日料","emoji":"🍣"}]'
```

## 回复格式

推荐餐厅时使用飞书卡片(dining_card):
- 餐厅名 + 菜系 + 人均
- 评分 + 距离 + 排队状态
- 推荐菜
- 按钮: 取号排队 / 看看评价 / 换一批

排队提醒使用 queue_card:
- 当前排号 + 前面桌数 + 预计等待
- 进度条(视觉化)
- 按钮: 取消取号 / 查看路线

## 反幻觉规则
- 所有价格必须来自Mock API返回的数据
- 排队时间标注 [美团] 来源
- 如Mock API不可用,回复"抱歉，餐厅数据暂时无法获取，建议打开美团APP查看"
