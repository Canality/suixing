"""Mock数据生成器 — 本地生活沙盒的静态数据+动态状态。

包含: 33+商户(餐饮/出行/娱乐)、天气、活动、路线。
所有带 `_state` 后缀的变量是运行时动态变化的。
"""

import random
import time
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# 餐饮商户 (12家)
# ═══════════════════════════════════════════════════════════════

RESTAURANTS = [
    {
        "id": "r001", "name": "后院·川渝火锅(望京店)", "cuisine": "川渝火锅",
        "area": "望京", "address": "望京街9号万科时代中心B1",
        "avg_price": 120, "rating": 4.5, "distance_km": 1.2,
        "tags": ["火锅", "辣", "聚会", "排队热门"],
        "hours": "11:00-23:00",
        "recommendations": ["毛肚", "鲜鸭血", "手切羊肉", "冰粉"],
        "has_queue": True, "booking_type": "queue",
    },
    {
        "id": "r002", "name": "麻辣诱惑(望京凯德MALL店)", "cuisine": "川菜",
        "area": "望京", "address": "广顺北大街33号凯德MALL 4F",
        "avg_price": 85, "rating": 4.3, "distance_km": 0.8,
        "tags": ["川菜", "小炒", "午餐", "性价比"],
        "hours": "10:00-22:00",
        "recommendations": ["水煮鱼", "麻婆豆腐", "回锅肉", "担担面"],
        "has_queue": False, "booking_type": "table",
    },
    {
        "id": "r003", "name": "鮨鲜(将台路店)", "cuisine": "日料",
        "area": "酒仙桥", "address": "将台路甲2号",
        "avg_price": 180, "rating": 4.6, "distance_km": 2.1,
        "tags": ["日料", "刺身", "约会", "高端"],
        "hours": "11:30-14:00,17:30-22:00",
        "recommendations": ["三文鱼刺身", "鳗鱼饭", "天妇罗", "抹茶甜品"],
        "has_queue": True, "booking_type": "queue",
    },
    {
        "id": "r004", "name": "老北京涮肉(望京店)", "cuisine": "北京菜",
        "area": "望京", "address": "阜通西大街12号",
        "avg_price": 95, "rating": 4.4, "distance_km": 1.5,
        "tags": ["涮肉", "北京味", "铜锅", "聚餐"],
        "hours": "11:00-22:30",
        "recommendations": ["手切羊肉", "麻酱糖饼", "爆肚", "糖蒜"],
        "has_queue": True, "booking_type": "queue",
    },
    {
        "id": "r005", "name": "湘味人家(望京SOHO店)", "cuisine": "湘菜",
        "area": "望京", "address": "望京SOHO T1 B1层",
        "avg_price": 55, "rating": 4.1, "distance_km": 0.3,
        "tags": ["湘菜", "午餐", "快餐", "性价比"],
        "hours": "10:00-21:00",
        "recommendations": ["剁椒鱼头", "小炒肉", "酸豆角", "米粉"],
        "has_queue": False, "booking_type": "table",
    },
    {
        "id": "r006", "name": "南门涮肉(酒仙桥店)", "cuisine": "北京菜",
        "area": "酒仙桥", "address": "酒仙桥路18号",
        "avg_price": 100, "rating": 4.5, "distance_km": 2.3,
        "tags": ["涮肉", "老字号", "麻酱", "排队"],
        "hours": "11:00-23:00",
        "recommendations": ["羊上脑", "百叶", "烧饼", "糖蒜"],
        "has_queue": True, "booking_type": "queue",
    },
    {
        "id": "r007", "name": "鼎泰丰(颐堤港店)", "cuisine": "台湾菜",
        "area": "酒仙桥", "address": "酒仙桥路18号颐堤港2F",
        "avg_price": 130, "rating": 4.3, "distance_km": 2.5,
        "tags": ["小笼包", "精致", "家庭", "午餐"],
        "hours": "11:00-21:30",
        "recommendations": ["蟹粉小笼", "蛋炒饭", "红烧牛肉面", "豆沙小包"],
        "has_queue": True, "booking_type": "queue",
    },
    {
        "id": "r008", "name": "韩式烤肉王(望京店)", "cuisine": "韩国料理",
        "area": "望京", "address": "望京西园四区底商",
        "avg_price": 90, "rating": 4.2, "distance_km": 1.0,
        "tags": ["烤肉", "韩餐", "聚会", "夜宵"],
        "hours": "11:00-02:00",
        "recommendations": ["五花肉", "牛舌", "冷面", "烧酒"],
        "has_queue": False, "booking_type": "table",
    },
    {
        "id": "r009", "name": "绿茶餐厅(望京凯德MALL店)", "cuisine": "江浙菜",
        "area": "望京", "address": "广顺北大街33号凯德MALL 3F",
        "avg_price": 65, "rating": 4.0, "distance_km": 0.8,
        "tags": ["江浙菜", "性价比", "家庭", "清淡"],
        "hours": "10:30-21:30",
        "recommendations": ["面包诱惑", "绿茶烤鸡", "东坡肉", "石锅豆腐"],
        "has_queue": False, "booking_type": "table",
    },
    {
        "id": "r010", "name": "海底捞火锅(望京华彩店)", "cuisine": "火锅",
        "area": "望京", "address": "广顺北大街16号华彩商业中心3F",
        "avg_price": 130, "rating": 4.6, "distance_km": 1.8,
        "tags": ["火锅", "服务好", "聚会", "排队王"],
        "hours": "11:00-07:00(次日)",
        "recommendations": ["番茄锅底", "捞派牛肉", "虾滑", "抻面"],
        "has_queue": True, "booking_type": "queue",
    },
    {
        "id": "r011", "name": "沙县小吃(恒通商务园店)", "cuisine": "快餐",
        "area": "酒仙桥", "address": "酒仙桥路10号恒通商务园内",
        "avg_price": 20, "rating": 3.8, "distance_km": 2.8,
        "tags": ["快餐", "便宜", "午餐", "快捷"],
        "hours": "07:00-21:00",
        "recommendations": ["蒸饺", "馄饨", "拌面", "炖罐"],
        "has_queue": False, "booking_type": "walk_in",
    },
    {
        "id": "r012", "name": "胖妹面庄(望京店)", "cuisine": "重庆小面",
        "area": "望京", "address": "阜通东大街1号",
        "avg_price": 35, "rating": 4.4, "distance_km": 1.1,
        "tags": ["小面", "重庆", "辣", "快餐"],
        "hours": "07:30-22:00",
        "recommendations": ["豌杂面", "牛肉面", "红油抄手", "冰粉"],
        "has_queue": True, "booking_type": "queue",
    },
]

# ═══════════════════════════════════════════════════════════════
# 出行服务
# ═══════════════════════════════════════════════════════════════

RIDE_ROUTES = [
    # 望京 → 酒仙桥/恒通
    {"from": "望京SOHO", "to": "恒通商务园", "distance_km": 3.2, "duration_min": 15, "price_estimate": 22, "mode": "打车"},
    {"from": "望京SOHO", "to": "恒通商务园", "distance_km": 3.5, "duration_min": 20, "price_estimate": 1.5, "mode": "美团单车"},
    {"from": "望京SOHO", "to": "恒通商务园", "distance_km": 4.0, "duration_min": 18, "price_estimate": 4, "mode": "地铁15号线"},
    # 望京 → 三里屯
    {"from": "望京SOHO", "to": "三里屯太古里", "distance_km": 8.5, "duration_min": 30, "price_estimate": 45, "mode": "打车"},
    {"from": "望京SOHO", "to": "三里屯太古里", "distance_km": 9.0, "duration_min": 35, "price_estimate": 5, "mode": "地铁14号线→10号线"},
    # 望京 → 颐堤港
    {"from": "望京SOHO", "to": "颐堤港", "distance_km": 2.8, "duration_min": 12, "price_estimate": 18, "mode": "打车"},
    {"from": "望京SOHO", "to": "颐堤港", "distance_km": 3.0, "duration_min": 15, "price_estimate": 1.5, "mode": "美团单车"},
    # 望京 → 798
    {"from": "望京SOHO", "to": "798艺术区", "distance_km": 4.5, "duration_min": 20, "price_estimate": 28, "mode": "打车"},
    {"from": "望京SOHO", "to": "798艺术区", "distance_km": 5.0, "duration_min": 25, "price_estimate": 1.5, "mode": "美团单车"},
    # 望京 → 温榆河公园 (新增)
    {"from": "望京SOHO", "to": "温榆河公园", "distance_km": 6.5, "duration_min": 28, "price_estimate": 32, "mode": "打车"},
    {"from": "望京SOHO", "to": "温榆河公园", "distance_km": 7.0, "duration_min": 30, "price_estimate": 1.5, "mode": "美团单车"},
    # 望京 → 温榆河绿道 (骑行路线)
    {"from": "望京SOHO", "to": "温榆河绿道(来广营段)", "distance_km": 5.0, "duration_min": 22, "price_estimate": 1.5, "mode": "美团单车"},
    # 望京 → 望京凯德MALL
    {"from": "望京SOHO", "to": "望京凯德MALL", "distance_km": 1.2, "duration_min": 6, "price_estimate": 13, "mode": "打车"},
    {"from": "望京SOHO", "to": "望京凯德MALL", "distance_km": 1.0, "duration_min": 5, "price_estimate": 1.5, "mode": "美团单车"},
    # 望京 → 万达影城
    {"from": "望京SOHO", "to": "万达影城(望京店)", "distance_km": 1.5, "duration_min": 8, "price_estimate": 15, "mode": "打车"},
    {"from": "望京SOHO", "to": "万达影城(望京店)", "distance_km": 1.5, "duration_min": 8, "price_estimate": 1.5, "mode": "美团单车"},
    # 望京 → 笑果工厂(798)
    {"from": "望京SOHO", "to": "笑果工厂(798店)", "distance_km": 4.5, "duration_min": 20, "price_estimate": 28, "mode": "打车"},
    {"from": "望京SOHO", "to": "笑果工厂(798店)", "distance_km": 5.0, "duration_min": 25, "price_estimate": 1.5, "mode": "美团单车"},
    # 望京 → 奥林匹克森林公园 (常见骑行目的地)
    {"from": "望京SOHO", "to": "奥林匹克森林公园", "distance_km": 10.0, "duration_min": 40, "price_estimate": 1.5, "mode": "美团单车"},
    {"from": "望京SOHO", "to": "奥林匹克森林公园", "distance_km": 9.5, "duration_min": 28, "price_estimate": 38, "mode": "打车"},
    # 望京 → 望京体育公园
    {"from": "望京SOHO", "to": "望京体育公园", "distance_km": 2.0, "duration_min": 8, "price_estimate": 1.5, "mode": "美团单车"},
    {"from": "望京SOHO", "to": "望京体育公园", "distance_km": 2.0, "duration_min": 7, "price_estimate": 14, "mode": "打车"},
]

BIKE_STATIONS = [
    {"name": "望京SOHO T1", "bikes_available": 12, "area": "望京"},
    {"name": "望京地铁站A口", "bikes_available": 8, "area": "望京"},
    {"name": "恒通商务园", "bikes_available": 5, "area": "酒仙桥"},
    {"name": "将台地铁站", "bikes_available": 15, "area": "酒仙桥"},
    {"name": "颐堤港", "bikes_available": 10, "area": "酒仙桥"},
    {"name": "798艺术区", "bikes_available": 6, "area": "酒仙桥"},
]

# ═══════════════════════════════════════════════════════════════
# 娱乐活动 (8个)
# ═══════════════════════════════════════════════════════════════

ACTIVITIES = [
    {
        "id": "a001", "name": "《流浪地球3》IMAX", "category": "电影",
        "venue": "万达影城(望京店)", "area": "望京", "distance_km": 1.0,
        "price": 65, "rating": 4.6,
        "times": ["13:30", "16:00", "19:30", "21:00"],
        "tags": ["科幻", "IMAX", "热门"],
    },
    {
        "id": "a002", "name": "《封神第二部》", "category": "电影",
        "venue": "CGV影城(颐堤港店)", "area": "酒仙桥", "distance_km": 2.5,
        "price": 55, "rating": 4.3,
        "times": ["14:00", "18:00", "20:30"],
        "tags": ["神话", "特效", "IMAX"],
    },
    {
        "id": "a003", "name": "UCCA·现代艺术展「边界」", "category": "展览",
        "venue": "UCCA尤伦斯当代艺术中心", "area": "798", "distance_km": 4.5,
        "price": 100, "rating": 4.4,
        "date_range": "2026-05-15 ~ 2026-07-15",
        "tags": ["当代艺术", "沉浸式", "打卡"],
    },
    {
        "id": "a004", "name": "温榆河骑行道", "category": "户外",
        "venue": "温榆河公园", "area": "朝阳", "distance_km": 5.0,
        "price": 0, "rating": 4.5,
        "duration_hours": 3, "difficulty": "轻松",
        "tags": ["骑行", "户外", "免费", "自然"],
    },
    {
        "id": "a005", "name": "周末羽毛球局", "category": "运动",
        "venue": "望京体育公园羽毛球馆", "area": "望京", "distance_km": 1.5,
        "price": 40, "rating": 4.1,
        "duration_hours": 2,
        "tags": ["运动", "羽毛球", "社交"],
    },
    {
        "id": "a006", "name": "脱口秀开放麦", "category": "演出",
        "venue": "笑果工厂(798店)", "area": "798", "distance_km": 4.5,
        "price": 80, "rating": 4.2,
        "times": ["19:30", "21:00"],
        "tags": ["脱口秀", "喜剧", "约会"],
    },
    {
        "id": "a007", "name": "望京SOHO天台市集", "category": "市集",
        "venue": "望京SOHO天台", "area": "望京", "distance_km": 0.3,
        "price": 0, "rating": 4.0,
        "date_range": "2026-06-05 ~ 2026-06-07",
        "tags": ["市集", "美食", "手作", "周末"],
    },
    {
        "id": "a008", "name": "密室逃脱·长安十二时辰", "category": "密室",
        "venue": "Xcape异时刻(望京店)", "area": "望京", "distance_km": 1.3,
        "price": 168, "rating": 4.7,
        "duration_hours": 2,
        "tags": ["密室", "沉浸式", "聚会", "热门"],
    },
]

# ═══════════════════════════════════════════════════════════════
# 天气模板
# ═══════════════════════════════════════════════════════════════

WEATHER_CONDITIONS = ["晴", "晴转多云", "多云", "阴", "小雨", "中雨", "雷阵雨", "多云转晴"]

# ═══════════════════════════════════════════════════════════════
# 动态状态 (运行时变化)
# ═══════════════════════════════════════════════════════════════

def init_restaurant_state():
    """初始化餐厅动态状态。"""
    state = {}
    for r in RESTAURANTS:
        if r["has_queue"]:
            queue_len = random.randint(0, 20)
            state[r["id"]] = {
                "queue_length": queue_len,
                "wait_minutes": queue_len * 2 + random.randint(-5, 5) if queue_len > 0 else 0,
                "available_tables": random.randint(0, 5),
                "is_open": True,
                "daily_specials": random.sample(r["recommendations"], min(2, len(r["recommendations"]))),
                "last_updated": datetime.now().isoformat(),
            }
        else:
            state[r["id"]] = {
                "queue_length": 0,
                "wait_minutes": 0,
                "available_tables": random.randint(1, 8),
                "is_open": True,
                "daily_specials": [],
                "last_updated": datetime.now().isoformat(),
            }
    return state

def init_weather_state():
    """初始化天气动态状态(含分时段预告)。"""
    return {
        "temperature": random.randint(20, 32),
        "condition": random.choice(WEATHER_CONDITIONS),
        # 分时段预告: LLM 根据用户计划的时间段来监控对应 slot
        "forecast": {
            "afternoon": random.choice(WEATHER_CONDITIONS),    # 12:00-18:00
            "evening": random.choice(WEATHER_CONDITIONS),       # 18:00-22:00
            "night": random.choice(WEATHER_CONDITIONS),         # 22:00-06:00
            "tomorrow_morning": random.choice(WEATHER_CONDITIONS),  # 次日06:00-12:00
            "tomorrow_afternoon": random.choice(WEATHER_CONDITIONS),
            "tomorrow_evening": random.choice(WEATHER_CONDITIONS),
        },
        "humidity": random.randint(30, 80),
        "wind": f"{random.choice(['东北','东南','西北','西南'])}风{random.randint(2,5)}级",
        "aqi": random.randint(30, 120),
        "updated_at": datetime.now().isoformat(),
    }

def init_activity_state():
    """初始化活动动态状态。"""
    state = {}
    for a in ACTIVITIES:
        state[a["id"]] = {
            "status": random.choice(["available", "available", "available", "available", "sold_out"]),
            "discount": random.choice([0, 0, 0, 0, 10, 20, 30]),
            "last_updated": datetime.now().isoformat(),
        }
    return state

def init_bike_state():
    """初始化单车动态状态。"""
    state = {}
    for b in BIKE_STATIONS:
        state[b["name"]] = {
            "bikes_available": random.randint(0, b["bikes_available"] + 5),
        }
    return state


# ═══════════════════════════════════════════════════════════════
# 场所/基础设施状态 (影院/地铁/健身房等, 运行时可能关闭/故障)
# ═══════════════════════════════════════════════════════════════

VENUE_STATUS_TEMPLATES = {
    "万达影城(望京店)":     {"type": "cinema",  "status": "open", "area": "望京"},
    "CGV影城(颐堤港店)":    {"type": "cinema",  "status": "open", "area": "酒仙桥"},
    "UCCA尤伦斯当代艺术中心": {"type": "gallery", "status": "open", "area": "798"},
    "笑果工厂(798店)":      {"type": "theater", "status": "open", "area": "798"},
    "望京体育公园羽毛球馆":   {"type": "gym",     "status": "open", "area": "望京"},
    "温榆河公园":            {"type": "park",    "status": "open", "area": "朝阳"},
    "Xcape异时刻(望京店)":   {"type": "escape",  "status": "open", "area": "望京"},
    "望京SOHO天台":          {"type": "market",  "status": "open", "area": "望京"},
    "地铁15号线":            {"type": "subway",  "status": "normal", "area": "望京"},
    "美团单车(望京区域)":     {"type": "bike_service", "status": "normal", "area": "望京"},
}

_venue_state: dict[str, dict] = {}


def init_venue_state():
    """初始化场所动态状态。"""
    global _venue_state
    _venue_state = {k: dict(v) for k, v in VENUE_STATUS_TEMPLATES.items()}
    return _venue_state


def get_venue_state():
    return _venue_state


# 全局动态状态(服务启动时初始化,运行时持续变化)
_restaurant_state = init_restaurant_state()
_weather_state = init_weather_state()
_activity_state = init_activity_state()
_bike_state = init_bike_state()
_venue_state = init_venue_state()

def get_restaurant_state(): return _restaurant_state
def get_weather_state(): return _weather_state
def get_activity_state(): return _activity_state
def get_bike_state(): return _bike_state
def get_venue_state(): return _venue_state
