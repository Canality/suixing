"""FastAPI 动态模拟沙盒 — 本地生活服务Mock后端。

启动: python app.py [--port 8010]
端点:
  GET  /api/restaurants          — 搜索餐厅(动态排队+空位)
  GET  /api/restaurants/{id}     — 餐厅详情
  GET  /api/restaurants/{id}/queue — 查询排队状态
  POST /api/restaurants/{id}/queue — 取号排队
  GET  /api/weather              — 当前天气
  GET  /api/activities           — 活动搜索
  GET  /api/activities/{id}      — 活动详情
  POST /api/route                — 路径规划
  POST /api/ride/estimate        — 打车预估
  GET  /api/bikes                — 单车站点
  GET  /api/events/random        — 随机事件
  GET  /api/health               — 健康检查
"""

import random
import argparse
from datetime import datetime

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from mock_data import (
    RESTAURANTS, ACTIVITIES, RIDE_ROUTES, BIKE_STATIONS,
    get_restaurant_state, get_weather_state, get_activity_state, get_bike_state,
)
from event_engine import start_tick_loop, get_recent_events

app = FastAPI(title="SuiXing Mock Backend", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ═══════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════

class RouteRequest(BaseModel):
    origin: str
    destination: str

class RideEstimateRequest(BaseModel):
    origin: str
    destination: str
    mode: str = "打车"  # 打车 | 单车 | 地铁


# ═══════════════════════════════════════════════════════════════
# 餐饮 API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/restaurants")
def search_restaurants(
    area: str = Query(None, description="区域: 望京/酒仙桥"),
    cuisine: str = Query(None, description="菜系"),
    min_rating: float = Query(None, description="最低评分"),
    max_price: int = Query(None, description="最高人均"),
    tags: str = Query(None, description="标签(逗号分隔)"),
    limit: int = Query(10, le=20),
):
    """搜索餐厅，返回实时动态数据。"""
    results = []
    rstate = get_restaurant_state()

    for r in RESTAURANTS:
        # 筛选
        if area and r["area"] != area:
            continue
        if cuisine and cuisine not in r["cuisine"]:
            continue
        if min_rating and r["rating"] < min_rating:
            continue
        if max_price and r["avg_price"] > max_price:
            continue
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            if not any(t in r["tags"] for t in tag_list):
                continue

        # 合并动态状态
        dyn = rstate.get(r["id"], {})
        result = {**r, **dyn}
        # 计算匹配分数(基于距离+评分)
        result["match_score"] = round(
            max(0, 5 - r["distance_km"]) * 0.3 + r["rating"] * 0.5 + (0.2 if not dyn.get("queue_length", 0) else 0), 2
        )
        results.append(result)

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return {
        "total": len(results),
        "results": results[:limit],
        "query": {"area": area, "cuisine": cuisine},
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/restaurants/{restaurant_id}")
def restaurant_detail(restaurant_id: str):
    """获取餐厅详情。"""
    r = next((x for x in RESTAURANTS if x["id"] == restaurant_id), None)
    if not r:
        raise HTTPException(status_code=404, detail="餐厅不存在")
    dyn = get_restaurant_state().get(restaurant_id, {})
    return {**r, **dyn}


@app.get("/api/restaurants/{restaurant_id}/queue")
def query_queue(restaurant_id: str):
    """查询排队状态。"""
    r = next((x for x in RESTAURANTS if x["id"] == restaurant_id), None)
    if not r:
        raise HTTPException(status_code=404, detail="餐厅不存在")
    dyn = get_restaurant_state().get(restaurant_id, {})
    return {
        "restaurant_id": restaurant_id,
        "restaurant_name": r["name"],
        "has_queue": r["has_queue"],
        "queue_length": dyn.get("queue_length", 0),
        "wait_minutes": dyn.get("wait_minutes", 0),
        "available_tables": dyn.get("available_tables", 0),
        "is_open": dyn.get("is_open", True),
        "updated_at": dyn.get("last_updated", ""),
    }


@app.post("/api/restaurants/{restaurant_id}/queue")
def take_queue(restaurant_id: str):
    """取号排队。"""
    r = next((x for x in RESTAURANTS if x["id"] == restaurant_id), None)
    if not r:
        raise HTTPException(status_code=404, detail="餐厅不存在")
    if not r["has_queue"]:
        return {"ok": False, "message": f"{r['name']}无需排队，直接入座即可"}

    dyn = get_restaurant_state().get(restaurant_id, {})
    if not dyn.get("is_open", True):
        return {"ok": False, "message": f"{r['name']}已休息"}

    queue_num = f"{r['id'].upper()}{random.randint(100, 999)}"
    return {
        "ok": True,
        "restaurant_name": r["name"],
        "queue_number": queue_num,
        "ahead_count": dyn.get("queue_length", 0),
        "estimated_wait_min": dyn.get("wait_minutes", 15),
        "message": f"取号成功！您的排队号是 {queue_num}，前面还有 {dyn.get('queue_length', 0)} 桌，预计等待 {dyn.get('wait_minutes', 15)} 分钟",
    }


# ═══════════════════════════════════════════════════════════════
# 天气 API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/weather")
def get_weather():
    """获取当前天气(动态)。"""
    w = get_weather_state()
    # 生成活动建议
    activity_tip = ""
    if "雨" in w["condition"]:
        activity_tip = "有雨，建议室内活动。附近电影院和密室逃脱是不错的选择"
    elif w["temperature"] > 32:
        activity_tip = "天气较热，推荐室内商场或傍晚骑行"
    elif w["temperature"] < 18:
        activity_tip = "偏凉，火锅或温泉好时机"
    elif w["aqi"] < 50:
        activity_tip = "空气质量优秀，强烈推荐户外骑行或公园散步"
    else:
        activity_tip = "天气不错，适合外出活动"

    return {**w, "activity_tip": activity_tip}


# ═══════════════════════════════════════════════════════════════
# 活动 API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/activities")
def search_activities(
    category: str = Query(None, description="类别: 电影/展览/户外/运动/演出/市集/密室"),
    area: str = Query(None),
    max_price: int = Query(None),
    limit: int = Query(10, le=20),
):
    """搜索活动。"""
    results = []
    astate = get_activity_state()

    for a in ACTIVITIES:
        if category and a["category"] != category:
            continue
        if area and a.get("area") != area:
            continue
        if max_price is not None and a["price"] > max_price:
            continue

        dyn = astate.get(a["id"], {})
        result = {**a, **dyn}
        results.append(result)

    results.sort(key=lambda x: x["rating"], reverse=True)
    return {
        "total": len(results),
        "results": results[:limit],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/activities/{activity_id}")
def activity_detail(activity_id: str):
    """获取活动详情。"""
    a = next((x for x in ACTIVITIES if x["id"] == activity_id), None)
    if not a:
        raise HTTPException(status_code=404, detail="活动不存在")
    dyn = get_activity_state().get(activity_id, {})
    return {**a, **dyn}


# ═══════════════════════════════════════════════════════════════
# 出行 API
# ═══════════════════════════════════════════════════════════════

@app.post("/api/route")
def plan_route(req: RouteRequest):
    """路径规划。"""
    routes = [r for r in RIDE_ROUTES if req.origin in r["from"] and req.destination in r["to"]]
    if not routes:
        # 模糊匹配
        routes = [r for r in RIDE_ROUTES if req.destination in r["to"] or req.origin in r["from"]]

    # 添加实时路况(模拟)
    results = []
    for r in routes:
        traffic_mult = random.choice([0.9, 1.0, 1.0, 1.0, 1.2])  # 80%正常, 20%微拥堵
        result = {**r}
        result["duration_min"] = round(r["duration_min"] * traffic_mult)
        result["traffic"] = "畅通" if traffic_mult < 0.95 else ("拥堵" if traffic_mult > 1.1 else "正常")
        result["price_estimate"] = round(r["price_estimate"] * (1 + random.uniform(-0.1, 0.2)), 1)
        results.append(result)

    results.sort(key=lambda x: x["duration_min"])
    return {
        "origin": req.origin,
        "destination": req.destination,
        "routes": results,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/ride/estimate")
def estimate_ride(req: RideEstimateRequest):
    """打车/单车预估。"""
    route = next((r for r in RIDE_ROUTES
                  if req.origin in r["from"] and req.destination in r["to"] and r["mode"] == req.mode), None)
    if not route:
        return {"ok": False, "message": "未找到匹配路线"}

    surge = random.choice([1.0, 1.0, 1.0, 1.0, 1.5])  # 20%概率动态加价
    wait_time = random.randint(1, 8)

    return {
        "ok": True,
        "mode": req.mode,
        "origin": req.origin,
        "destination": req.destination,
        "distance_km": route["distance_km"],
        "duration_min": route["duration_min"],
        "price_estimate": round(route["price_estimate"] * surge, 1),
        "surge": surge > 1.0,
        "wait_min": wait_time,
        "message": f"{req.mode}: ¥{round(route['price_estimate'] * surge, 1)}, 预计{route['duration_min']}分钟, 等待{wait_time}分钟" + (" ⚡动态加价中" if surge > 1.0 else ""),
    }


@app.get("/api/bikes")
def get_bikes(area: str = Query(None)):
    """查询单车站点。"""
    bstate = get_bike_state()
    results = []
    for b in BIKE_STATIONS:
        if area and b["area"] != area:
            continue
        dyn = bstate.get(b["name"], {})
        results.append({**b, **dyn})

    results.sort(key=lambda x: x["bikes_available"], reverse=True)
    return {
        "total": len(results),
        "stations": results,
        "timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# 随机事件 API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/events/random")
def get_random_events(limit: int = Query(10, le=50)):
    """获取最近的随机事件。"""
    events = get_recent_events(limit)
    # 如果没有最近事件，生成一个即时事件
    if not events:
        r = random.choice(RESTAURANTS)
        event_types = [
            {"type": "queue_alert", "message": f"📊 {r['name']} 排队进度: 前面{random.randint(3,8)}桌, 预计{random.randint(10,25)}分钟"},
            {"type": "daily_special", "message": f"🔥 {r['name']} 今日特价: {random.choice(r['recommendations'])} 限时8折"},
            {"type": "new_open", "message": f"🆕 {r['name']} 新开放了露台座位"},
        ]
        events = [random.choice(event_types)]
    return {"events": events, "timestamp": datetime.now().isoformat()}


@app.get("/api/health")
def health():
    return {"ok": True, "timestamp": datetime.now().isoformat(), "service": "SuiXing Mock Backend"}


# ═══════════════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="SuiXing Mock Backend")
    parser.add_argument("--port", type=int, default=8010, help="服务端口")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    # 启动事件引擎(后台tick)
    start_tick_loop(interval=30.0)
    print(f"[SuiXing Mock] Event engine started (tick every 30s)")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
