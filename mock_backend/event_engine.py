"""随机事件引擎 — 模拟真实世界状态变化。

每30秒运行一次:
1. 随机选1-2家餐厅调整排队(偏下降分布)
2. 10%概率触发特殊事件(满座/空位/特价菜/临时停业)
3. 场所状态随机变化(影院故障/地铁延误等)
4. 天气每5 tick刷新(约2.5分钟, Demo加速)
5. 活动状态可能变为sold_out, 5%概率退票恢复
6. 生活事件每tick 15%概率触发(工作/社交/财务/机会)
"""

import random
import time
import threading
from datetime import datetime

from mock_backend.mock_data import (
    get_restaurant_state, get_weather_state,
    get_activity_state, get_bike_state, get_venue_state,
    RESTAURANTS, WEATHER_CONDITIONS, BIKE_STATIONS, ACTIVITIES,
)
from mock_backend.life_events import tick_life_events

_events_log: list = []  # 最近的事件记录(最多50条)
_lock = threading.Lock()


def _add_event(event_type: str, entity_id: str, message: str):
    """线程安全地添加事件到日志。"""
    with _lock:
        _events_log.append({
            "time": datetime.now().isoformat(),
            "type": event_type,
            "entity_id": entity_id,
            "message": message,
        })
        if len(_events_log) > 100:
            _events_log[:] = _events_log[-100:]


def tick_restaurants():
    """更新餐厅动态状态。"""
    state = get_restaurant_state()

    targets = random.sample(list(state.keys()), min(random.randint(1, 2), len(state)))
    for rid in targets:
        r = state[rid]
        if not r["is_open"]:
            continue
        # 排队变化 (偏下降: 模拟排队随时间减少)
        delta = random.choice([-3, -2, -2, -1, -1, -1, 0, 0, +1])
        r["queue_length"] = max(0, r["queue_length"] + delta)
        r["wait_minutes"] = r["queue_length"] * 2 + random.randint(-3, 3) if r["queue_length"] > 0 else 0
        r["available_tables"] = max(0, r["available_tables"] + random.choice([-1, 0, 0, +1]))

        # 10%概率特殊事件
        if random.random() < 0.10:
            event_type = random.choice(
                ["restaurant_full", "table_opened", "daily_special",
                 "temporary_closed", "temporary_closed"]  # 2/5权重给停业, 低概率
            )
            rest = next((x for x in RESTAURANTS if x["id"] == rid), None)
            if rest is None:
                continue
            if event_type == "restaurant_full":
                r["available_tables"] = 0
                r["queue_length"] += random.randint(3, 8)
                msg = f"⚠️ {rest['name']} 刚才宣布满座！排队人数激增"
            elif event_type == "table_opened":
                r["available_tables"] += random.randint(2, 5)
                r["queue_length"] = max(0, r["queue_length"] - 3)
                msg = f"🟢 {rest['name']} 有空桌了！排队减少"
            elif event_type == "temporary_closed":
                if r.get("is_open", True):
                    r["is_open"] = False
                    r["available_tables"] = 0
                    r["queue_length"] = 0
                    msg = f"🚫 {rest['name']} 突发水管故障，临时停业！"
                    _add_event("restaurant_closed", rid, msg)
                    continue  # skip daily_special for closed restaurants
            else:
                special = random.choice([x for x in rest["recommendations"] if x not in r.get("daily_specials", [])])
                r["daily_specials"] = [special]
                msg = f"🔥 {rest['name']} 今日特价: {special} 限时8折"

            _add_event(event_type, rid, msg)

        # 停业餐厅10%概率恢复
        if not r.get("is_open", True) and random.random() < 0.10:
            r["is_open"] = True
            r["available_tables"] = random.randint(2, 6)
            rest = next((x for x in RESTAURANTS if x["id"] == rid), None)
            name = rest['name'] if rest else rid
            _add_event("restaurant_reopened", rid, f"✅ {name} 已恢复营业！")

        r["last_updated"] = datetime.now().isoformat()


def tick_weather():
    """更新天气实况 + 分时段预告 (Demo加速: 每2 tick, ~1分钟)。

    预告按"时段"组织: afternoon/evening/night/tomorrow_morning 等。
    LLM 根据用户计划的时间段来监控对应 slot。
    """
    w = get_weather_state()
    forecast = w.setdefault("forecast", {})

    # Step 1: 随机选1-2个时段更新预告 (60%概率变坏)
    slots = list(forecast.keys())
    for slot in random.sample(slots, min(random.randint(1, 2), len(slots))):
        old = forecast.get(slot, "晴")
        if random.random() < 0.60:
            if old in ("晴", "晴转多云", "多云", "多云转晴"):
                # 好天气 → 倾向变坏
                forecast[slot] = random.choice(["小雨", "中雨", "雷阵雨", "阴", "多云", "晴转多云"])
            else:
                # 坏天气 → 可能好转也可能更坏
                forecast[slot] = random.choice(WEATHER_CONDITIONS)
            _add_event("forecast_change", "weather",
                       f"天气预告: {slot}时段预计{forecast[slot]}")

    # Step 2: 当前实况有时兑现最近的预告 (25%概率)
    now = datetime.now()
    if now.hour < 12:
        active_slot = "tomorrow_morning"
    elif now.hour < 18:
        active_slot = "afternoon"
    elif now.hour < 22:
        active_slot = "evening"
    else:
        active_slot = "night"

    if random.random() < 0.25 and active_slot in forecast:
        old = w["condition"]
        if forecast[active_slot] != old:
            w["condition"] = forecast[active_slot]
            _add_event("weather_changed", "weather",
                       f"天气已变化: {old} → {w['condition']}")

    # Step 3: 温度/湿度/AQI 微调
    w["temperature"] += random.choice([-3, -2, -1, 0, +1, +2, +3])
    w["temperature"] = max(10, min(42, w["temperature"]))
    w["humidity"] = max(20, min(95, w["humidity"] + random.choice([-10, -5, 0, +5, +10])))
    w["aqi"] = max(20, min(250, w["aqi"] + random.choice([-20, -10, 0, +10, +20])))
    w["updated_at"] = datetime.now().isoformat()


def tick_activities():
    """更新活动状态（含退票事件）。"""
    state = get_activity_state()
    for aid, s in state.items():
        if s["status"] == "available" and random.random() < 0.03:
            s["status"] = "sold_out"
        # 5%概率: sold_out → available (有人退票)
        elif s["status"] == "sold_out" and random.random() < 0.05:
            s["status"] = "available"
            act = next((a for a in ACTIVITIES if a["id"] == aid), None)
            act_name = act["name"] if act else aid
            _add_event("ticket_released", aid, f"🎫 有人退票！{act_name} 现在有票了")
        s["discount"] = random.choice([0, 0, 0, 0, 0, 10, 20])


def tick_bikes():
    """更新单车数量(偏下降: 早晚高峰后单车被骑走)。"""
    state = get_bike_state()
    for b in BIKE_STATIONS:
        name = b["name"]
        if name in state:
            delta = random.choice([-3, -2, -2, -1, 0, +1, +2])
            state[name]["bikes_available"] = max(0, min(30, state[name]["bikes_available"] + delta))
            # 5%概率: 单车被骑光
            if state[name]["bikes_available"] <= 2 and random.random() < 0.05:
                state[name]["bikes_available"] = 0
                _add_event("bikes_empty", name, f"🚲 {name}附近单车被骑光了！")


def tick_venues():
    """场所/基础设施状态随机变化。影院故障、地铁延误、健身房装修等。"""
    state = get_venue_state()
    for name, s in state.items():
        current = s["status"]
        # 正常 → 异常 (3%概率)
        if current in ("open", "normal") and random.random() < 0.03:
            if s["type"] == "subway":
                s["status"] = "delayed"
                _add_event("venue_disrupted", name, f"🚇 {name}信号故障，延误约30分钟")
            elif s["type"] == "bike_service":
                s["status"] = "depleted"
                _add_event("venue_disrupted", name, f"🚲 {name}单车大面积短缺")
            elif s["type"] in ("cinema", "gym", "theater", "gallery", "escape"):
                reasons = ["设备故障", "临时维护", "消防检查", "空调坏了"]
                reason = random.choice(reasons)
                s["status"] = "maintenance"
                _add_event("venue_closed", name, f"🚫 {name}{reason}，今日暂时关闭")
            elif s["type"] in ("park", "market"):
                s["status"] = "closed"
                _add_event("venue_closed", name, f"🚫 {name}因天气原因临时关闭")
                # 同步天气: 场地因天气关闭 → 天气必须一致变坏
                w = get_weather_state()
                bad_weather = random.choice(["小雨", "中雨", "雷阵雨"])
                w["condition"] = bad_weather
                w["forecast"]["afternoon"] = bad_weather
                w["forecast"]["evening"] = bad_weather
                _add_event("weather_changed", "weather",
                           f"天气已变化: → {bad_weather}（{name}因此关闭）")
        # 异常 → 恢复 (8%概率)
        elif current in ("delayed", "maintenance", "closed", "depleted") and random.random() < 0.08:
            s["status"] = "open" if s["type"] != "subway" and s["type"] != "bike_service" else "normal"
            _add_event("venue_recovered", name, f"✅ {name}已恢复正常")


def run_all_ticks():
    """执行一轮完整tick。"""
    tick_restaurants()
    tick_activities()
    tick_bikes()
    tick_venues()
    # 生活事件: 15%概率触发
    tick_life_events(_add_event)


def get_recent_events(limit: int = 20) -> list:
    with _lock:
        return list(_events_log[-limit:])


def clear_events():
    """清空事件日志（页面刷新时调用）。"""
    with _lock:
        _events_log.clear()


# 后台tick线程
_tick_thread = None
_tick_running = False


def start_tick_loop(interval: float = 30.0):
    """启动后台tick循环(每30秒一次)。"""
    global _tick_thread, _tick_running
    _tick_running = True

    def _loop():
        tick_count = 0
        while _tick_running:
            time.sleep(interval)
            run_all_ticks()
            tick_count += 1
            if tick_count % 5 == 0:  # 每5 tick (~2.5分钟)更新天气, 让个人/机遇事件有空间
                tick_weather()

    _tick_thread = threading.Thread(target=_loop, daemon=True)
    _tick_thread.start()


def stop_tick_loop():
    global _tick_running
    _tick_running = False
