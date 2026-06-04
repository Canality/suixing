#!/usr/bin/env python3
"""Heartbeat Runner — 7x24后台监控执行器。

三线程监控: 餐食时段 / 排队进度 / 天气变化
由OpenClaw HEARTBEAT.md触发, 每60秒运行一次。

Usage:
  python heartbeat_runner.py --dry-run          # 模拟运行
  python heartbeat_runner.py --monitor meal      # 仅餐食监控
  python heartbeat_runner.py --monitor queue     # 仅排队监控
  python heartbeat_runner.py --monitor weather   # 仅天气监控
  python heartbeat_runner.py --monitor all       # 全部三线程
"""

import json
import os
import sys
import argparse
import urllib.request
from datetime import datetime, date, timedelta

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")
STATE_FILE = os.path.join(os.path.dirname(__file__), "heartbeat_state.json")


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_current_meal_period() -> str:
    """根据当前时间确定餐食时段。"""
    hour = datetime.now().hour
    if 7 <= hour < 9:
        return "breakfast"
    elif 11 <= hour < 13:
        return "lunch"
    elif 17 <= hour < 20:
        return "dinner"
    elif 21 <= hour < 23:
        return "latenight"
    return ""


def call_mock_api(endpoint: str) -> dict:
    try:
        with urllib.request.urlopen(f"{MOCK_API}{endpoint}", timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# 监控 1: 餐食时段
# ═══════════════════════════════════════════════════════════════

def monitor_meal(state: dict, dry_run: bool = False) -> list:
    """检测餐食时段, 决定是否推送餐厅推荐。"""
    actions = []
    period = get_current_meal_period()
    if not period:
        return actions

    meal_state = state.get("meal", {})
    last_trigger = meal_state.get("last_trigger", "")
    today = str(date.today())

    # 每餐只触发一次
    key = f"{today}_{period}"
    if meal_state.get(key):
        return actions

    period_names = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "latenight": "夜宵"}
    actions.append({
        "type": "meal_recommendation",
        "period": period,
        "message": f"{period_names.get(period)}时间到了！要不要帮你推荐附近的餐厅？",
        "action": "trigger dining-advisor",
        "api_call": f"GET /api/restaurants?area=望京&meal-period={period}",
    })

    if not dry_run:
        meal_state[key] = True
        meal_state["last_trigger"] = today
        state["meal"] = meal_state
        save_state(state)

    return actions


# ═══════════════════════════════════════════════════════════════
# 监控 2: 排队进度
# ═══════════════════════════════════════════════════════════════

def monitor_queue(state: dict, dry_run: bool = False) -> list:
    """检查活跃排队, 决定是否推送提醒。"""
    actions = []
    active_queues = state.get("active_queues", [])

    for q in list(active_queues):
        rid = q.get("restaurant_id", "")
        data = call_mock_api(f"/api/restaurants/{rid}/queue")
        if "error" in data:
            continue

        ahead = data.get("queue_length", 0)
        wait = data.get("wait_minutes", 0)
        name = data.get("restaurant_name", "")

        # 决策矩阵
        if ahead == 0:
            actions.append({
                "type": "queue_ready",
                "restaurant": name,
                "message": f"排到了！{name}可以入座了",
                "action": "alert_user",
            })
            active_queues.remove(q)
        elif ahead <= 5 and not q.get("warned"):
            actions.append({
                "type": "queue_almost",
                "restaurant": name,
                "ahead": ahead,
                "wait_min": wait,
                "message": f"{name}前面只剩{ahead}桌(约{wait}分钟), 建议现在出发！",
                "action": "alert_user + suggest_ride",
                "chain_action": "commute-planner → 规划打车路线",
            })
            q["warned"] = True
        elif ahead <= 10 and not q.get("notified"):
            actions.append({
                "type": "queue_update",
                "restaurant": name,
                "ahead": ahead,
                "wait_min": wait,
                "message": f"{name}前面还有{ahead}桌, 预计{wait}分钟",
                "action": "notify_user",
            })
            q["notified"] = True

    if active_queues != state.get("active_queues"):
        state["active_queues"] = active_queues
        if not dry_run:
            save_state(state)

    return actions


# ═══════════════════════════════════════════════════════════════
# 监控 3: 天气+活动
# ═══════════════════════════════════════════════════════════════

def monitor_weather_activity(state: dict, dry_run: bool = False) -> list:
    """检测天气变化+活动推荐时机。"""
    actions = []
    now = datetime.now()
    today = str(date.today())

    ws = state.get("weather", {})
    last_check = ws.get("last_check", "")

    # 每小时检查一次, 周末早上9点重点推荐
    if last_check == today:
        return actions

    data = call_mock_api("/api/weather")
    if "error" in data:
        return actions

    condition = data.get("condition", "")
    temp = data.get("temperature", 25)
    tip = data.get("activity_tip", "")

    is_weekend = date.today().weekday() >= 5
    is_morning = 7 <= now.hour <= 10

    if is_weekend and is_morning:
        actions.append({
            "type": "weekend_activity",
            "message": f"周末好！{condition} {temp}°C — {tip}",
            "action": "trigger leisure-scout",
        })
    elif "雨" in condition and not ws.get("rain_warned_today"):
        actions.append({
            "type": "rain_alert",
            "message": f"{condition} {temp}°C, 记得带伞！推荐室内活动",
            "action": "trigger leisure-scout → 室内活动",
        })
        ws["rain_warned_today"] = True

    if not dry_run:
        ws["last_check"] = today
        state["weather"] = ws
        save_state(state)

    return actions


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="7x24 Heartbeat Runner")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行(不写状态)")
    parser.add_argument("--monitor", default="all",
                        choices=["meal", "queue", "weather", "all"])
    args = parser.parse_args()

    state = load_state() if not args.dry_run else {}
    all_actions = []

    if args.monitor in ("meal", "all"):
        all_actions.extend(monitor_meal(state, args.dry_run))
    if args.monitor in ("queue", "all"):
        all_actions.extend(monitor_queue(state, args.dry_run))
    if args.monitor in ("weather", "all"):
        all_actions.extend(monitor_weather_activity(state, args.dry_run))

    output = {
        "heartbeat_time": datetime.now().isoformat(),
        "dry_run": args.dry_run,
        "monitor": args.monitor,
        "actions_count": len(all_actions),
        "actions": all_actions,
    }

    if not all_actions:
        output["status"] = "HEARTBEAT_OK"
    else:
        output["status"] = "ACTIONS_PENDING"

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
