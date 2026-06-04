#!/usr/bin/env python3
"""活动搜索脚本 — 调用Mock API搜索附近活动/电影/演出。

Usage:
  python activity_scraper.py --category 电影 --area 望京
  python activity_scraper.py --category 展览 --max-price 100
"""

import json
import argparse
import urllib.request
import os

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")

CATEGORY_SOURCE_MAP = {
    "电影": "[猫眼]",
    "展览": "[大麦]",
    "演出": "[大麦]",
    "户外": "[美团]",
    "运动": "[美团]",
    "市集": "[大众点评]",
    "密室": "[大众点评]",
}


def search_activities(category: str = None, area: str = None,
                      max_price: int = None, limit: int = 10) -> dict:
    params = []
    if category:
        params.append(f"category={category}")
    if area:
        params.append(f"area={area}")
    if max_price is not None:
        params.append(f"max_price={max_price}")
    params.append(f"limit={limit}")

    url = f"{MOCK_API}/api/activities?{'&'.join(params)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e), "results": []}


def format_for_ai(data: dict) -> dict:
    results = data.get("results", [])
    formatted = []
    for a in results:
        source = CATEGORY_SOURCE_MAP.get(a.get("category", ""), "[美团]")
        entry = {
            "id": a["id"],
            "name": a["name"],
            "category": a["category"],
            "venue": a.get("venue", ""),
            "area": a.get("area", ""),
            "price": a.get("price", 0),
            "rating": a.get("rating", 0),
            "distance_km": a.get("distance_km", 0),
            "status": a.get("status", "available"),
            "discount": a.get("discount", 0),
            "tags": a.get("tags", []),
            "times": a.get("times", []),
            "source_label": source,
        }
        if entry["discount"] > 0:
            entry["price_after_discount"] = round(a["price"] * (1 - entry["discount"] / 100))
        formatted.append(entry)

    formatted.sort(key=lambda x: (x["status"] == "sold_out", -x["rating"]))
    return {
        "total_found": data.get("total", 0),
        "activities": formatted,
        "available_count": sum(1 for a in formatted if a["status"] == "available"),
        "timestamp": data.get("timestamp", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="活动搜索")
    parser.add_argument("--category", default=None, help="活动类别")
    parser.add_argument("--area", default=None, help="区域")
    parser.add_argument("--max-price", type=int, default=None, help="最高价格")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    data = search_activities(args.category, args.area, args.max_price, args.limit)
    result = format_for_ai(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
