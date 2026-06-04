#!/usr/bin/env python3
"""SuiXing Demo Server — 本地生活管家 Web 应用入口。

一键启动:
  python app.py
  → 浏览器打开 http://localhost:8010
"""

import json
import asyncio
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

from server.config import HOST, PORT
from server.session import get_or_create_session
from server.event_bus import bus
from server.prompts import refresh_cache
from server.watchdog import watchdog, start_watchdog_loop
from server.proactive import brain, start_proactive_loop

# ═══════════════════════════════════════════════════════════════
# Mock Backend (内嵌)
# ═══════════════════════════════════════════════════════════════

from mock_backend.mock_data import (
    RESTAURANTS, ACTIVITIES, RIDE_ROUTES, BIKE_STATIONS,
    get_restaurant_state, get_weather_state, get_activity_state, get_bike_state,
)
from mock_backend.event_engine import start_tick_loop, get_recent_events
import random

app = FastAPI(title="SuiXing Demo Server", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ═══════════════════════════════════════════════════════════════
# Web UI
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            "<h1>SuiXing Demo Server is running</h1><p>UI template not found.</p>",
            status_code=200,
        )


# ═══════════════════════════════════════════════════════════════
# Chat API
# ═══════════════════════════════════════════════════════════════

@app.post("/api/chat")
async def chat_endpoint(req: Request):
    try:
        body = await req.json()
    except Exception:
        return {"ok": False, "error": "invalid JSON body"}
    message = (body.get("message") or "").strip()
    session_id = body.get("session_id", "main")
    if not message:
        return {"ok": False, "error": "empty message"}

    session = get_or_create_session(session_id)
    try:
        reply = await session.handle_message(message)
        return {"ok": True, "reply": reply}
    except Exception as e:
        return {"ok": False, "error": f"处理消息失败: {str(e)}"}


@app.post("/api/reset")
async def reset_session(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    session_id = body.get("session_id", "main")
    from server.session import _sessions
    if session_id in _sessions:
        del _sessions[session_id]
    return {"ok": True, "message": f"Session {session_id} reset"}


# ═══════════════════════════════════════════════════════════════
# SSE Events (技术面板)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/events")
async def events():
    q = bus.subscribe()

    async def stream():
        try:
            while True:
                # Check async queue
                try:
                    data = await asyncio.wait_for(q.get(), timeout=5)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    pass
                # Check sync heartbeat queue
                try:
                    while True:
                        item = _sse_queue.get_nowait()
                        yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                except _sync_queue.Empty:
                    pass
                # Send keepalive
                yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════════════════
# System info
# ═══════════════════════════════════════════════════════════════

@app.get("/api/info")
async def info():
    return {
        "name": "随行 SuiXing",
        "version": "2.0.0",
        "skills": ["dining-advisor", "commute-planner", "leisure-scout"],
        "workspace": "openclaw-workspace/",
        "llm_model": "deepseek-chat",
        "started_at": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# Mock API (内嵌在同一个Server中)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/restaurants")
def mock_restaurants(area: str = None, cuisine: str = None,
                     max_price: int = None, tags: str = None,
                     min_rating: float = None, limit: int = 10):
    rstate = get_restaurant_state()
    results = []
    for r in RESTAURANTS:
        if area and r.get("area") != area:
            continue
        if cuisine and cuisine not in r.get("cuisine", ""):
            continue
        if max_price and r.get("avg_price", 0) > max_price:
            continue
        if min_rating and r.get("rating", 0) < min_rating:
            continue
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            if not any(t in r.get("tags", []) for t in tag_list):
                continue
        dyn = rstate.get(r["id"], {})
        result = {**r, **dyn}
        result["match_score"] = round(
            max(0, 5 - r.get("distance_km", 5)) * 0.3 + r.get("rating", 0) * 0.5 +
            (0.2 if not dyn.get("queue_length", 0) else 0), 2
        )
        results.append(result)
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return {"total": len(results), "results": results[:limit], "timestamp": datetime.now().isoformat()}


@app.get("/api/restaurants/{restaurant_id}")
def mock_restaurant_detail(restaurant_id: str):
    r = next((x for x in RESTAURANTS if x["id"] == restaurant_id), None)
    if not r:
        return {"error": "not found"}
    dyn = get_restaurant_state().get(restaurant_id, {})
    return {**r, **dyn}


@app.get("/api/restaurants/{restaurant_id}/queue")
def mock_queue(restaurant_id: str):
    dyn = get_restaurant_state().get(restaurant_id, {})
    r = next((x for x in RESTAURANTS if x["id"] == restaurant_id), {})
    return {
        "restaurant_id": restaurant_id,
        "restaurant_name": r.get("name", ""),
        "has_queue": r.get("has_queue", False),
        "queue_length": dyn.get("queue_length", 0),
        "wait_minutes": dyn.get("wait_minutes", 0),
        "available_tables": dyn.get("available_tables", 0),
        "is_open": dyn.get("is_open", True),
        "source_label": "[美团]",
    }


@app.post("/api/restaurants/{restaurant_id}/queue")
async def mock_take_queue(restaurant_id: str):
    r = next((x for x in RESTAURANTS if x["id"] == restaurant_id), None)
    if not r:
        return {"ok": False, "error": "not found"}
    if not r.get("has_queue"):
        return {"ok": False, "message": f"{r['name']}无需排队"}
    dyn = get_restaurant_state().get(restaurant_id, {})
    num = f"{r['id'].upper()}{random.randint(100,999)}"
    return {
        "ok": True, "restaurant_name": r["name"],
        "queue_number": num, "ahead_count": dyn.get("queue_length", 0),
        "estimated_wait_min": dyn.get("wait_minutes", 15),
        "message": f"取号成功！{num}, 前面{dyn.get('queue_length',0)}桌, 预计{dyn.get('wait_minutes',15)}分钟 [美团]",
    }


@app.get("/api/weather")
def mock_weather():
    w = get_weather_state()
    tip = ""
    if "雨" in w.get("condition", ""):
        tip = "有雨，建议室内活动"
    elif w.get("temperature", 25) > 32:
        tip = "天气较热，推荐室内商场"
    elif w.get("aqi", 50) < 50:
        tip = "空气质量优秀，适合户外骑行"
    else:
        tip = "天气不错，适合外出活动"
    return {**w, "activity_tip": tip, "source_label": "[天气网]"}


@app.get("/api/activities")
def mock_activities(category: str = None, area: str = None,
                    max_price: int = None, limit: int = 10):
    astate = get_activity_state()
    results = []
    for a in ACTIVITIES:
        if category and a.get("category") != category:
            continue
        if area and a.get("area") != area:
            continue
        if max_price is not None and a.get("price", 0) > max_price:
            continue
        dyn = astate.get(a["id"], {})
        results.append({**a, **dyn})
    results.sort(key=lambda x: x.get("rating", 0), reverse=True)
    return {"total": len(results), "results": results[:limit], "timestamp": datetime.now().isoformat()}


@app.post("/api/route")
async def mock_route(req: Request):
    body = await req.json()
    origin = body.get("origin", "")
    destination = body.get("destination", "")
    routes = [r for r in RIDE_ROUTES if origin in r["from"] and destination in r["to"]]
    if not routes:
        routes = [r for r in RIDE_ROUTES if destination in r.get("to", "")]
    results = []
    for r in routes:
        traffic = random.choice(["畅通", "正常", "正常", "正常", "拥堵"])
        mult = 1.2 if traffic == "拥堵" else (0.9 if traffic == "畅通" else 1.0)
        results.append({
            **r, "traffic": traffic,
            "duration_min": round(r["duration_min"] * mult),
            "price_estimate": round(r.get("price_estimate", 0) * random.uniform(0.9, 1.2), 1),
            "source_label": "[高德]",
        })
    results.sort(key=lambda x: x["duration_min"])
    return {"origin": origin, "destination": destination, "routes": results}


@app.post("/api/ride/estimate")
async def mock_ride_estimate(req: Request):
    body = await req.json()
    origin = body.get("origin", "")
    destination = body.get("destination", "")
    mode = body.get("mode", "打车")
    route = next((r for r in RIDE_ROUTES
                  if origin in r["from"] and destination in r["to"] and r.get("mode") == mode), None)
    if not route:
        return {"ok": False, "message": "未找到匹配路线"}
    surge = random.choice([1.0, 1.0, 1.0, 1.0, 1.5])
    return {
        "ok": True, "mode": mode, "origin": origin, "destination": destination,
        "distance_km": route["distance_km"],
        "duration_min": route["duration_min"],
        "price_estimate": round(route["price_estimate"] * surge, 1),
        "wait_min": random.randint(1, 6),
        "surge": surge > 1.0,
        "source_label": "[高德]",
    }


@app.get("/api/bikes")
def mock_bikes(area: str = None):
    bstate = get_bike_state()
    results = []
    for b in BIKE_STATIONS:
        if area and b.get("area") != area:
            continue
        dyn = bstate.get(b["name"], {})
        results.append({**b, **dyn})
    return {"total": len(results), "stations": results}


@app.get("/api/events/random")
def mock_random_events(limit: int = 10):
    events = get_recent_events(limit)
    if not events:
        r = random.choice(RESTAURANTS)
        events = [{"type": "queue_update", "message": f"📊 {r['name']}: 前面{random.randint(3,8)}桌, 预计{random.randint(10,25)}分钟"}]
    return {"events": events, "timestamp": datetime.now().isoformat()}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "SuiXing Demo Server", "timestamp": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════════════════
# Watch API (长时监控任务)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/watch/list")
def list_watches():
    tasks = watchdog.list_tasks()
    return {"ok": True, "total": len(tasks), "tasks": [
        {"id": t.id, "type": t.type, "target_name": t.target_name,
         "condition": t.condition, "status": t.status, "created_at": t.created_at}
        for t in tasks
    ]}


@app.post("/api/watch/cancel")
async def cancel_watch(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    task_id = body.get("task_id", "")
    if not task_id:
        return {"ok": False, "error": "task_id required"}
    success = watchdog.cancel(task_id)
    return {"ok": success, "message": f"Task {task_id} {'cancelled' if success else 'not found'}"}


# ═══════════════════════════════════════════════════════════════
# 7x24 Heartbeat API
# ═══════════════════════════════════════════════════════════════

_heartbeat_state = {"meal_triggered": {}, "last_weather_check": "", "active_queues": []}


def get_meal_period() -> str:
    h = datetime.now().hour
    if 7 <= h < 9: return "breakfast"
    if 11 <= h < 13: return "lunch"
    if 17 <= h < 19: return "dinner"
    if 21 <= h < 23: return "latenight"
    return ""


@app.get("/api/heartbeat/status")
def heartbeat_status():
    period = get_meal_period()
    w = get_weather_state()
    events = get_recent_events(5)
    return {
        "current_time": datetime.now().isoformat(),
        "meal_period": period or "idle",
        "weather": f"{w.get('condition','')} {w.get('temperature','')}°C",
        "active_queues": len(_heartbeat_state["active_queues"]),
        "recent_events": len(events),
        "monitors": {
            "meal": period != "",
            "queue": len(_heartbeat_state["active_queues"]) > 0,
            "weather": _heartbeat_state["last_weather_check"] == str(datetime.now().date()),
        },
    }


# ═══════════════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════════════

import threading
import queue as _sync_queue

# 线程安全队列(供心跳线程向SSE推送)
_sse_queue = _sync_queue.Queue()


def _heartbeat_loop():
    """后台心跳线程: 每30秒检查是否需要主动推送"""
    import time as _time
    while True:
        _time.sleep(30)
        try:
            period = get_meal_period()
            today = str(datetime.now().date())
            if period:
                key = f"{today}_{period}"
                if key not in _heartbeat_state["meal_triggered"]:
                    _heartbeat_state["meal_triggered"][key] = True
                    names = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "latenight": "夜宵"}
                    _sse_queue.put({"type": "heartbeat_meal", "timestamp": datetime.now().isoformat(),
                                     "data": {"period": period, "message": f"⏰ {names[period]}时间到！可触发 dining-advisor 推荐餐厅"}})
            if _heartbeat_state["last_weather_check"] != today:
                _heartbeat_state["last_weather_check"] = today
                refresh_cache()  # 新的一天，刷新prompt缓存(时间戳已变化)
                w = get_weather_state()
                if datetime.now().weekday() >= 5:
                    _sse_queue.put({"type": "heartbeat_weather", "timestamp": datetime.now().isoformat(),
                                     "data": {"message": f"🌤️ 周末好天气！{w['condition']} {w['temperature']}°C，可触发 leisure-scout"}})
        except Exception:
            pass


def _on_watch_triggered(task):
    """Watchdog 触发回调: 推送到SSE + 异步触发LLM推理。"""
    import asyncio
    _sse_queue.put({
        "type": "watch_triggered_raw",
        "timestamp": datetime.now().isoformat(),
        "data": {"task_id": task.id, "target_name": task.target_name, "condition": task.condition}
    })
    # 触发LLM推理
    session = get_or_create_session(task.session_id)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        reply = loop.run_until_complete(session.trigger_watch(task))
        _sse_queue.put({
            "type": "watch_triggered",
            "timestamp": datetime.now().isoformat(),
            "data": {"task_id": task.id, "target_name": task.target_name, "reply": reply}
        })
    except Exception as e:
        _sse_queue.put({
            "type": "watch_error",
            "timestamp": datetime.now().isoformat(),
            "data": {"task_id": task.id, "error": str(e)}
        })


def _on_proactive_notify(message: str):
    """ProactiveBrain 主动通知回调: 推送到SSE。"""
    _sse_queue.put({
        "type": "watch_triggered",
        "timestamp": datetime.now().isoformat(),
        "data": {"task_id": "proactive", "target_name": "环境变化", "reply": message}
    })


if __name__ == "__main__":
    start_tick_loop(interval=30.0)
    t = threading.Thread(target=_heartbeat_loop, daemon=True)
    t.start()
    start_watchdog_loop(interval=15.0, on_trigger=_on_watch_triggered)
    start_proactive_loop(interval=30.0, on_notify=_on_proactive_notify)
    import sys
    banner = f"""
╔══════════════════════════════════════════════╗
║   SuiXing - Local Life Butler Demo Server   ║
╠══════════════════════════════════════════════╣
║  Web UI:    http://{HOST}:{PORT}           ║
║  SSE:       http://{HOST}:{PORT}/api/events ║
║  Health:    http://{HOST}:{PORT}/api/health ║
║  Watch:     http://{HOST}:{PORT}/api/watch/list ║
║  Heartbeat: http://{HOST}:{PORT}/api/heartbeat/status ║
╚══════════════════════════════════════════════╝
"""
    sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None
    print(banner)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
