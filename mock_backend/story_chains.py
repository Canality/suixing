"""剧情链事件 — 将离散事件串联成有因果关系的剧情。

当用户完成某个动作后，触发延时后续事件，制造戏剧冲突。

例如:
  吃火锅 → 30分钟后"工卡落下" → 回去路上"单车爆胎" → "15分钟后开会"
"""

import random
import time
from datetime import datetime


# ── 剧情链模板 ────────────────────────────────────────────

STORY_CHAINS = [
    {
        "id": "lost_badge",
        "trigger_on": "dining_completed",  # 在用户完成就餐后触发
        "title": "失物招领大冒险",
        "steps": [
            {"delay_sec": 60,  "msg": "📇 你刚才吃饭时工卡落在餐厅了！服务员刚发现"},
            {"delay_sec": 90,  "msg": "🚲 回餐厅的路上共享单车爆胎了，最近的还车点800米外"},
            {"delay_sec": 100, "msg": "⏰ 你15分钟后有个重要会议，时间非常紧张！"},
        ],
    },
    {
        "id": "surprise_date",
        "trigger_on": "weekend_plan_made",  # 周末计划确定后触发
        "title": "惊喜变惊吓",
        "steps": [
            {"delay_sec": 120, "msg": "💝 女朋友突然发消息说周末想和你一起去你之前提的那个地方"},
            {"delay_sec": 130, "msg": "😱 但你刚刚答应了朋友那天的饭局邀请..."},
            {"delay_sec": 150, "msg": "📱 朋友群开始讨论饭局细节了，两边都推不掉！"},
        ],
    },
    {
        "id": "boss_chain",
        "trigger_on": "boss_overtime",
        "title": "连环加班灾难",
        "steps": [
            {"delay_sec": 30,  "msg": "📊 老板追加需求：隔壁组也缺人，需要你们组支援"},
            {"delay_sec": 45,  "msg": "🍕 公司订了加班餐，但是人均只有¥30预算"},
            {"delay_sec": 60,  "msg": "😤 同事群里开始吐槽，有人提议一起辞职..."},
        ],
    },
    {
        "id": "weather_trap",
        "trigger_on": "outdoor_plan_confirmed",
        "title": "天气陷阱",
        "steps": [
            {"delay_sec": 90,  "msg": "⛅ 天气突变！原来预告的晴天变成了雷阵雨"},
            {"delay_sec": 100, "msg": "💨 风力加大到5级，户外活动基本不可能了"},
            {"delay_sec": 120, "msg": "🎬 附近的电影院刚好放出下午场特价票"},
        ],
    },
]

# ── 触发匹配 ──────────────────────────────────────────────

def match_chain(trigger_type: str, user_message: str = "") -> dict | None:
    """检查是否有匹配的剧情链。"""
    for chain in STORY_CHAINS:
        if chain["trigger_on"] == trigger_type:
            return chain
    return None


def get_chain_steps(chain: dict) -> list:
    """返回剧情链的所有步骤(按delay_sec排序)。"""
    return sorted(chain["steps"], key=lambda s: s["delay_sec"])


# ── 运行时管理 ────────────────────────────────────────────

_pending_steps: list[dict] = []  # 待触发的步骤 {trigger_at, msg, chain_id}


def schedule_chain(trigger_type: str, add_event_callback) -> bool:
    """触发一个剧情链。返回是否成功。"""
    chain = match_chain(trigger_type)
    if not chain:
        return False

    now = time.time()
    steps = get_chain_steps(chain)
    for step in steps:
        _pending_steps.append({
            "trigger_at": now + step["delay_sec"],
            "msg": step["msg"],
            "chain_id": chain["id"],
        })

    add_event_callback("story_chain_start", chain["id"],
                       f"📜 剧情触发: {chain['title']}")
    return True


def process_chains(add_event_callback) -> list:
    """处理到期的剧情链步骤。"""
    global _pending_steps
    now = time.time()
    triggered = []
    remaining = []

    for step in _pending_steps:
        if now >= step["trigger_at"]:
            add_event_callback("story_chain_step", step["chain_id"], step["msg"])
            triggered.append(step)
        else:
            remaining.append(step)

    _pending_steps = remaining
    return triggered
