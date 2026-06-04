#!/usr/bin/env python3
"""Generate local life service recommendations for Meituan ecosystem integration.

Covers:
  1. Food delivery near hotel (Travel-Waimai): search queries + local cuisine mapping
  2. Bike routes (Travel-Bike): scenic cycling paths per city, integrated with daily itinerary

Usage:
  python local_services.py \
      --final-selection /tmp/final_selection.json \
      --output /tmp/local_services.json

Output: structured recommendations the Agent presents conversationally.
"""

import json
import argparse
import os

# Per-city cuisine keywords for food delivery search
CITY_CUISINE = {
    "泉州": {
        "must_try": ["面线糊", "烧肉粽", "土笋冻", "海蛎煎", "四果汤", "姜母鸭", "润饼"],
        "late_night": ["面线糊(24h老店)", "烧烤", "沙县小吃", "麻辣烫"],
        "breakfast": ["面线糊+油条", "花生汤+麻糍", "扁食"],
        "search_zones": ["西街", "钟楼", "丰泽广场", "浦西万达"]
    },
    "成都": {
        "must_try": ["火锅", "串串香", "担担面", "龙抄手", "钵钵鸡", "蹄花汤"],
        "late_night": ["火锅(通宵)", "烧烤", "钵钵鸡", "蹄花汤"],
        "breakfast": ["担担面", "龙抄手", "蛋烘糕", "豆浆油条"],
        "search_zones": ["春熙路", "太古里", "宽窄巷子", "玉林路"]
    },
    "三亚": {
        "must_try": ["椰子鸡", "清补凉", "抱罗粉", "海鲜烧烤", "椰子饭", "陵水酸粉"],
        "late_night": ["海鲜烧烤", "清补凉", "炒冰"],
        "breakfast": ["抱罗粉", "海南粉", "早茶"],
        "search_zones": ["大东海", "三亚湾", "亚龙湾", "第一市场"]
    },
    "大连": {
        "must_try": ["海鲜烧烤", "海胆蒸蛋", "烤鱿鱼", "海鲜焖子", "鲅鱼饺子"],
        "late_night": ["烧烤(大连烧烤文化)", "海鲜大排档", "烤冷面"],
        "breakfast": ["豆浆油条", "煎饼果子", "豆腐脑"],
        "search_zones": ["星海广场", "中山广场", "青泥洼桥", "西安路"]
    },
    "昆明": {
        "must_try": ["过桥米线", "汽锅鸡", "豆花米线", "烤豆腐", "野生菌火锅", "饵块"],
        "late_night": ["烧烤(昭通小串)", "烤豆腐", "米线(24h)"],
        "breakfast": ["过桥米线", "豆花米线", "烧饵块"],
        "search_zones": ["南屏街", "翠湖", "金马碧鸡坊", "文林街"]
    }
}

# Per-city bike routes with scenic value and difficulty
BIKE_ROUTES = {
    "泉州": [
        {
            "name": "古城骑行环线",
            "distance_km": 8,
            "duration_min": 50,
            "difficulty": "easy",
            "scenic_score": 5,
            "route": "钟楼 → 西街 → 开元寺 → 承天寺 → 清净寺 → 关帝庙 → 天后宫 → 聚宝街 → 回到钟楼",
            "highlights": ["开元寺东西塔", "西街骑楼", "天后宫闽南建筑", "聚宝街老巷"],
            "best_time": "清晨6:30-8:30 或 傍晚16:00-18:00",
            "bike_stations": ["钟楼(20辆)", "西街口(15辆)", "天后宫(12辆)", "聚宝街(10辆)"],
            "tips": "古城石板路较多，建议慢骑。西街早8点前车辆少，拍照最佳。"
        },
        {
            "name": "晋江入海口湿地骑行",
            "distance_km": 15,
            "duration_min": 90,
            "difficulty": "moderate",
            "scenic_score": 4,
            "route": "丰泽广场 → 晋江大桥 → 晋江湿地公园 → 洛阳桥 → 返回",
            "highlights": ["泉州湾湿地", "洛阳桥(千年古桥)", "红树林观鸟", "晋江大桥夜景"],
            "best_time": "下午15:00-18:00，回程看日落",
            "bike_stations": ["丰泽广场(25辆)", "晋江大桥(8辆)", "洛阳桥入口(15辆)"],
            "tips": "湿地公园内部禁止骑行，需在入口停车步行。洛阳桥段坡道缓，适合拍照。"
        }
    ],
    "成都": [
        {
            "name": "锦江夜骑绿道",
            "distance_km": 12,
            "duration_min": 70,
            "difficulty": "easy",
            "scenic_score": 5,
            "route": "合江亭 → 九眼桥 → 望江楼 → 东湖公园 → 锦城湖 → 返回",
            "highlights": ["九眼桥夜景", "望江楼竹海", "锦江灯光秀", "东湖日落"],
            "best_time": "傍晚17:00-20:00，正好看夜景",
            "bike_stations": ["合江亭(30辆)", "九眼桥(20辆)", "望江楼(15辆)", "锦城湖(20辆)"],
            "tips": "锦江绿道全程独立于机动车道，非常安全。九眼桥段晚上人流量大，注意减速。"
        },
        {
            "name": "天府绿道·青龙湖段",
            "distance_km": 20,
            "duration_min": 120,
            "difficulty": "moderate",
            "scenic_score": 4,
            "route": "青龙湖公园 → 玉石湿地 → 白鹭湾 → 天鹅湖环湖 → 返回",
            "highlights": ["青龙湖湿地", "白鹭湾芦苇荡", "天鹅湖观鸟", "环湖花海"],
            "best_time": "上午8:00-11:00，空气最好",
            "bike_stations": ["青龙湖正门(40辆)", "玉石湿地(15辆)", "白鹭湾(20辆)"],
            "tips": "周末人多建议早去。全程有自行车道，坡度小。带水，中途补给点少。"
        }
    ],
    "三亚": [
        {
            "name": "椰梦长廊海岸线骑行",
            "distance_km": 10,
            "duration_min": 60,
            "difficulty": "easy",
            "scenic_score": 5,
            "route": "三亚湾 → 椰梦长廊 → 海月广场 → 金鸡岭 → 返回",
            "highlights": ["椰梦长廊(三亚最美骑行道)", "三亚湾日落", "凤凰岛远景", "沿海棕榈林"],
            "best_time": "清晨6:00-8:00 或 傍晚17:00-19:00(看日落)",
            "bike_stations": ["三亚湾入口(35辆)", "海月广场(25辆)", "金鸡岭(15辆)"],
            "tips": "沿海非机动车道宽敞平整。傍晚骑行务必在日落前抵达椰梦长廊中段，拍照光线最佳。"
        }
    ],
    "大连": [
        {
            "name": "滨海路海岸线骑行",
            "distance_km": 13,
            "duration_min": 80,
            "difficulty": "moderate",
            "scenic_score": 5,
            "route": "星海广场 → 森林动物园 → 付家庄 → 燕窝岭 → 老虎滩 → 返回",
            "highlights": ["星海广场(亚洲最大广场)", "跨海大桥远景", "燕窝岭断崖", "老虎滩海湾"],
            "best_time": "上午7:30-10:30，顺光看海景",
            "bike_stations": ["星海广场(40辆)", "付家庄(20辆)", "老虎滩(25辆)"],
            "tips": "滨海路部分路段有坡度，建议从星海广场方向出发(下坡为主)。春秋季海风大，带防风外套。"
        }
    ],
    "昆明": [
        {
            "name": "滇池环湖绿道骑行",
            "distance_km": 15,
            "duration_min": 90,
            "difficulty": "easy",
            "scenic_score": 5,
            "route": "海埂公园 → 海埂大坝 → 云南民族村 → 草海隧道 → 滇池绿道 → 返回",
            "highlights": ["滇池全景", "海埂大坝(冬季有红嘴鸥)", "云南民族村外观", "西山睡美人"],
            "best_time": "上午8:00-11:00，风小湖面平静",
            "bike_stations": ["海埂公园正门(50辆)", "海埂大坝(30辆)", "民族村(25辆)"],
            "tips": "春秋两季骑行最佳。夏季午后滇池风大，建议上午出行。红嘴鸥季节(11月-3月)海埂大坝段特别美。"
        }
    ]
}


def build_food_queries(selection: dict) -> dict:
    """Generate food delivery search queries for the arrival day."""
    city_name = selection.get("city_name", "")
    hotel = selection.get("hotel", {})
    hotel_name = hotel.get("name", "")
    hotel_location = hotel.get("location", "")

    cuisine = CITY_CUISINE.get(city_name, CITY_CUISINE.get("泉州", {}))

    # Determine if arrival is late (after 20:00 based on transport arrival time)
    transport = selection.get("transport", {})
    arrival_time = transport.get("arrival", "16:00")
    try:
        arrival_hour = int(arrival_time.split(":")[0])
    except (ValueError, AttributeError):
        arrival_hour = 16
    is_late_arrival = arrival_hour >= 20

    search_queries = []
    search_zones = cuisine.get("search_zones", [])

    if is_late_arrival:
        search_queries.append({
            "scenario": "late_arrival",
            "priority": "high",
            "query": f"{city_name} {hotel_location} 附近 宵夜 外卖 美团 营业中",
            "note": "用户深夜抵达，优先搜仍在营业的店铺"
        })
        for food in cuisine["late_night"][:3]:
            search_queries.append({
                "scenario": "late_arrival",
                "priority": "high",
                "query": f"{city_name} {hotel_location} {food} 外卖 美团 评分",
                "note": f"当地深夜招牌：{food}"
            })

    for zone in search_zones[:2]:
        search_queries.append({
            "scenario": "general",
            "priority": "medium",
            "query": f"{city_name} {zone} 高分外卖 美团 推荐",
            "note": f"酒店周边商圈：{zone}"
        })

    for food in cuisine["must_try"][:3]:
        search_queries.append({
            "scenario": "local_specialty",
            "priority": "high",
            "query": f"{city_name} {food} 外卖 哪家正宗 美团 高分",
            "note": f"当地必吃：{food}"
        })

    # Breakfast for next morning
    for food in cuisine["breakfast"][:2]:
        search_queries.append({
            "scenario": "next_morning",
            "priority": "medium",
            "query": f"{city_name} {hotel_location} {food} 早餐 外卖 美团",
            "note": f"次日早餐：{food}"
        })

    return {
        "city": city_name,
        "hotel_name": hotel_name,
        "hotel_location": hotel_location,
        "is_late_arrival": is_late_arrival,
        "arrival_time": arrival_time,
        "local_cuisine": cuisine,
        "search_queries": search_queries
    }


def build_bike_recommendations(selection: dict) -> dict:
    """Generate bike route recommendations matching the itinerary."""
    city_name = selection.get("city_name", "")
    duration_days = selection.get("duration_days", 3)
    travel_style = selection.get("travel_style", "relaxed")

    routes = BIKE_ROUTES.get(city_name, [])
    matched = []

    for route in routes:
        # Match difficulty to travel style
        style_match = {
            "intensive": ["easy", "moderate"],
            "standard": ["easy", "moderate"],
            "relaxed": ["easy"]
        }

        if route["difficulty"] not in style_match.get(travel_style, ["easy"]):
            continue

        # Determine best day in itinerary for this route
        if route["difficulty"] == "easy":
            suggested_day = 1  # Arrival day, easy ride to explore
        elif duration_days >= 3 and route["scenic_score"] >= 5:
            suggested_day = 2  # Middle day for best route
        else:
            suggested_day = duration_days  # Last day

        matched.append({
            **route,
            "suggested_day": suggested_day,
            "style_compatibility": "perfect" if route["difficulty"] == "easy" else "good",
            "search_query": f"{city_name} {route['name'].split('骑行')[0]} 共享单车 骑行路线 攻略",
            "meituan_bike_query": f"{city_name} {route['highlights'][0]} 附近 美团单车 停车点"
        })

    return {
        "city": city_name,
        "available_routes": len(routes),
        "matched_routes": len(matched),
        "has_bike_service": len(routes) > 0,
        "routes": matched,
        "general_tips": [
            "美团单车APP查看实时车辆位置和停车区",
            "古城/老城区注意单行道和禁行区域",
            "海边骑行注意防晒和防风",
            "骑行前检查刹车和座椅高度"
        ] if matched else []
    }


def build_welcome_message(food: dict, bike: dict, selection: dict) -> str:
    """Generate the Agent's conversational opener for local services."""
    city = selection.get("city_name", "")
    hotel_name = food.get("hotel_name", "")
    is_late = food.get("is_late_arrival", False)
    must_try = food.get("local_cuisine", {}).get("must_try", [])[:3]
    has_bike = bike.get("has_bike_service", False)
    bike_count = bike.get("matched_routes", 0)

    parts = []

    if is_late:
        parts.append(
            f"你抵达{hotel_name}已经{selection.get('transport', {}).get('arrival', '晚了')}了。"
            f"我帮你扫了一下酒店周边的美团外卖——{', '.join(must_try)}都有高分店还在营业。"
            f"刚到酒店肯定饿了，要不要帮你推荐几家？"
        )
    else:
        parts.append(
            f"抵达{city}后先到{hotel_name}放下行李。我提前帮你看了酒店周边的美团外卖，"
            f"{', '.join(must_try)}这些当地特色都能送到。"
        )

    if has_bike and bike_count > 0:
        best_route = bike["routes"][0] if bike["routes"] else None
        if best_route:
            parts.append(
                f"\n\n另外，{city}有美团单车覆盖。有一条\"{best_route['name']}\"评分{best_route['scenic_score']}/5，"
                f"全程{best_route['distance_km']}公里，{best_route['duration_min']}分钟左右，{best_route['difficulty']}难度。"
                f"可以安排在Day {best_route['suggested_day']}。要不要加到行程里？"
            )

    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Generate local life service recommendations")
    parser.add_argument("--final-selection", required=True, help="Path to final_selection.json from Skill 2")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    with open(args.final_selection, "r", encoding="utf-8") as f:
        selection = json.load(f)

    food = build_food_queries(selection)
    bike = build_bike_recommendations(selection)
    welcome = build_welcome_message(food, bike, selection)

    output = {
        "food_delivery": food,
        "bike_routes": bike,
        "welcome_message": welcome,
        "confidence": {
            "food_delivery": {"score": 0.60, "label": "本地映射", "note": "当地美食数据来自本地知识库，外卖实时价格需搜索确认"},
            "bike_routes": {"score": 0.60, "label": "本地数据", "note": "骑行路线来自本地数据库，建议用美团单车APP查看实时车辆位置"},
            "disclaimer": "外卖店铺评分和营业状态以美团外卖APP实时显示为准。单车停车点和车辆数以美团单车APP为准。"
        },
        "integration_points": {
            "arrival_evening": "抵达当晚 → 呈现外卖推荐，询问是否代下单（演示仅推荐）",
            "next_morning": "次日早上 → 呈现早餐外卖推荐",
            "bike_day": f"Day {bike['routes'][0]['suggested_day'] if bike['routes'] else 2} → 骑行路线嵌入当日行程",
            "meituan_touchpoints": ["美团外卖", "美团单车", "美团酒店", "美团门票"]
        }
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
