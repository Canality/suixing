"""大型城市事件 — 跨域连锁反应。

马拉松/音乐节等大型活动触发后，自动产生:
- 交通域连锁: 封路 → 网约车不可用 → 单车站满员
- 餐饮域连锁: 外卖延时 → 餐厅爆满
- 机遇域连锁: 景观位/观赛特餐放出
"""

import random
from datetime import datetime

# ── 事件模板 ──────────────────────────────────────────────

MEGA_EVENT_TEMPLATES = [
    {
        "name": "望京半程马拉松",
        "trigger_msg": "🏃 望京区域正在举办半程马拉松！预计持续3小时",
        "chains": [
            # 交通域 (立即)
            {"delay": 0, "msg": "🚗 马拉松封路中，望京区域网约车暂停服务，建议骑车或地铁出行"},
            {"delay": 0, "msg": "🚲 马拉松沿线共享单车站被跑者占用，基本无车可用"},
            {"delay": 0, "msg": "🚇 地铁望京站客流激增，但不受封路影响可正常通行"},
            # 餐饮域 (立即)
            {"delay": 0, "msg": "🍜 外卖骑手无法进入赛道区域，配送预计延时60分钟"},
            {"delay": 0, "msg": "🔥 赛事沿线观赛人群涌入，附近餐厅排队人数翻倍"},
            # 机遇域 (2 tick后)
            {"delay": 2, "msg": "🍲 后院·川渝火锅推出「跑者补给套餐」限时8折"},
            {"delay": 2, "msg": "☕ 望京SOHO天台观赛位开放，可俯瞰赛道全程"},
        ],
    },
    {
        "name": "798艺术区户外音乐节",
        "trigger_msg": "🎵 798艺术区正在举办户外电子音乐节！",
        "chains": [
            {"delay": 0, "msg": "🚗 798周边道路管制，打车需绕行预计多花20分钟"},
            {"delay": 0, "msg": "🎨 UCCA艺术展因音乐节人流过多，排队入场需40分钟"},
            {"delay": 0, "msg": "🚲 798周边共享单车被音乐节观众骑光"},
            {"delay": 2, "msg": "🎫 音乐节临时放出少量半价票(仅限App内购买)"},
            {"delay": 2, "msg": "🍻 颐堤港精酿啤酒花园推出音乐节特供套餐"},
        ],
    },
    {
        "name": "美团骑士节大促",
        "trigger_msg": "🎉 美团骑士节！全城外卖配送费全免，限时2小时",
        "chains": [
            {"delay": 0, "msg": "🆓 外卖配送费全免！最低0元起送"},
            {"delay": 0, "msg": "🔥 热门餐厅外卖订单暴增，预计出餐延时30分钟"},
            {"delay": 1, "msg": "📊 麻辣诱惑(望京凯德MALL)推出骑士节特价套餐¥39.9"},
            {"delay": 1, "msg": "🎬 万达影城(望京店)骑士节爆米花套餐买一送一"},
        ],
    },
]

# ── 状态管理 ──────────────────────────────────────────────

_active_mega: dict | None = None  # 当前进行中的大型事件
_mega_tick: int = 0               # 已持续tick数
_cooldown: int = 0                # 冷却tick数(一次大事件后等一段时间)


def tick_mega_events(add_event_callback) -> list:
    """每tick检查: 是否触发新的大型事件 / 推进已有事件的连锁。

    触发条件: 没有活跃事件 + 冷却结束 + 10%概率
    """
    global _active_mega, _mega_tick, _cooldown

    results = []

    if _active_mega is not None:
        # 已有活跃事件 → 推进连锁
        _mega_tick += 1
        for chain in _active_mega.get("chains", []):
            if chain["delay"] == _mega_tick:
                add_event_callback("mega_chain", "mega", chain["msg"])
                results.append(chain["msg"])

        # 事件结束(5 tick后)
        if _mega_tick >= 5:
            add_event_callback("mega_end", "mega",
                               f"✅ {_active_mega['name']}已结束，城市恢复正常")
            _active_mega = None
            _cooldown = 8  # 冷却8个tick
        return results

    # 冷却中
    if _cooldown > 0:
        _cooldown -= 1
        return results

    # 10%概率触发新事件
    if random.random() < 0.10:
        _active_mega = random.choice(MEGA_EVENT_TEMPLATES)
        _mega_tick = 0
        add_event_callback("mega_start", "mega", _active_mega["trigger_msg"])
        results.append(_active_mega["trigger_msg"])

        # 立即触发 delay=0 的连锁
        for chain in _active_mega.get("chains", []):
            if chain["delay"] == 0:
                add_event_callback("mega_chain", "mega", chain["msg"])
                results.append(chain["msg"])

    return results


def is_mega_active() -> bool:
    return _active_mega is not None


def get_active_mega() -> dict | None:
    return _active_mega
