"""Mock Backend 集成测试。需要mock-backend在localhost:8010运行。"""

import json
import os
import sys
import io

# Fix Unicode output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import urllib.request
import urllib.error
import urllib.parse


def url_encode(s: str) -> str:
    return urllib.parse.quote(s, safe='')

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")
pass_count = 0
fail_count = 0


def test(name: str, condition: bool):
    global pass_count, fail_count
    if condition:
        print(f"  ✅ {name}")
        pass_count += 1
    else:
        print(f"  ❌ {name} FAILED")
        fail_count += 1


def api_get(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{MOCK_API}{path}", timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def run_tests():
    global pass_count, fail_count
    print("=" * 60)
    print("Mock Backend 测试")
    print("=" * 60)

    # Health
    print("\n🏥 Health Check")
    h = api_get("/api/health")
    test("Health endpoint returns ok", h.get("ok") is True)

    # Restaurants
    print("\n🍜 Restaurant API")
    r = api_get(f"/api/restaurants?area={url_encode('望京')}&limit=5")
    test("Restaurant search returns results", r.get("total", 0) > 0)
    test("Results contain name and rating", "name" in r["results"][0] and "rating" in r["results"][0])
    test("Results contain dynamic queue state", "queue_length" in r["results"][0])
    test("Results sorted by match_score", r["results"][0].get("match_score", 0) >= r["results"][-1].get("match_score", 0))

    # Restaurant detail
    print("\n📋 Restaurant Detail")
    d = api_get("/api/restaurants/r001")
    test("Detail has name", d.get("name") == "后院·川渝火锅(望京店)")
    test("Detail has dynamic state", "queue_length" in d)

    # Queue
    print("\n🕐 Queue API")
    q = api_get("/api/restaurants/r001/queue")
    test("Queue returns status", "queue_length" in q)

    # Weather
    print("\n🌤️ Weather API")
    w = api_get("/api/weather")
    test("Weather has temperature", "temperature" in w)
    test("Weather has condition", "condition" in w)
    test("Weather has activity_tip", "activity_tip" in w)

    # Activities
    print("\n🎬 Activity API")
    a = api_get(f"/api/activities?category={url_encode('电影')}&limit=3")
    test("Activity search returns results", a.get("total", 0) > 0)
    test("Activities have dynamic status", "status" in a["results"][0])

    # Random Events
    print("\n🎲 Random Events")
    e = api_get("/api/events/random")
    test("Random events returns events", len(e.get("events", [])) > 0)

    print(f"\n{'=' * 60}")
    print(f"结果: {pass_count} 通过, {fail_count} 失败, 共 {pass_count + fail_count} 项")
    return fail_count == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
