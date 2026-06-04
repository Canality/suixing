#!/usr/bin/env python3
"""Feishu IM Bot — 飞书消息推送模块（多卡片类型 + Webhook/API双模式）。

Card types: dining, queue, commute, leisure
Modes: webhook (demo), api (production), dry-run (print card JSON)

Usage:
  python feishu_bot.py --mode webhook --webhook-url "https://..." --card-type dining --card-data-file data.json
  python feishu_bot.py --mode dry-run --card-type queue --card-data-file data.json
"""

import json
import argparse
import urllib.request
import urllib.error
import os
from datetime import datetime


# ── Webhook Mode ──────────────────────────────────────────────

def send_webhook_text(webhook_url: str, text: str) -> dict:
    body = json.dumps({"msg_type": "text", "content": {"text": text}}, ensure_ascii=False)
    req = urllib.request.Request(
        webhook_url, data=body.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": True, "status": resp.status,
                    "body": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8")}


def send_webhook_card(webhook_url: str, card: dict) -> dict:
    body = json.dumps({"msg_type": "interactive", "card": card}, ensure_ascii=False)
    req = urllib.request.Request(
        webhook_url, data=body.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": True, "status": resp.status,
                    "body": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8")}


# ── API Mode ──────────────────────────────────────────────────

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": app_id, "app_secret": app_secret})
    req = urllib.request.Request(
        url, data=body.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get token: {data}")
    return data["tenant_access_token"]


def send_api_message(token: str, receive_id_type: str, receive_id: str,
                     msg_type: str, content: str) -> dict:
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = f"?receive_id_type={receive_id_type}"
    body = json.dumps({
        "receive_id": receive_id, "msg_type": msg_type, "content": content
    }, ensure_ascii=False)
    req = urllib.request.Request(
        url + params, data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": True, "status": resp.status,
                    "body": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8")}


# ── Card: 主动问候 ─────────────────────────────────────────────

def build_travel_greeting_card(holiday: dict, user_profile: dict) -> dict:
    name = holiday["name"]
    start = holiday["start"]
    end = holiday["end"]
    days = holiday["days"]
    days_until = holiday.get("days_until", "?")
    home = user_profile.get("home_city", "你的城市")
    budget = user_profile.get("budget_preference", {}).get("short_break", {})
    budget_str = f"¥{budget.get('min', 1500)}-{budget.get('max', 3500)}"

    return {
        "header": {
            "title": {"tag": "plain_text", "content": f" {name}出行提醒"},
            "template": "wathet"
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md",
                         "content": f"**{name}** 就要到啦！ {start} - {end}（{days}天假期）\n\n"
                                    f"还有 **{days_until} 天**，想去哪里走走吗？"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md",
                         "content": f" 出发城市：**{home}**\n"
                                    f" 预算参考：**{budget_str}**（根据你的偏好）\n"
                                    f" 我帮你推荐几个热门目的地？"}
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": " 帮我推荐"},
                        "type": "primary",
                        "value": json.dumps({"action": "start_planning", "holiday": name},
                                            ensure_ascii=False)
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": " 暂时不去"},
                        "type": "default",
                        "value": json.dumps({"action": "decline", "holiday": name},
                                            ensure_ascii=False)
                    }
                ]
            },
            {
                "tag": "note",
                "elements": [{"tag": "plain_text",
                              "content": f" 美团AI旅行管家 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}]
            }
        ]
    }


# ── Card: 规划提醒 ─────────────────────────────────────────────

def build_planning_reminder_card(holiday: dict, last_updated: str) -> dict:
    name = holiday["name"]
    return {
        "header": {
            "title": {"tag": "plain_text", "content": f" {name}出行方案还没定完哦"},
            "template": "yellow"
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md",
                         "content": f"上次我们在 **{last_updated}** 聊了{name}的出行方案，"
                                    f"但还没确定下来。\n\n要不要继续？之前的偏好我都记着呢。"}
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": " 继续规划"},
                        "type": "primary",
                        "value": json.dumps({"action": "resume_planning", "holiday": name},
                                            ensure_ascii=False)
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": " 再说吧"},
                        "type": "default",
                        "value": json.dumps({"action": "decline", "holiday": name},
                                            ensure_ascii=False)
                    }
                ]
            }
        ]
    }


# ── Card: 行程单 ───────────────────────────────────────────────

def build_itinerary_card(selection: dict) -> dict:
    city = selection.get("city_name", "")
    transport = selection.get("transport", {})
    hotel = selection.get("hotel", {})
    budget = selection.get("budget", {})
    attractions = selection.get("attractions", [])[:5]

    att_lines_parts = []
    for a in attractions[:4]:
        price_str = "免费" if a.get("price", 0) == 0 else f"¥{a['price']}"
        att_lines_parts.append(f"• {a['name']}（{price_str}）⭐{a.get('rating', '?')}")
    att_lines = "\n".join(att_lines_parts)

    return {
        "header": {
            "title": {"tag": "plain_text",
                      "content": f" {city}{selection.get('duration_days', 3)}日行程单"},
            "template": "turquoise"
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md",
                         "content": f"📅 **{selection.get('date_start', '')} - {selection.get('date_end', '')}**\n"
                                    f"🚄 {transport.get('id', '')} {transport.get('from', '')}→{transport.get('to', '')} "
                                    f"¥{transport.get('price', 0)} | "
                                    f"🏨 {hotel.get('name', '')} ¥{hotel.get('price_per_night', 0)}/晚"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**景点安排：**\n{att_lines}"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md",
                         "content": f"💰 预算：**¥{budget.get('total', 0)}**\n"
                                    f"   🚄交通 ¥{budget.get('transport_roundtrip', 0)} + "
                                    f"🏨住宿 ¥{budget.get('hotel_total', 0)} + "
                                    f"🎫景点 ¥{budget.get('attractions', 0)}"}
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": " 确认预订"},
                        "type": "primary",
                        "value": json.dumps({"action": "confirm_booking", "city": city},
                                            ensure_ascii=False)
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": " 换一个方案"},
                        "type": "default",
                        "value": json.dumps({"action": "change_plan"}, ensure_ascii=False)
                    }
                ]
            },
            {
                "tag": "note",
                "elements": [{"tag": "plain_text",
                              "content": " 价格以官方平台实时显示为准 | 美团AI旅行管家"}]
            }
        ]
    }


# ── Card: 方案对比 ─────────────────────────────────────────────

def build_comparison_card(cities: list, preference: dict) -> dict:
    emoji_map = {"海边度假": "🏖️", "人文美食+海景": "🏯", "北方海滨": "🌊",
                 "美食休闲": "🍜", "自然风光": "🏔️", "温泉": "♨️"}

    city_blocks = []
    for i, city in enumerate(cities[:3]):
        emoji = emoji_map.get(city.get("city_type", ""), "📍")
        budget = city.get("budget_estimate", {})
        conf = city.get("confidence", {})
        conf_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(conf.get("color"), "⚪")
        hotel_range = budget.get("hotel_per_night_range", [0])

        city_blocks.append({
            "tag": "div",
            "text": {"tag": "lark_md",
                     "content": f"{emoji} **{city['city_name']}** "
                                f"¥{budget.get('budget_recommended', 0)} "
                                f"{conf_emoji}\n"
                                f"{city.get('city_type', '')} | "
                                f"🚄 ¥{budget.get('transport_roundtrip', 0)}往返 | "
                                f"🏨 ¥{hotel_range[0]}起/晚"}
        })
        if i < len(cities) - 1:
            city_blocks.append({"tag": "hr"})

    dest_type = preference.get("destination_type", "")

    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md",
                     "content": f"根据你的偏好（{dest_type}，预算 ¥{preference.get('budget', 0)}），"
                                f"为你找到 **{len(cities)} 个** 合适的目的地："}
        },
        {"tag": "hr"},
    ] + city_blocks + [
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {"tag": "lark_md",
                     "content": "⚠️ 价格仅供参考，以官方平台实时数据为准\n"
                                "💡 回复城市名即可选择，或说「投票」发起群投票"}
        },
        {
            "tag": "note",
            "elements": [{"tag": "plain_text",
                          "content": f"信心指数: 🟢高 🟡中 🔴低 | {datetime.now().strftime('%Y-%m-%d %H:%M')}"}]
        }
    ]

    return {
        "header": {
            "title": {"tag": "plain_text", "content": " 目的地推荐对比"},
            "template": "blue"
        },
        "elements": elements
    }


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Feishu Bot — 飞书消息推送（多卡片）")
    parser.add_argument("--mode", choices=["webhook", "api"], default="webhook")
    parser.add_argument("--webhook-url", help="飞书机器人 Webhook 地址")
    parser.add_argument("--app-id", help="飞书 App ID (API mode)")
    parser.add_argument("--app-secret", help="飞书 App Secret (API mode)")
    parser.add_argument("--receive-id-type", choices=["open_id", "user_id", "chat_id"],
                        default="open_id")
    parser.add_argument("--receive-id", help="接收者 ID (API mode)")
    parser.add_argument("--message", help="纯文本消息内容")
    parser.add_argument("--card-file", help="卡片 JSON 文件路径")
    parser.add_argument("--card-type",
                        choices=["greeting", "reminder", "itinerary", "comparison"])
    parser.add_argument("--card-data-file",
                        help="JSON data file for itinerary/comparison cards")
    parser.add_argument("--holiday-name", default="端午节")
    parser.add_argument("--holiday-start", default="2026-06-19")
    parser.add_argument("--holiday-end", default="2026-06-21")
    parser.add_argument("--holiday-days", type=int, default=3)
    parser.add_argument("--days-until", type=int, default=0)
    parser.add_argument("--last-updated", default="")
    args = parser.parse_args()

    if args.card_type:
        holiday = {
            "name": args.holiday_name,
            "start": args.holiday_start,
            "end": args.holiday_end,
            "days": args.holiday_days,
            "days_until": args.days_until
        }
        if args.card_type == "greeting":
            card = build_travel_greeting_card(holiday, {})
        elif args.card_type == "reminder":
            card = build_planning_reminder_card(holiday, args.last_updated or "前几天")
        elif args.card_type in ("itinerary", "comparison"):
            if not args.card_data_file:
                print(json.dumps(
                    {"ok": False, "error": f"--card-type {args.card_type} requires --card-data-file"},
                    ensure_ascii=False))
                return
            with open(args.card_data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if args.card_type == "itinerary":
                card = build_itinerary_card(data)
            else:
                card = build_comparison_card(data.get("cities", []),
                                              data.get("preference", {}))
        else:
            card = build_planning_reminder_card(holiday, args.last_updated or "前几天")

        result = send_webhook_card(args.webhook_url, card)
    elif args.card_file:
        with open(args.card_file, "r", encoding="utf-8") as f:
            card = json.load(f)
        result = send_webhook_card(args.webhook_url, card)
    elif args.message:
        result = send_webhook_text(args.webhook_url, args.message)
    else:
        parser.error("需要 --message, --card-file 或 --card-type")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
