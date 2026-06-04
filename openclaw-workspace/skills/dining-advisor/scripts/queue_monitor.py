#!/usr/bin/env python3
"""排队监控脚本 — 取号、查询排队状态、轮询监控。

Usage:
  python queue_monitor.py --action take --restaurant-id r001
  python queue_monitor.py --action check --restaurant-id r001
  python queue_monitor.py --action monitor --restaurant-id r001 --alert-threshold 5
"""

import json
import argparse
import urllib.request
import time
import os

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")


def take_queue(restaurant_id: str) -> dict:
    """取号排队。"""
    url = f"{MOCK_API}/api/restaurants/{restaurant_id}/queue"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_queue(restaurant_id: str) -> dict:
    """查询排队状态。"""
    url = f"{MOCK_API}/api/restaurants/{restaurant_id}/queue"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # 添加来源标签
            data["source_label"] = "[美团]"
            # 生成进度描述
            ahead = data.get("queue_length", 0)
            wait = data.get("wait_minutes", 0)
            if ahead == 0:
                data["status_text"] = "已经排到了！请尽快到店"
            elif ahead <= 5:
                data["status_text"] = f"快到了！前面{ahead}桌, 预计{wait}分钟, 建议现在出发"
            elif ahead <= 10:
                data["status_text"] = f"前面{ahead}桌, 预计{wait}分钟, 可以准备了"
            else:
                data["status_text"] = f"前面{ahead}桌, 预计{wait}分钟, 还早"
            return data
    except Exception as e:
        return {"error": str(e)}


def monitor_queue(restaurant_id: str, alert_threshold: int = 5,
                  check_interval: int = 30, max_checks: int = 60) -> dict:
    """轮询监控排队(模拟后台线程行为)。"""
    checks = []
    for i in range(max_checks):
        status = check_queue(restaurant_id)
        checks.append({
            "check": i + 1,
            "queue_length": status.get("queue_length", 0),
            "wait_minutes": status.get("wait_minutes", 0),
            "timestamp": status.get("updated_at", ""),
        })
        ahead = status.get("queue_length", 999)
        if ahead <= alert_threshold:
            return {
                "alert": True,
                "message": f"前面只剩{ahead}桌！建议现在出发",
                "restaurant_name": status.get("restaurant_name", ""),
                "queue_length": ahead,
                "wait_minutes": status.get("wait_minutes", 0),
                "total_checks": i + 1,
                "checks": checks,
                "source_label": "[美团]",
                "next_action": "查询路线 → commute-planner",
            }
        time.sleep(min(check_interval, 5))  # 限制最大等待时间以保持响应

    return {
        "alert": False,
        "message": f"监控结束({max_checks}次检查)，排队尚未到达阈值",
        "total_checks": max_checks,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="排队监控")
    parser.add_argument("--action", required=True,
                        choices=["take", "check", "monitor"])
    parser.add_argument("--restaurant-id", required=True, help="餐厅ID")
    parser.add_argument("--alert-threshold", type=int, default=5,
                        help="排队提醒阈值(剩N桌时提醒)")
    parser.add_argument("--check-interval", type=int, default=30,
                        help="检查间隔(秒)")
    parser.add_argument("--max-checks", type=int, default=60)
    args = parser.parse_args()

    if args.action == "take":
        result = take_queue(args.restaurant_id)
    elif args.action == "check":
        result = check_queue(args.restaurant_id)
    else:
        result = monitor_queue(args.restaurant_id, args.alert_threshold,
                               args.check_interval, args.max_checks)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
