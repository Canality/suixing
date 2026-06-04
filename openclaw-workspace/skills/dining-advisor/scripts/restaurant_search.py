#!/usr/bin/env python3
"""餐厅搜索脚本 — 调用Mock API搜索餐厅，返回结构化结果。

Usage:
  python restaurant_search.py --area 望京 --cuisine 川菜 --max-price 100 --meal-period dinner
  python restaurant_search.py --area 望京 --tags 火锅,聚会
"""

import json
import argparse
import urllib.request
import urllib.parse
import os

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")


def search_restaurants(area: str = None, cuisine: str = None,
                       max_price: int = None, tags: str = None,
                       min_rating: float = None, limit: int = 5) -> dict:
    """调用Mock API搜索餐厅。"""
    params = {}
    if area:
        params["area"] = area
    if cuisine:
        params["cuisine"] = cuisine
    if max_price:
        params["max_price"] = max_price
    if tags:
        params["tags"] = tags
    if min_rating:
        params["min_rating"] = min_rating
    params["limit"] = limit

    qs = urllib.parse.urlencode(params)
    url = f"{MOCK_API}/api/restaurants?{qs}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e), "results": []}


def format_for_ai(data: dict, meal_period: str = "dinner") -> dict:
    """将API返回数据格式化为AI可直接使用的结构。"""
    results = data.get("results", [])
    formatted = []
    for r in results[:5]:
        entry = {
            "id": r["id"],
            "name": r["name"],
            "cuisine": r["cuisine"],
            "area": r["area"],
            "avg_price": r["avg_price"],
            "rating": r["rating"],
            "distance_km": r["distance_km"],
            "queue_length": r.get("queue_length", 0),
            "wait_minutes": r.get("wait_minutes", 0),
            "available_tables": r.get("available_tables", 0),
            "has_queue": r.get("has_queue", False),
            "daily_specials": r.get("daily_specials", []),
            "recommendations": r.get("recommendations", [])[:3],
            "match_score": r.get("match_score", 0),
            "source_label": "[美团]",
        }
        # 排队状态描述
        if r.get("queue_length", 0) > 0:
            entry["queue_status"] = f"排队{r['queue_length']}桌, 约{r.get('wait_minutes', '?')}分钟"
        elif r.get("available_tables", 0) > 0:
            entry["queue_status"] = f"有空位({r['available_tables']}桌)"
        else:
            entry["queue_status"] = "已满座"
        formatted.append(entry)

    period_labels = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "latenight": "夜宵"}
    return {
        "meal_period": period_labels.get(meal_period, "用餐"),
        "total_found": data.get("total", 0),
        "recommendations": formatted,
        "top_pick": formatted[0] if formatted else None,
        "timestamp": data.get("timestamp", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="餐厅搜索")
    parser.add_argument("--area", default="望京", help="区域")
    parser.add_argument("--cuisine", default=None, help="菜系")
    parser.add_argument("--max-price", type=int, default=None, help="最高人均")
    parser.add_argument("--tags", default=None, help="标签(逗号分隔)")
    parser.add_argument("--min-rating", type=float, default=None, help="最低评分")
    parser.add_argument("--meal-period", default="dinner",
                        choices=["breakfast", "lunch", "dinner", "latenight"])
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    data = search_restaurants(
        area=args.area, cuisine=args.cuisine,
        max_price=args.max_price, tags=args.tags,
        min_rating=args.min_rating, limit=args.limit,
    )
    result = format_for_ai(data, args.meal_period)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
