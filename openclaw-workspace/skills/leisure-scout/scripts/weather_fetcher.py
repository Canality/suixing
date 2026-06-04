#!/usr/bin/env python3
"""天气获取脚本 — 调用Mock API获取当前天气 + 活动建议。

Usage:
  python weather_fetcher.py
  python weather_fetcher.py --activity-hint
"""

import json
import argparse
import urllib.request
import os

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")


def get_weather() -> dict:
    try:
        with urllib.request.urlopen(f"{MOCK_API}/api/weather", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            data["source_label"] = "[天气网]"
            return data
    except Exception as e:
        return {"error": str(e), "source_label": "[天气网]"}


def get_weather_activities() -> dict:
    """获取天气 + 推荐活动。"""
    weather = get_weather()
    condition = weather.get("condition", "")
    temp = weather.get("temperature", 25)
    aqi = weather.get("aqi", 50)
    tip = weather.get("activity_tip", "")

    # 活动类型推荐
    if "雨" in condition:
        indoor_priority = ["电影", "展览", "密室", "演出"]
        outdoor_priority = []
    elif temp > 32:
        indoor_priority = ["电影", "展览", "密室"]
        outdoor_priority = ["市集"]
    elif aqi > 100:
        indoor_priority = ["电影", "展览", "密室"]
        outdoor_priority = []
    else:
        indoor_priority = ["电影", "密室"]
        outdoor_priority = ["户外", "骑行", "市集", "运动"]

    # 获取活动数据
    activities = {"indoor": [], "outdoor": []}
    for cat in indoor_priority[:2]:
        try:
            url = f"{MOCK_API}/api/activities?category={cat}&limit=3"
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for r in data.get("results", []):
                    r["source_label"] = "[猫眼]" if cat == "电影" else "[大麦]"
                    activities["indoor"].append(r)
        except Exception:
            pass
    for cat in outdoor_priority[:2]:
        try:
            url = f"{MOCK_API}/api/activities?category={cat}&limit=3"
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for r in data.get("results", []):
                    r["source_label"] = "[猫眼]"
                    activities["outdoor"].append(r)
        except Exception:
            pass

    return {
        "weather": weather,
        "tip": tip,
        "indoor_priority": indoor_priority,
        "outdoor_priority": outdoor_priority,
        "recommended_activities": activities,
        "one_liner": f"{condition} {temp}°C — {tip}",
    }


def main():
    parser = argparse.ArgumentParser(description="天气+活动推荐")
    parser.add_argument("--activity-hint", action="store_true",
                        help="附带活动推荐")
    args = parser.parse_args()

    if args.activity_hint:
        result = get_weather_activities()
    else:
        result = get_weather()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
