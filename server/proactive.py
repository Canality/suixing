"""LLM驱动的主动通知引擎 — 三级事件分类 + 智能推送。

事件分类:
  1. 个人事务 (personal)  — 老板加班/女友生病/父母想念 → 一律提醒
  2. 环境变化 (environmental) — 天气/场馆/单车 → 只在与用户计划冲突时提醒
  3. 机遇事件 (opportunity) — 退票/特价/空桌 → 按稀有度节流推送

RarityTracker: 机遇事件频次控制
  urgent → 每次都推   rare → 每3次推1次   common → 每5次推1次
"""

import json
import sys
import time
import threading
from datetime import datetime
from server.llm import chat
from server.memory import memory
from mock_backend.event_engine import get_recent_events


# ── 事件分类表 ──────────────────────────────────────────

EVENT_CATEGORIES: dict[str, tuple[str, str]] = {
    # === 个人事务 (personal, rarity) ===
    "life_work_deadline":      ("personal", "urgent"),
    "life_work_overtime":      ("personal", "urgent"),
    "life_work_meeting":       ("personal", "high"),
    "life_social_birthday":    ("personal", "urgent"),
    "life_social_invite":      ("personal", "high"),
    "life_girlfriend_sick":    ("personal", "urgent"),
    "life_parents_miss":       ("personal", "urgent"),
    "life_boss_trip":          ("personal", "urgent"),
    "life_health_steps":       ("personal", "low"),
    "life_health_takeout":     ("personal", "low"),
    "life_budget_warning":     ("personal", "medium"),
    "life_rain_surge":         ("personal", "urgent"),
    "life_heat_wave":          ("personal", "urgent"),

    # === 环境变化 (environmental, _) ===
    "weather_changed":         ("environmental", ""),
    "forecast_change":         ("environmental", ""),
    "venue_closed":            ("environmental", ""),
    "venue_disrupted":         ("environmental", ""),
    "venue_recovered":         ("environmental", ""),
    "restaurant_closed":       ("environmental", ""),
    "temporary_closed":        ("environmental", ""),
    "restaurant_full":         ("environmental", ""),
    "bikes_empty":             ("environmental", ""),

    # === 机遇事件 (opportunity, rarity) ===
    "life_flash_table":        ("opportunity", "urgent"),
    "life_flash_discount":     ("opportunity", "rare"),
    "life_ticket_released_vip":("opportunity", "urgent"),
    "life_last_chance":        ("opportunity", "rare"),
    "life_coupon_expiring":    ("opportunity", "common"),
    "life_member_expiring":    ("opportunity", "common"),
    "life_social_group_ride":  ("opportunity", "rare"),
    "ticket_released":         ("opportunity", "rare"),
    "table_opened":            ("opportunity", "common"),
    "daily_special":           ("opportunity", "common"),
    "restaurant_reopened":     ("opportunity", "rare"),
    "ticket_available":        ("opportunity", "urgent"),
}


class RarityTracker:
    """机遇事件频次控制: urgent=每次, rare=每3次, common=每5次."""

    def __init__(self):
        self._counts: dict[str, int] = {}

    def should_notify(self, event_type: str, rarity: str) -> bool:
        if rarity == "urgent":
            return True
        if rarity == "high":
            return True
        if rarity == "medium":
            self._counts[event_type] = self._counts.get(event_type, 0) + 1
            return self._counts[event_type] % 2 == 0
        if rarity == "rare":
            self._counts[event_type] = self._counts.get(event_type, 0) + 1
            return self._counts[event_type] % 3 == 0
        if rarity == "common":
            self._counts[event_type] = self._counts.get(event_type, 0) + 1
            return self._counts[event_type] % 5 == 0
        return True


# ── 轻量会话上下文 ──────────────────────────────────────

_last_context: str = ""
_context_lock = threading.Lock()


def update_context(user_msg: str, reply_summary: str):
    global _last_context
    with _context_lock:
        t = datetime.now().strftime("%H:%M")
        _last_context = f"[{t}] 用户: {user_msg[:120]}\n[{t}] 助手: {reply_summary[:120]}"


def _get_context() -> str:
    with _context_lock:
        return _last_context


# ── Prompt 构建 ──────────────────────────────────────────

def _build_proactive_prompt(
    profile_text: str,
    personal_events: list,
    env_events: list,
    opp_events: list,
    context: str,
    last_notify: str,
) -> str:

    def _fmt(events):
        if not events:
            return "(无)"
        lines = []
        for e in events[-6:]:
            t = e.get("time", "")
            if isinstance(t, str) and len(t) >= 16:
                t = t[11:16]
            else:
                t = ""
            lines.append(f"- [{t}] {e.get('message', '')}")
        return "\n".join(lines)

    return f"""你是随行的主动通知大脑。按分类有不同处理规则。

## 用户画像
{profile_text}

## 最近对话（注意区分"LLM建议的选项"和"用户确认的计划"）
{context or "(暂无)"}

## 🔴 个人紧急事务 (必须提醒)
{_fmt(personal_events)}

## 🟡 环境变化 (仅在用户已确认具体计划时才提醒)
{_fmt(env_events)}

## 🟢 机遇事件 (已按稀有度过滤)
{_fmt(opp_events)}

## 通知规则（严格）

### 个人事务 — 一律提醒
- 所有个人事务事件都必须通知用户，不分优先级
- 加班/生病/家人/步数/外卖/预算 → 一律 NOTIFY

### 环境变化 — 红线
- **用户必须明确说了具体地点+时间才算"有计划"**
  - "我要去温榆河" ❌ 不够具体
  - "周六下午4点去温榆河骑行" ✅ 有具体计划
  - LLM建议/推荐的选项 ❌ 不算计划
  - 用户说"好无聊有什么推荐" ❌ 不算计划
- 即使用户有偏好(骑行/电影)，没确认具体计划 → SILENT
- 场馆关闭/单车骑光/天气变化 → 只在与已确认计划冲突时提醒

### 机遇事件
- urgent → NOTIFY
- rare/common(已被系统节流) → 与用户wishlist/偏好匹配才NOTIFY，否则SILENT

## 上次已通知
{last_notify if last_notify else "(无)"}
如果话题相同 → SILENT

## 回复格式（严格）
- 不需要通知: SILENT
- 需要通知: NOTIFY: <消息>
- **一次只推一条最重要的事件**，不要拼接多条

消息: 称呼"小明"，≤50字，给建议。
"""



# ── ProactiveBrain ────────────────────────────────────────

class ProactiveBrain:

    def __init__(self):
        self._last_event_time = ""
        self._lock = threading.Lock()
        self._notification_callback = None
        self._check_count = 0
        self._last_notify_msg = ""
        self._last_notify_topics: set = set()  # 已通知话题, 防重复
        self._rarity_tracker = RarityTracker()

    def set_callback(self, callback):
        self._notification_callback = callback

    def _topic_keywords(self, msg: str) -> set:
        """提取消息中的核心话题词（用于去重）。"""
        keywords = {"雨", "雷阵雨", "小雨", "中雨", "暴雨", "高温", "关闭",
                     "骑行", "骑车", "野餐", "户外", "公园", "温榆河", "奥森",
                     "电影院", "影院", "电影", "影城", "万达", "CGV", "保利",
                     "退票", "特价", "打折", "空桌", "排队", "火锅", "加班",
                     "生病", "发烧", "出差", "女朋友", "父母", "妈妈", "老板"}
        msg_words = set(msg.replace("，", " ").replace("、", " ").split())
        return keywords & msg_words

    def _is_duplicate_topic(self, msg: str) -> bool:
        """检查是否与最近通知话题重复(≥2个关键词重叠)。"""
        if msg == self._last_notify_msg:
            return True
        current = self._topic_keywords(msg)
        if not current:
            return False
        overlap = len(current & self._last_notify_topics)
        return overlap >= 2

    def _add_topics(self, msg: str):
        """记录本次通知的话题词。保留最近5条。"""
        self._last_notify_topics |= self._topic_keywords(msg)
        # 简单策略: 保留话题词, LLM 判断自然过期时重置
        # 每10次check清理一次旧话题
        if self._check_count % 10 == 0:
            self._last_notify_topics.clear()

    def check(self) -> str | None:
        """执行一次主动检查。三级分类 + 频次控制。"""
        try:
            self._check_count += 1

            # 1. 用户画像
            profile = memory.get_summary()
            if not profile or "(尚无记录)" in profile:
                return None

            # 2. 获取事件并按三级分类
            events = get_recent_events(limit=80)
            if not events:
                return None

            newest_time = events[-1].get("time", "")
            if newest_time == self._last_event_time and self._check_count > 1:
                return None
            self._last_event_time = newest_time

            personal, env, opp = [], [], []
            for e in events:
                cat, rarity = EVENT_CATEGORIES.get(e.get("type", ""), ("environmental", ""))
                if cat == "personal":
                    personal.append(e)
                elif cat == "opportunity":
                    if self._rarity_tracker.should_notify(e["type"], rarity):
                        opp.append(e)
                else:
                    env.append(e)

            # 3. 如果没有个人事务也没有需评估的事件，跳过
            has_urgent_personal = any(
                EVENT_CATEGORIES.get(e["type"], ("", ""))[1] in ("urgent", "high")
                for e in personal
            )
            if not personal and not env and not opp:
                return None

            # 4. 上下文 + LLM判断
            context = _get_context()

            prompt = _build_proactive_prompt(profile, personal, env, opp, context, self._last_notify_msg)
            print(f"[ProactiveBrain] #{self._check_count} P:{len(personal)} E:{len(env)} O:{len(opp)} ctx:{len(context)}c", flush=True)

            result = chat(
                system_prompt=prompt,
                user_message="请判断以上事件是否需要通知用户。",
                history=[],
            )

            if not result.get("ok"):
                print(f"[ProactiveBrain] LLM error: {result.get('error','')}", flush=True)
                return None

            reply = result.get("reply", "").strip()
            print(f"[ProactiveBrain] LLM({len(reply)}c): {reply[:150]}", flush=True)

            if reply.upper().startswith("SILENT"):
                return None

            if "NOTIFY:" in reply.upper():
                idx = reply.upper().find("NOTIFY:") + 7
                msg = reply[idx:].strip()
                # 只取第一条(防止LLM用 | 拼接多条)
                if " | " in msg:
                    msg = msg.split(" | ")[0].strip()
                if msg and not self._is_duplicate_topic(msg):
                    self._last_notify_msg = msg
                    self._add_topics(msg)
                    print(f"[ProactiveBrain] → 推送", flush=True)
                    return msg
                else:
                    print(f"[ProactiveBrain] → 跳过(重复话题)", flush=True)

            return None

        except Exception as e:
            print(f"[ProactiveBrain] 异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None


# 全局单例
brain = ProactiveBrain()


def start_proactive_loop(interval: float = 30.0, on_notify=None):
    """启动后台主动通知线程。"""
    brain.set_callback(on_notify)

    def loop():
        time.sleep(10)
        print("[ProactiveBrain] 三级分类通知引擎已启动", flush=True)
        while True:
            time.sleep(interval)
            try:
                msg = brain.check()
                if msg and on_notify:
                    on_notify(msg)
            except Exception as e:
                print(f"[ProactiveBrain] loop err: {e}", flush=True)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
