"""工具执行器 — 执行Skill脚本和Mock API调用"""

import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from server.config import MOCK_API_URL, get_skill_scripts_dir


def execute_script(skill_name: str, script_name: str, args: list) -> dict:
    """执行指定Skill的Python脚本，返回JSON结果。"""
    scripts_dir = get_skill_scripts_dir(skill_name)
    script_path = os.path.join(scripts_dir, script_name)

    if not os.path.exists(script_path):
        return {"error": f"Script not found: {script_path}"}

    cmd = [sys.executable, script_path] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30)
        stdout = result.stdout.strip()
        if stdout:
            return json.loads(stdout)
        return {"error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"error": "Script timeout (30s)"}
    except json.JSONDecodeError:
        return {"error": "Script returned invalid JSON", "raw": result.stdout[:300]}
    except Exception as e:
        return {"error": str(e)}


def call_mock_api(endpoint: str) -> dict:
    """调用Mock API。"""
    url = f"{MOCK_API_URL}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# LLM工具定义 (OpenAI function calling格式)
# ═══════════════════════════════════════════════════════════════

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "搜索附近餐厅。当用户想吃东西、问餐厅推荐时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "区域，如望京/酒仙桥"},
                    "cuisine": {"type": "string", "description": "菜系，如川菜/火锅/日料"},
                    "max_price": {"type": "integer", "description": "最高人均价格"},
                    "tags": {"type": "string", "description": "标签，如排队热门/聚会/快餐"},
                    "meal_period": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "latenight"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_queue",
            "description": "查询/取号餐厅排队状态。当用户想排队取号或查看排队进度时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["take", "check"]},
                    "restaurant_id": {"type": "string", "description": "餐厅ID"},
                },
                "required": ["action", "restaurant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_route",
            "description": "路径规划。当用户问怎么去某地、打车多少钱时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "出发地"},
                    "destination": {"type": "string", "description": "目的地"},
                    "mode": {"type": "string", "enum": ["打车", "美团单车", "地铁"]},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_activities",
            "description": "搜索附近活动/电影/演出。当用户问周末有什么好玩的时候调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["电影", "展览", "户外", "运动", "演出", "市集", "密室"]},
                    "area": {"type": "string", "description": "区域"},
                    "max_price": {"type": "integer", "description": "最高价格"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取当前天气。当用户问天气时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_watch",
            "description": (
                "创建一个后台监控任务。当用户表达了一个意图，但当前条件不满足时调用。"
                "例如: 用户想吃火锅但排队太长→创建排队监控；"
                "用户想骑行但天气不好→创建天气监控；"
                "用户想看演出但票售罄→创建票源监控。"
                "即使条件满足，也可创建监控持续跟踪变化。"
                "户外活动→必须考虑天气；餐厅→必须考虑排队；演出→必须考虑票源。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "watch_type": {
                        "type": "string",
                        "enum": ["queue_threshold", "weather_change", "ticket_available", "time_point"],
                        "description": "监控类型",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "监控目标ID（餐厅ID如r001/活动ID如a003），天气监控留空",
                    },
                    "target_name": {
                        "type": "string",
                        "description": "监控目标的可读名称，如'海底捞(望京)'或'周末天气'",
                    },
                    "condition": {
                        "type": "string",
                        "description": (
                            "触发条件表达式。支持: field op value。"
                            "op ∈ {<=, >=, ==, !=, <, >, in, not in}。"
                            "餐厅字段: queue_length(排队桌数)。"
                            "天气字段: condition(如'晴'/'雨'), temperature(温度), aqi(空气质量)。"
                            "活动字段: status('available'/'sold_out')。"
                            "时间字段: hour(0-23), minute(0-59)。"
                            "示例: 'queue_length <= 5', 'condition not in (雨,雷阵雨)', 'status == available', 'hour >= 17'"
                        ),
                    },
                    "trigger_instruction": {
                        "type": "string",
                        "description": (
                            "触发后LLM的自主行动指令。写清楚: 1)通知用户什么 2)调哪些工具 3)推荐什么联动。"
                            "如: '排队快到了，告诉用户+预估叫车时间+推荐海底捞附近饭后活动'"
                        ),
                    },
                    "context": {
                        "type": "string",
                        "description": "用户原始意图上下文，触发时参考。如'用户想周末去骑行'",
                    },
                },
                "required": ["watch_type", "target_name", "condition", "trigger_instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "持久记住用户的重要信息。当用户在对话中透露了偏好、习惯、忌口、预算、住址、"
                "出行方式、兴趣等信息时调用。不要等用户明确说'记住'——听到重要信息就主动记录。"
                "什么值得记: 口味偏好、忌口/过敏、预算区间、出行习惯、居住/工作区域、兴趣爱好。"
                "什么不记: 一次性需求、闲聊内容、已过时的信息。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["food", "weather", "residence", "transport", "entertainment", "basic", "status"],
                        "description": "记忆域: food=食, weather=衣(天气偏好), residence=住, transport=行, entertainment=娱, basic=基本, status=状态",
                    },
                    "key": {
                        "type": "string",
                        "description": "具体字段。如 cuisines_liked, dislikes, allergies, budget_lunch, budget_dinner, home, work, commute, mode_preference, sports, movies, wishlist",
                    },
                    "value": {
                        "type": "string",
                        "description": "记录的值。追加型字段(cuisines_liked/sports/movies等)会合并到原值；覆盖型字段(home/budget等)会替换原值",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["confirmed", "inferred"],
                        "description": "confirmed=用户明确说的, inferred=从行为推断的",
                    },
                },
                "required": ["category", "key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": (
                "查询用户画像的详细信息。当你需要用户的具体偏好细节、历史记录、wishlist等"
                "不在摘要中的信息时调用。例如: 用户上次去的餐厅、预算细节、具体忌口等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询关键词，如 '上次吃的餐厅' 'wishlist' '预算细节' '忌口' '通勤路线' '兴趣偏好'",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_route_link",
            "description": (
                "生成高德地图导航链接。当用户需要具体路线导航、或用户想'打开高德看看'时调用。"
                "返回可点击跳转的高德地图链接(手机端唤醒App, 电脑端打开网页)。"
                "骑行场景、驾车场景、公交场景都应生成对应链接。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "出发地"},
                    "destination": {"type": "string", "description": "目的地"},
                    "mode": {
                        "type": "string",
                        "enum": ["bicycle", "drive", "bus", "walk"],
                        "description": "出行方式: bicycle=骑行, drive=驾车, bus=公交, walk=步行",
                    },
                    "distance_km": {"type": "number", "description": "距离(km), 如已知"},
                    "duration_min": {"type": "integer", "description": "预计时长(分钟), 如已知"},
                },
                "required": ["origin", "destination", "mode"],
            },
        },
    },
]


def execute_tool_call(tool_name: str, tool_args: dict) -> dict:
    """执行LLM请求的工具调用，返回结果。"""
    if tool_name == "search_restaurants":
        args = []
        if tool_args.get("area"):
            args.extend(["--area", tool_args["area"]])
        if tool_args.get("cuisine"):
            args.extend(["--cuisine", tool_args["cuisine"]])
        if tool_args.get("max_price"):
            args.extend(["--max-price", str(tool_args["max_price"])])
        if tool_args.get("tags"):
            args.extend(["--tags", tool_args["tags"]])
        if tool_args.get("meal_period"):
            args.extend(["--meal-period", tool_args["meal_period"]])
        return execute_script("dining-advisor", "restaurant_search.py", args)

    elif tool_name == "check_queue":
        return execute_script("dining-advisor", "queue_monitor.py", [
            "--action", tool_args.get("action", "check"),
            "--restaurant-id", tool_args["restaurant_id"],
        ])

    elif tool_name == "plan_route":
        return execute_script("commute-planner", "route_planner.py", [
            "--origin", tool_args["origin"],
            "--destination", tool_args["destination"],
        ])

    elif tool_name == "search_activities":
        args = []
        if tool_args.get("category"):
            args.extend(["--category", tool_args["category"]])
        if tool_args.get("area"):
            args.extend(["--area", tool_args["area"]])
        if tool_args.get("max_price"):
            args.extend(["--max-price", str(tool_args["max_price"])])
        return execute_script("leisure-scout", "activity_scraper.py", args)

    elif tool_name == "get_weather":
        return execute_script("leisure-scout", "weather_fetcher.py", ["--activity-hint"])

    elif tool_name == "create_watch":
        from server.watchdog import watchdog, WatchTask
        task = WatchTask(
            id=f"watch_{int(time.time())}_{random.randint(1000, 9999)}",
            type=tool_args["watch_type"],
            target_id=tool_args.get("target_id", ""),
            target_name=tool_args["target_name"],
            condition=tool_args["condition"],
            trigger_instruction=tool_args["trigger_instruction"],
            context=tool_args.get("context", ""),
            session_id="main",
        )
        watchdog.add_task(task)
        return {"ok": True, "task_id": task.id, "message": f"已开始监控: {task.target_name}"}

    elif tool_name == "remember":
        from server.memory import memory
        return memory.remember(
            category=tool_args["category"],
            key=tool_args["key"],
            value=tool_args["value"],
            confidence=tool_args.get("confidence", "confirmed"),
        )

    elif tool_name == "get_user_profile":
        from server.memory import memory
        detail = memory.get_detail(tool_args["query"])
        return {"ok": True, "query": tool_args["query"], "result": detail}

    elif tool_name == "generate_route_link":
        return execute_script("commute-planner", "route_link.py", [
            "--origin", tool_args["origin"],
            "--destination", tool_args["destination"],
            "--mode", tool_args.get("mode", "bicycle"),
            "--distance", str(tool_args.get("distance_km", 0)),
            "--duration", str(tool_args.get("duration_min", 0)),
        ])

    return {"error": f"Unknown tool: {tool_name}"}
