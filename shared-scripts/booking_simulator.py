#!/usr/bin/env python3
"""Simulate booking with combinatorial coupon optimization + savings reallocation.

Enhancements over v1:
  1. Combinatorial optimization: enumerates ALL valid coupon combos, not just 1/category
  2. Stacking rules: rate coupons apply after fixed coupons for max savings
  3. Savings reallocation: "省下的¥X正好够买YY门票"
  4. Alternative suggestions: budget-tight scenarios trigger trade-off proposals

Usage:
    python booking_simulator.py \\
        --selection-file /tmp/final_selection.json \\
        --coupons-file data/coupons.json \\
        --output /tmp/booking_confirmation.json
"""

import json
import argparse
import os
import random
import string
from datetime import datetime, date
from itertools import combinations, permutations


# ── Coupon Loading & Validation ────────────────────────────────

def load_coupons(coupons_file: str) -> list:
    if not coupons_file or not os.path.exists(coupons_file):
        return []
    with open(coupons_file, "r", encoding="utf-8") as f:
        return json.load(f)


def is_coupon_valid(c: dict, today: str) -> bool:
    if c.get("status") != "available":
        return False
    if today < c.get("valid_from", "") or today > c.get("valid_until", ""):
        return False
    return True


# ── Savings Calculator ─────────────────────────────────────────

def calc_savings(coupon: dict, amount: float) -> float:
    """Calculate savings for a single coupon against an amount."""
    if amount < coupon.get("min_amount", 0):
        return 0.0
    if coupon["discount_type"] == "fixed":
        return float(coupon.get("discount_amount", 0))
    elif coupon["discount_type"] == "rate":
        rate = coupon.get("discount_rate", 0)
        cap = coupon.get("discount_cap", float("inf"))
        return min(amount * rate, cap)
    return 0.0


def calc_combo_savings(coupons: list, amount: float) -> tuple:
    """Calculate total savings from a combination of coupons applied to an amount.

    Optimal ordering: fixed coupons first (reduce base), then rate coupons.
    Returns (total_savings, applied_coupons_with_savings).
    """
    if not coupons:
        return 0.0, []

    fixed_coupons = [c for c in coupons if c["discount_type"] == "fixed"]
    rate_coupons = [c for c in coupons if c["discount_type"] == "rate"]

    remaining = amount
    total_savings = 0.0
    applied = []

    # Apply fixed coupons first (each reduces the base for rate coupons)
    for c in fixed_coupons:
        if remaining >= c.get("min_amount", 0):
            s = float(c.get("discount_amount", 0))
            remaining -= s
            total_savings += s
            applied.append({
                "coupon_id": c.get("id", ""),
                "coupon_name": c.get("name", ""),
                "category": c.get("category", ""),
                "savings": round(s),
                "description": c.get("description", ""),
                "applied_to": c.get("category", ""),
                "discount_type": c.get("discount_type", ""),
            })

    # Then apply rate coupons on the reduced base
    for c in rate_coupons:
        if remaining >= c.get("min_amount", 0):
            rate = c.get("discount_rate", 0)
            cap = c.get("discount_cap", float("inf"))
            s = min(remaining * rate, cap)
            total_savings += s
            applied.append({
                "coupon_id": c.get("id", ""),
                "coupon_name": c.get("name", ""),
                "category": c.get("category", ""),
                "savings": round(s),
                "description": c.get("description", ""),
                "applied_to": c.get("category", ""),
                "discount_type": c.get("discount_type", ""),
            })

    return round(total_savings), applied


# ── Combinatorial Optimizer ────────────────────────────────────

def find_optimal_coupon_combo(selection: dict, coupons: list) -> dict:
    """Enumerate valid coupon combinations to find the one with max total savings.

    Rules:
      - Hotel/transport/attraction coupons apply only to their respective subtotals
      - General coupons apply to the grand total AFTER category coupons
      - Within each category, try all valid combinations (not just 1 best)
      - Two coupons of same discount_type+category may conflict (互斥)
    """
    today = date.today().isoformat()
    valid = [c for c in coupons if is_coupon_valid(c, today)]

    hotel = selection.get("hotel", {})
    transport = selection.get("transport", {})
    attractions = selection.get("attractions", [])
    duration = selection.get("duration_days", 3)

    hotel_total = hotel.get("price_per_night", 0) * (duration - 1)
    transport_total = transport.get("price", 0) * 2
    attractions_total = sum(a.get("price", 0) for a in attractions[:duration * 2])

    # Categorize coupons
    hotel_coupons = [c for c in valid if c["category"] == "hotel"]
    transport_coupons = [c for c in valid if c["category"] in ("transport_train", "transport_flight")]
    attraction_coupons = [c for c in valid if c["category"] == "attraction"]
    general_coupons = [c for c in valid if c["category"] == "general"]

    # Filter transport coupons by type
    t_type = transport.get("type", "")
    if t_type in ("high_speed_rail", "regular_train"):
        transport_coupons = [c for c in transport_coupons if c["category"] == "transport_train"]
    elif t_type == "flight":
        transport_coupons = [c for c in transport_coupons if c["category"] == "transport_flight"]

    # Best for each category via combinatorial search
    best_hotel = _best_combo(hotel_coupons, hotel_total)
    best_transport = _best_combo(transport_coupons, transport_total)
    best_attraction = _best_combo(attraction_coupons, attractions_total)

    category_total_savings = best_hotel[0] + best_transport[0] + best_attraction[0]
    category_applied = best_hotel[1] + best_transport[1] + best_attraction[1]

    # Apply general coupons on top of category-discounted total
    grand_after_category = (hotel_total + transport_total + attractions_total) - category_total_savings
    best_general = _best_combo(general_coupons, grand_after_category)

    total_savings = category_total_savings + best_general[0]
    all_applied = category_applied + best_general[1]

    # Build optimization report
    return {
        "all_applied": all_applied,
        "total_savings": total_savings,
        "breakdown": {
            "hotel": {"subtotal": hotel_total, "savings": best_hotel[0], "coupons": best_hotel[1]},
            "transport": {"subtotal": transport_total, "savings": best_transport[0], "coupons": best_transport[1]},
            "attraction": {"subtotal": attractions_total, "savings": best_attraction[0], "coupons": best_attraction[1]},
            "general": {"subtotal": grand_after_category, "savings": best_general[0], "coupons": best_general[1]},
        },
        "grand_total_before": hotel_total + transport_total + attractions_total,
        "grand_total_after": hotel_total + transport_total + attractions_total - total_savings,
        "optimization_method": "combinatorial_v2"
    }


def _best_combo(coupons: list, amount: float) -> tuple:
    """Find the best combination of coupons for a given amount.

    Tries all subsets up to size 4 (16 coupons max combos = 2^N).
    Returns (best_savings, best_applied_list).
    """
    if not coupons or amount <= 0:
        return 0.0, []

    best_savings = 0.0
    best_applied = []

    n = len(coupons)
    max_size = min(n, 4)  # practical limit

    for size in range(1, max_size + 1):
        for combo in combinations(coupons, size):
            # Try different orderings for rate vs fixed priority
            savings, applied = calc_combo_savings(list(combo), amount)
            if savings > best_savings:
                best_savings = savings
                best_applied = applied

    return best_savings, best_applied


# ── Savings Reallocation Narrative ─────────────────────────────

def generate_savings_narrative(optimization: dict, selection: dict) -> str:
    """Generate human-readable narrative about what the savings can buy."""
    total_savings = optimization["total_savings"]
    if total_savings <= 0:
        return ""

    attractions = selection.get("attractions", [])
    free_attractions = [a for a in attractions if a.get("price", 0) == 0]
    paid_attractions = sorted(
        [a for a in attractions if a.get("price", 0) > 0],
        key=lambda x: x["price"]
    )

    narratives = []

    # What can savings buy?
    affordable = [a for a in paid_attractions if a["price"] <= total_savings]
    if affordable:
        best = affordable[-1]  # most expensive affordable one
        leftover = total_savings - best["price"]
        narratives.append(
            f"省下的 ¥{total_savings} 正好够买 **{best['name']}** 门票（¥{best['price']}）"
        )
        if leftover > 0 and affordable[0]["price"] <= leftover:
            narratives[-1] += f"，还能再来一张 **{affordable[0]['name']}**（¥{affordable[0]['price']}）"

    # Multi-item narrative
    if len(affordable) >= 2:
        multi = sorted(affordable, key=lambda x: x["price"], reverse=True)[:2]
        combo_price = sum(a["price"] for a in multi)
        if combo_price <= total_savings:
            names = " + ".join(a["name"] for a in multi)
            narratives.append(
                f"或者，省下的 ¥{total_savings} 能覆盖 **{names}** 两张门票（共 ¥{combo_price}）"
            )

    # Free attractions bonus
    if free_attractions and narratives:
        free_names = "、".join(a["name"] for a in free_attractions[:2])
        narratives.append(f"再加上免费的 {free_names}，行程安排得更满!")

    # Food/drink framing
    narratives.append(
        f"换个说法：¥{total_savings} 够在大连吃 {total_savings // 50} 顿海鲜烧烤 🦞"
    )

    return "\n".join(f"> 💡 {n}" for n in narratives)


# ── Alternative Suggestions ────────────────────────────────────

def suggest_alternatives(selection: dict, optimization: dict) -> list:
    """When budget is tight, suggest trade-offs to save more money."""
    suggestions = []
    budget = selection.get("budget", {}).get("total", 0)
    actual = optimization["grand_total_after"]

    if budget and actual > budget:
        over = actual - budget
        suggestions.append({
            "type": "over_budget",
            "overspent": over,
            "message": f"当前方案超出预算 ¥{over}，以下调整可以帮你控预算："
        })

    hotel = selection.get("hotel", {})
    hotel_price = hotel.get("price_per_night", 0)
    duration = selection.get("duration_days", 3)
    hotel_total = hotel_price * (duration - 1)

    # Suggest cheaper hotel alternatives
    alt_hotels = selection.get("_alt_hotels", [])
    for ah in alt_hotels:
        ah_total = ah.get("price_per_night", 0) * (duration - 1)
        saving = hotel_total - ah_total
        if saving > 0:
            suggestions.append({
                "type": "hotel_downgrade",
                "current": {"name": hotel["name"], "price": hotel_price, "total": hotel_total},
                "alternative": {"name": ah["name"], "price": ah["price_per_night"], "total": ah_total},
                "savings": saving
            })

    # Suggest transport alternatives
    transport = selection.get("transport", {})
    alt_transports = selection.get("_alt_transports", [])
    for at in alt_transports:
        saving = (transport.get("price", 0) - at.get("price", 0)) * 2
        if saving > 0:
            suggestions.append({
                "type": "transport_downgrade",
                "current": {"id": transport["id"], "price": transport["price"]},
                "alternative": {"id": at["id"], "price": at["price"]},
                "savings": saving
            })

    return suggestions


# ── Order ID Generator ─────────────────────────────────────────

def generate_order_id(prefix: str) -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=8))
    return f"{prefix}-{suffix}"


# ── Main Simulator ─────────────────────────────────────────────

def simulate_booking(selection: dict, coupons: list = None) -> dict:
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")

    transport = selection.get("transport", {})
    hotel = selection.get("hotel", {})
    duration = selection.get("duration_days", 3)
    nights = duration - 1

    transport_price = transport.get("price", 0)
    hotel_price = hotel.get("price_per_night", 0)

    transport_roundtrip = transport_price * 2
    hotel_total = hotel_price * nights
    attractions_total = sum(a["price"] for a in selection.get("attractions", [])[:duration * 2])
    total_amount = transport_roundtrip + hotel_total + attractions_total

    # Combinatorial optimization
    optimization = find_optimal_coupon_combo(selection, coupons or [])
    matched_coupons = optimization["all_applied"]
    total_savings = optimization["total_savings"]
    final_amount = total_amount - total_savings

    # Generate narratives
    savings_narrative = generate_savings_narrative(optimization, selection)
    alternatives = suggest_alternatives(selection, optimization)

    main_order_id = f"MEITUAN-{date_str}-{generate_order_id('').split('-')[-1][:4]}"

    confirmation = {
        "order_id": main_order_id,
        "booking_time": now.isoformat(),
        "status": "confirmed",
        "transport_booking": {
            "order_id": generate_order_id("RC"),
            "type": transport.get("type", ""),
            "id": transport.get("id", ""),
            "route": f"{transport.get('from', '')} → {transport.get('to', '')}",
            "departure_date": selection.get("date_start", ""),
            "departure_time": transport.get("departure", ""),
            "arrival_time": transport.get("arrival", ""),
            "seat_type": transport.get("seat_type", ""),
            "price_per_ticket": transport_price,
            "tickets": 1,
            "subtotal": transport_roundtrip,
            "status": "issued"
        },
        "hotel_booking": {
            "order_id": generate_order_id("RH"),
            "hotel_name": hotel.get("name", ""),
            "check_in": selection.get("date_start", ""),
            "check_out": selection.get("date_end", ""),
            "nights": nights,
            "room_type": "标准大床房",
            "price_per_night": hotel_price,
            "subtotal": hotel_total,
            "status": "confirmed"
        },
        "coupons_applied": matched_coupons,
        "optimization": {
            "method": "combinatorial_v2",
            "total_combos_evaluated": optimization.get("total_combos", "N/A"),
            "breakdown": optimization["breakdown"],
            "savings_narrative": savings_narrative
        },
        "alternatives": alternatives,
        "total_savings": total_savings,
        "payment": {
            "subtotal_transport": transport_roundtrip,
            "subtotal_hotel": hotel_total,
            "subtotal_attractions": attractions_total,
            "coupon_savings": total_savings,
            "total_amount": total_amount,
            "final_amount": final_amount if total_savings > 0 else total_amount,
            "payment_method": "美团支付（模拟）",
            "payment_status": "paid",
            "payment_time": now.isoformat()
        },
        "confidence": {
            "score": 0.0,
            "label": "模拟演示",
            "note": "此为Demo模拟预订，非真实交易。实际出行请前往12306和美团APP下单。",
            "disclaimer": "本系统不处理真实支付，所有订单号均为模拟生成(MEITUAN-前缀)。行程价格以官方平台实时显示为准。"
        }
    }

    return confirmation


def format_confirmation_text(confirmation: dict) -> str:
    tb = confirmation["transport_booking"]
    hb = confirmation["hotel_booking"]
    pm = confirmation["payment"]
    opt = confirmation.get("optimization", {})

    lines = []
    lines.append("✅ 预订确认！")
    lines.append("")
    lines.append(f"📋 订单号：{confirmation['order_id']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    transport_icon = "🚄" if tb["type"] == "high_speed_rail" else "✈️"
    lines.append(f"{transport_icon} {tb['id']} {tb['route']}")
    lines.append(f"   {tb['departure_date']} {tb['departure_time']}-{tb['arrival_time']}")
    lines.append(f"   {tb['seat_type']} ¥{tb['price_per_ticket']} | 订单号：{tb['order_id']}")
    lines.append(f"   状态：✅ 已出票")
    lines.append("")

    lines.append(f"🏨 {hb['hotel_name']}")
    lines.append(f"   {hb['check_in']}-{hb['check_out']}（{hb['nights']}晚）")
    lines.append(f"   {hb['room_type']} ¥{hb['price_per_night']}×{hb['nights']} = ¥{hb['subtotal']}")
    lines.append(f"   订单号：{hb['order_id']}")
    lines.append(f"   状态：✅ 已确认")
    lines.append("")

    lines.append(f"💰 支付总额：¥{pm['total_amount']}")

    coupons = confirmation.get("coupons_applied", [])
    if coupons:
        lines.append("")
        lines.append("🎫 智能优惠券组合（已自动匹配最优叠加方案）：")
        for c in coupons:
            lines.append(f"   ✅ {c['coupon_name']} — 省 ¥{c['savings']}")
        lines.append(f"💳 实付：¥{pm.get('final_amount', pm['total_amount'])} "
                     f"(共省 ¥{confirmation.get('total_savings', 0)})")

    lines.append(f"💳 支付方式：{pm['payment_method']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Savings reallocation narrative
    narrative = opt.get("savings_narrative", "")
    if narrative:
        lines.append("")
        lines.append("📊 省钱再分配分析：")
        lines.append(narrative)

    # Alternative suggestions
    alternatives = confirmation.get("alternatives", [])
    if alternatives:
        over_budget = [a for a in alternatives if a["type"] == "over_budget"]
        if over_budget:
            lines.append("")
            lines.append(f"⚠️ {over_budget[0]['message']}")
        for a in alternatives:
            if a["type"] == "hotel_downgrade":
                lines.append(f"   🏨 {a['current']['name']} → {a['alternative']['name']} "
                             f"(省 ¥{a['savings']})")
            elif a["type"] == "transport_downgrade":
                lines.append(f"   🚄 {a['current']['id']} → {a['alternative']['id']} "
                             f"(省 ¥{a['savings']})")

    lines.append("")
    lines.append("祝旅途愉快！🎉")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Simulate booking with combinatorial optimization")
    parser.add_argument("--selection-file", required=True)
    parser.add_argument("--coupons-file", default=None, help="Path to coupons.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.selection_file, "r", encoding="utf-8") as f:
        selection = json.load(f)

    coupons = load_coupons(args.coupons_file)
    confirmation = simulate_booking(selection, coupons)
    confirmation["summary_text"] = format_confirmation_text(confirmation)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(confirmation, f, ensure_ascii=False, indent=2)

    print(confirmation["summary_text"])
    print()
    print(json.dumps(confirmation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
