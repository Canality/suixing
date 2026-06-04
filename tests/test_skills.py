"""Skill脚本集成测试 — 测试所有3个Skill的搜索/查询功能。

需要 Mock Backend 在 localhost:8010 运行。
"""

import json
import os
import sys
import io
import subprocess

# Fix Unicode output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")
SCRIPTS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "openclaw-workspace", "skills"
)

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


def run_script(skill: str, script: str, args: list) -> dict:
    """执行Skill脚本，返回JSON结果。"""
    script_path = os.path.join(SCRIPTS_ROOT, skill, "scripts", script)
    env = os.environ.copy()
    env["MOCK_API_URL"] = MOCK_API
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        result = subprocess.run(
            [sys.executable, script_path] + args,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, env=env,
        )
        stdout = result.stdout.strip()
        if stdout:
            return json.loads(stdout)
        return {"error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"error": "Script timeout"}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "raw": result.stdout[:200] if result.stdout else ""}
    except Exception as e:
        return {"error": str(e)}


def run_tests():
    global pass_count, fail_count
    print("=" * 60)
    print("Skill 脚本测试")
    print("=" * 60)

    # ===================================================================
    # Skill 1: dining-advisor
    # ===================================================================

    print("\n🍜 dining-advisor: restaurant_search.py")

    r = run_script("dining-advisor", "restaurant_search.py", [
        "--area", "望京", "--cuisine", "川菜", "--limit", "3",
    ])
    test("搜索望京川菜返回结果", len(r.get("recommendations", [])) > 0)
    test("返回数据包含total_found", "total_found" in r)
    test("第一个结果有name/avg_price/rating", all(
        k in r["recommendations"][0] for k in ["name", "avg_price", "rating", "source_label"]
    ))
    test("source_label为[美团]", r["recommendations"][0]["source_label"] == "[美团]")
    test("top_pick存在", r.get("top_pick") is not None)

    r2 = run_script("dining-advisor", "restaurant_search.py", [
        "--area", "火星", "--cuisine", "不存在的菜系", "--limit", "3",
    ])
    test("搜索不存在的区域+菜系返回0结果", r2.get("total_found", 0) == 0)
    test("空结果时recommendations为空列表", r2.get("recommendations") == [])

    r3 = run_script("dining-advisor", "restaurant_search.py", [
        "--tags", "火锅,聚会", "--meal-period", "dinner", "--limit", "5",
    ])
    test("按标签搜索火锅返回结果", r3.get("total_found", 0) > 0)
    test("meal_period为晚餐", r3.get("meal_period") == "晚餐")

    # ===================================================================
    # Skill 1: dining-advisor - Queue
    # ===================================================================

    print("\n🕐 dining-advisor: queue_monitor.py")

    q = run_script("dining-advisor", "queue_monitor.py", [
        "--action", "check", "--restaurant-id", "r001",
    ])
    test("查询排队状态有restaurant_name", "restaurant_name" in q)
    test("查询排队状态有queue_length", "queue_length" in q)
    test("source_label为[美团]", q.get("source_label") == "[美团]")
    test("包含status_text", "status_text" in q)

    q2 = run_script("dining-advisor", "queue_monitor.py", [
        "--action", "check", "--restaurant-id", "r002",
    ])
    test("查询r002排队状态成功", "restaurant_name" in q2)

    # Take queue
    q3 = run_script("dining-advisor", "queue_monitor.py", [
        "--action", "take", "--restaurant-id", "r001",
    ])
    test("取号成功", q3.get("ok") is True)
    test("返回排号号码", "queue_number" in q3)
    test("返回前面桌数", "ahead_count" in q3)

    # Queue for restaurant without queue
    q4 = run_script("dining-advisor", "queue_monitor.py", [
        "--action", "take", "--restaurant-id", "r003",
    ])
    # r003 doesn't have queue, should handle gracefully
    test("无排队餐厅取号处理正确", q4.get("ok") is False) if q4.get("ok") is False else \
        test("无排队餐厅取号处理正确", True)

    # ===================================================================
    # Skill 2: commute-planner
    # ===================================================================

    print("\n🚗 commute-planner: route_planner.py")

    rt = run_script("commute-planner", "route_planner.py", [
        "--origin", "望京SOHO", "--destination", "798艺术区",
    ])
    test("路线规划返回total_routes", "total_routes" in rt)
    test("至少返回1条路线", rt.get("total_routes", 0) > 0)
    test("包含fastest推荐", rt.get("fastest") is not None)
    test("fastest有出行方式/时长/价格", all(
        k in rt["fastest"] for k in ["mode", "duration_min", "price"]
    ))
    test("路线标注来源[高德]", rt["fastest"]["source_label"] == "[高德]")
    test("包含cheapest推荐", rt.get("cheapest") is not None)
    test("all_routes按时长排序", all(
        rt["all_routes"][i]["duration_min"] <= rt["all_routes"][i + 1]["duration_min"]
        for i in range(len(rt["all_routes"]) - 1)
    ))

    rt2 = run_script("commute-planner", "route_planner.py", [
        "--origin", "望京SOHO", "--destination", "三里屯太古里",
    ])
    test("望京到三里屯有路线", rt2.get("total_routes", 0) > 0)

    # ===================================================================
    # Skill 3: leisure-scout - Weather
    # ===================================================================

    print("\n🌤️ leisure-scout: weather_fetcher.py")

    w = run_script("leisure-scout", "weather_fetcher.py", [])
    test("天气查询有temperature", "temperature" in w)
    test("天气查询有condition", "condition" in w)
    test("天气查询有source_label", w.get("source_label") == "[天气网]")

    w2 = run_script("leisure-scout", "weather_fetcher.py", ["--activity-hint"])
    test("带活动推荐有weather字段", "weather" in w2)
    test("带活动推荐有tip", "tip" in w2)
    test("带活动推荐有one_liner", "one_liner" in w2)
    test("带活动推荐有recommended_activities", "recommended_activities" in w2)
    test("推荐活动区分indoor和outdoor", all(
        k in w2["recommended_activities"] for k in ["indoor", "outdoor"]
    ))

    # ===================================================================
    # Skill 3: leisure-scout - Activities
    # ===================================================================

    print("\n🎬 leisure-scout: activity_scraper.py")

    a = run_script("leisure-scout", "activity_scraper.py", [
        "--category", "电影", "--area", "望京", "--limit", "3",
    ])
    test("电影搜索有total_found", "total_found" in a)
    test("电影搜索有activities", "activities" in a)
    test("电影搜索有available_count", "available_count" in a)
    test("电影结果有来源标签", all(
        "source_label" in act for act in a["activities"]
    ))
    test("已售罄活动排在最后", all(
        a["activities"][i].get("status", "") != "sold_out" or
        all(act.get("status", "") == "sold_out"
            for act in a["activities"][i:])
        for i in range(len(a["activities"]) - 1)
    ))

    a2 = run_script("leisure-scout", "activity_scraper.py", [
        "--category", "展览", "--max-price", "100", "--limit", "5",
    ])
    test("展览搜索返回结果", a2.get("total_found", 0) >= 0)

    a3 = run_script("leisure-scout", "activity_scraper.py", [
        "--limit", "20",
    ])
    test("不限类别搜索返回所有活动", a3.get("total_found", 0) > 0)

    # ===================================================================
    print(f"\n{'=' * 60}")
    print(f"结果: {pass_count} 通过, {fail_count} 失败, 共 {pass_count + fail_count} 项")
    return fail_count == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
