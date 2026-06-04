#!/usr/bin/env python3
"""路径规划 — 调用Mock API获取多条路线方案。

Usage:
  python route_planner.py --origin "望京SOHO" --destination "798艺术区"
"""

import json
import argparse
import urllib.request
import os

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")


def plan_route(origin: str, destination: str) -> dict:
    body = json.dumps({"origin": origin, "destination": destination}).encode("utf-8")
    req = urllib.request.Request(
        f"{MOCK_API}/api/route",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # 添加来源标签
            for r in data.get("routes", []):
                r["source_label"] = "[高德]"
            return data
    except Exception as e:
        return {"error": str(e), "routes": []}


def format_for_ai(data: dict) -> dict:
    routes = data.get("routes", [])
    recommendations = []
    for r in routes[:4]:
        recommendations.append({
            "mode": r["mode"],
            "duration_min": r["duration_min"],
            "price": r.get("price_estimate", 0),
            "distance_km": r.get("distance_km", 0),
            "traffic": r.get("traffic", "正常"),
            "source_label": "[高德]",
        })

    if recommendations:
        fastest = min(recommendations, key=lambda x: x["duration_min"])
        cheapest = min(recommendations, key=lambda x: x["price"])
    else:
        fastest = cheapest = None

    return {
        "origin": data.get("origin", ""),
        "destination": data.get("destination", ""),
        "total_routes": len(recommendations),
        "fastest": fastest,
        "cheapest": cheapest,
        "all_routes": recommendations,
    }


def main():
    parser = argparse.ArgumentParser(description="路径规划")
    parser.add_argument("--origin", required=True, help="出发地")
    parser.add_argument("--destination", required=True, help="目的地")
    args = parser.parse_args()

    data = plan_route(args.origin, args.destination)
    result = format_for_ai(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
