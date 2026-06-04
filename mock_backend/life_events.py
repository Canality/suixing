"""个人生活事件生成器 — 模拟真实世界的冲突与机会。

事件引擎每次 tick 有概率触发一个生活事件。事件本身不绑定具体 entity，
LLM 收到事件后自主判断: 是否与用户画像/当前计划/wishlist 冲突？该如何应对？

设计原则:
- 制造冲突 → LLM 帮用户做抉择（DDL vs 骑行、预算 vs 美食）
- 制造机会 → LLM 帮用户抓窗口（限时优惠、突然空位）
- 制造故事 → 跨域联动（暴雨 → 外卖 + 室内活动）
"""

import random
from datetime import datetime

# ── 事件模板池 ────────────────────────────────────────────────
# msg 字段: LLM 看到的事件描述
# urgency: high=必须立刻处理, medium=值得关注, low=可选
# domain: 关联的 Skill 域
# hook: 建议 LLM 考虑的联动方向

LIFE_EVENT_POOL = [
    # ═══ 工作域 ═══
    {
        "type": "work_deadline",
        "msg": "明天下午有个项目DDL，看进度还差不少",
        "urgency": "high",
        "domain": "general",
        "hook": "冲突检测: 如果用户有计划中的户外/社交活动 → 建议调整时间",
    },
    {
        "type": "work_meeting",
        "msg": "明天临时加了个午餐评审会(12:00-13:30)",
        "urgency": "medium",
        "domain": "general",
        "hook": "午饭时间被占 → 建议提前叫外卖 or 会后推荐附近快餐",
    },
    {
        "type": "work_overtime",
        "msg": "老板刚说今晚可能要加班到21:00",
        "urgency": "high",
        "domain": "general",
        "hook": "如果用户有晚餐/电影计划 → 建议取消or推迟 + 推荐加班夜宵",
    },

    # ═══ 社交域 ═══
    {
        "type": "social_invite",
        "msg": "饭搭子群里在讨论今晚聚餐，有人提议去吃烤肉",
        "urgency": "medium",
        "domain": "dining",
        "hook": "匹配用户口味偏好 → 推荐餐厅 + 对比排队 + 规划路线",
    },
    {
        "type": "social_birthday",
        "msg": "后天是女朋友生日，还没想好送什么",
        "urgency": "high",
        "domain": "entertainment",
        "hook": "推荐浪漫晚餐(结合用户预算) + 查附近电影院/展览 + 订位",
    },
    {
        "type": "social_group_ride",
        "msg": "骑行群里在组织周末温榆河骑行，刚好缺一个人",
        "urgency": "medium",
        "domain": "leisure",
        "hook": "用户喜欢骑行 → 检查天气 → 天气好直接加入 / 天气差创建monitor",
    },

    # ═══ 财务域 ═══
    {
        "type": "budget_warning",
        "msg": "这个月餐饮预算还剩¥200(已经25号了)",
        "urgency": "medium",
        "domain": "dining",
        "hook": "后续餐厅推荐自动过滤高价 → 推荐性价比餐厅 → 关注优惠",
    },
    {
        "type": "coupon_expiring",
        "msg": "美团外卖满50-20的券明天就过期了",
        "urgency": "low",
        "domain": "dining",
        "hook": "提醒用户用券 → 结合用户口味推荐外卖",
    },
    {
        "type": "member_expiring",
        "msg": "大众点评黑卡会员月底到期，还有2张免排队券没用",
        "urgency": "low",
        "domain": "dining",
        "hook": "用户喜欢吃火锅/川菜 → 推荐用券的热门餐厅",
    },

    # ═══ 健康域 ═══
    {
        "type": "health_steps",
        "msg": "今天步数才3000，日常目标10000还差很远",
        "urgency": "low",
        "domain": "leisure",
        "hook": "建议下班步行 or 骑行 → 结合天气推荐路线",
    },
    {
        "type": "health_takeout",
        "msg": "这周已经连续5天外卖了，有点不太健康",
        "urgency": "low",
        "domain": "dining",
        "hook": "推荐到店吃 → 查附近评分高+不用排队的餐厅",
    },

    # ═══ 机会域 (限时窗口 — 制造戏剧性) ═══
    {
        "type": "flash_table",
        "msg": "后院·川渝火锅突然放出一张今晚7点的空桌(可能是有人取消)",
        "urgency": "high",
        "domain": "dining",
        "hook": "用户喜欢火锅且上次去过 → 限时机会 → 快速决策: 叫车+订位",
    },
    {
        "type": "flash_discount",
        "msg": "密室逃脱·长安十二时辰今晚场次限时6折(原价¥168→¥101)",
        "urgency": "high",
        "domain": "entertainment",
        "hook": "用户喜欢聚会 → 结合社交人数推荐 → 查是否还有票",
    },
    {
        "type": "last_chance",
        "msg": "望京SOHO天台市集今天是最后一天",
        "urgency": "medium",
        "domain": "leisure",
        "hook": "用户喜欢探索新餐厅/逛市集 → 结合天气推荐 → 时间窗口紧迫",
    },
    {
        "type": "ticket_released_vip",
        "msg": "《流浪地球3》IMAX今晚19:30场有人退了一张中间座位",
        "urgency": "high",
        "domain": "entertainment",
        "hook": "用户喜欢科幻 → 火爆场次有退票 → 要不要锁定？",
    },

    # ═══ 紧急个人事务 ═══
    {
        "type": "girlfriend_sick",
        "msg": "女朋友发消息说不舒服，好像发烧了",
        "urgency": "high",
        "domain": "general",
        "hook": "紧急 → 取消计划 + 查药店 + 推荐清淡外卖",
    },
    {
        "type": "parents_miss",
        "msg": "妈妈发消息说想你了，问你这周回不回家吃饭",
        "urgency": "medium",
        "domain": "general",
        "hook": "如果周末有安排 → 提醒留时间回家",
    },
    {
        "type": "boss_trip",
        "msg": "老板说明天临时出差，让你今晚加班准备材料",
        "urgency": "high",
        "domain": "general",
        "hook": "今晚有安排 → 冲突 + 推荐加班夜宵",
    },

    # ═══ 天气相关生活事件 ═══
    {
        "type": "rain_surge",
        "msg": "望京区域突降暴雨，网约车价格翻倍了",
        "urgency": "high",
        "domain": "transport",
        "hook": "用户可能要出行 → 对比地铁/等雨小 → 推荐外卖+室内活动",
    },
    {
        "type": "heat_wave",
        "msg": "今天体感温度38°C，户外活动不太安全",
        "urgency": "high",
        "domain": "leisure",
        "hook": "用户怕热 → 推荐室内商场/电影院/密室 → 推迟户外计划",
    },
]


def tick_life_events(events_log_callback) -> list:
    """执行一次生活事件 tick。15%概率触发一个随机事件。

    events_log_callback(type, entity_id, message) — 事件记录回调。
    """
    if random.random() > 0.25:
        return []

    event = random.choice(LIFE_EVENT_POOL)
    events_log_callback(
        event_type=f"life_{event['type']}",
        entity_id="life",
        message=event["msg"],
    )
    return [event]


def get_life_events_by_domain(domain: str) -> list:
    """按域筛选事件模板（供 LLM 按需查询）。"""
    return [e for e in LIFE_EVENT_POOL if e["domain"] == domain]
