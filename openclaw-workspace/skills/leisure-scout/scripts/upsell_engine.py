#!/usr/bin/env python3
"""Coupon Upsell Engine — 凑单/拆单智能优化。

Core insight: "像真人管家一样帮你省钱" — not just match coupons, but actively
suggest small upgrades that trigger bigger discounts.

Capabilities:
  1. Gap detection: "差X元触发Y券，要不要凑一下?"
  2. Upsell calculation: "多花25元升级江景房 → 触发30元券 → 等于花5元住江景"
  3. Marginal cost analysis: net cost = upgrade_price - triggered_savings
  4. Bundle optimization: find item pairs that maximize coupon coverage

Usage:
    python upsell_engine.py \
        --selection-file /tmp/final_selection.json \
        --coupons-file data/coupons.json \
        --output /tmp/upsell_suggestions.json
"""

import json
import argparse
import os
from datetime import date
from itertools import combinations


# ── Load ───────────────────────────────────────────────────────

def load_json(path: str):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Core: Gap Detector ─────────────────────────────────────────

def find_near_miss_coupons(selection: dict, coupons: list, threshold: float = 0.20) -> list:
    """Find coupons that are close to being triggered but need a bit more spend.

    near-miss = the gap is within `threshold` of the min_amount.
    E.g., spent ¥270, coupon needs ¥300 → gap=30, gap_ratio=10% → near miss.
    """
    today = date.today().isoformat()
    hotel_total = selection.get("hotel", {}).get("price_per_night", 0) * \
                  (selection.get("duration_days", 3) - 1)
    transport_total = selection.get("transport", {}).get("price", 0) * 2
    attractions_total = sum(a.get("price", 0)
                            for a in selection.get("attractions", [])[:6])
    grand_total = hotel_total + transport_total + attractions_total

    near_misses = []

    for c in coupons:
        if c.get("status") != "available":
            continue
        if today < c.get("valid_from", "") or today > c.get("valid_until", ""):
            continue

        min_amount = c.get("min_amount", 0)
        category = c["category"]

        if category == "hotel":
            current = hotel_total
        elif category in ("transport_train", "transport_flight"):
            current = transport_total
        elif category == "attraction":
            current = attractions_total
        elif category == "general":
            current = grand_total
        else:
            continue

        gap = min_amount - current
        if gap <= 0:
            continue  # already triggered

        gap_ratio = gap / min_amount if min_amount > 0 else 0
        if gap_ratio <= threshold:
            potential_savings = _calc_potential_savings(c, min_amount)
            near_misses.append({
                "coupon_id": c["id"],
                "coupon_name": c["name"],
                "category": category,
                "min_amount": min_amount,
                "current_spend": current,
                "gap": gap,
                "gap_ratio": round(gap_ratio * 100, 1),
                "potential_savings": potential_savings,
                "net_benefit_if_triggered": potential_savings - gap,
            })

    return sorted(near_misses, key=lambda x: x["net_benefit_if_triggered"], reverse=True)


def _calc_potential_savings(coupon: dict, amount: float) -> int:
    if coupon["discount_type"] == "fixed":
        return coupon.get("discount_amount", 0)
    else:
        rate = coupon.get("discount_rate", 0)
        cap = coupon.get("discount_cap", float("inf"))
        return int(min(amount * rate, cap))


# ── Core: Upsell Suggester ─────────────────────────────────────

def generate_upsell_suggestions(selection: dict, near_misses: list) -> list:
    """For each near-miss coupon, find upgrade options that close the gap.

    Types of upgrades:
      - hotel_room_upgrade: standard → sea view / deluxe
      - hotel_meal_addon: add breakfast / dinner buffet
      - transport_seat_upgrade: 2nd class → 1st class
      - attraction_addon: add one more attraction ticket
      - insurance: add travel insurance
    """
    hotel = selection.get("hotel", {})
    transport = selection.get("transport", {})
    attractions = selection.get("attractions", [])
    duration = selection.get("duration_days", 3)
    nights = duration - 1

    suggestions = []

    for nm in near_misses:
        gap = nm["gap"]
        category = nm["category"]

        if category == "hotel":
            # Room upgrade: price diff × nights
            room_upgrades = [
                {"name": "升级海景房", "price_per_night": 40,
                 "desc": f"标准间→海景房，+¥{40}/晚"},
                {"name": "升级豪华套房", "price_per_night": 80,
                 "desc": f"标准间→豪华套房，+¥{80}/晚"},
                {"name": "加购双人早餐", "price_per_night": 30,
                 "desc": f"双人自助早餐，+¥{30}/晚"},
            ]
            for ru in room_upgrades:
                cost = ru["price_per_night"] * nights
                net = nm["net_benefit_if_triggered"] - cost + gap
                if net >= -gap * 0.3:  # within reason
                    suggestions.append({
                        "trigger_coupon": nm["coupon_name"],
                        "trigger_gap": gap,
                        "upgrade_type": "hotel",
                        "upgrade_name": ru["name"],
                        "upgrade_cost": cost,
                        "coupon_savings": nm["potential_savings"],
                        "net_cost": cost - nm["potential_savings"],
                        "message": (
                            f"只需再加 ¥{cost} {ru['desc']}，"
                            f"就能触发「{nm['coupon_name']}」省 ¥{nm['potential_savings']}，"
                            f"等于{'多花' if cost - nm['potential_savings'] > 0 else '净赚'}"
                            f"¥{abs(cost - nm['potential_savings'])}"
                            f"{'住海景' if '海景' in ru['name'] else ''}！"
                        ),
                        "roi": round(nm["potential_savings"] / cost, 2) if cost > 0 else 0,
                        "is_sweet_spot": abs(cost - nm['potential_savings']) <= 20,
                    })

        elif category == "transport_train":
            seat_upgrades = [
                {"name": "升级一等座", "price_diff": 150,
                 "desc": f"二等座→一等座，+¥{150}"},
            ]
            for su in seat_upgrades:
                cost = su["price_diff"] * 2  # round trip
                if cost <= gap * 1.5:
                    suggestions.append({
                        "trigger_coupon": nm["coupon_name"],
                        "trigger_gap": gap,
                        "upgrade_type": "transport",
                        "upgrade_name": su["name"],
                        "upgrade_cost": cost,
                        "coupon_savings": nm["potential_savings"],
                        "net_cost": cost - nm["potential_savings"],
                        "message": (
                            f"{su['desc']}，触发「{nm['coupon_name']}」省 ¥{nm['potential_savings']}，"
                            f"等于{'多花' if cost - nm['potential_savings'] > 0 else '净赚'}"
                            f"¥{abs(cost - nm['potential_savings'])}坐一等座！"
                        ),
                        "roi": round(nm["potential_savings"] / cost, 2) if cost > 0 else 0,
                        "is_sweet_spot": abs(cost - nm['potential_savings']) <= 30,
                    })

        elif category == "attraction":
            # Suggest adding one more cheap attraction
            cheap_attractions = [a for a in attractions
                                 if 0 < a.get("price", 0) <= gap * 1.5]
            for ca in cheap_attractions:
                cost = ca["price"]
                suggestions.append({
                    "trigger_coupon": nm["coupon_name"],
                    "trigger_gap": gap,
                    "upgrade_type": "attraction",
                    "upgrade_name": f"加购{ca['name']}门票",
                    "upgrade_cost": cost,
                    "coupon_savings": nm["potential_savings"],
                    "net_cost": cost - nm["potential_savings"],
                    "message": (
                        f"再加一张 **{ca['name']}** 门票（¥{cost}），"
                        f"触发「{nm['coupon_name']}」省 ¥{nm['potential_savings']}，"
                        f"等于{'多花' if cost - nm['potential_savings'] > 0 else '净赚'}"
                        f"¥{abs(cost - nm['potential_savings'])}多玩一个景点！"
                    ),
                    "roi": round(nm["potential_savings"] / cost, 2) if cost > 0 else 0,
                    "is_sweet_spot": abs(cost - nm['potential_savings']) <= 15,
                })

    # Sort: "sweet spots" first (几乎免费升级), then by ROI
    return sorted(suggestions, key=lambda x: (not x["is_sweet_spot"], -x["roi"]))


# ── Core: Bundle Optimizer ─────────────────────────────────────

def find_bundle_opportunities(selection: dict, coupons: list) -> list:
    """Find combinations of 2 items that together trigger an otherwise unreachable coupon.

    "拆单" logic: instead of one big order, split into smaller orders to trigger more coupons.
    """
    hotel = selection.get("hotel", {})
    transport = selection.get("transport", {})
    attractions = selection.get("attractions", [])
    duration = selection.get("duration_days", 3)
    hotel_total = hotel.get("price_per_night", 0) * (duration - 1)
    transport_total = transport.get("price", 0) * 2

    bundles = []

    # Hotel + attraction combo to trigger general coupon
    for c in coupons:
        if c.get("category") != "general":
            continue
        if c.get("status") != "available":
            continue

        min_amount = c.get("min_amount", 0)
        # Check if hotel alone doesn't trigger, but hotel + 1 attraction does
        for a in attractions:
            combo_total = hotel_total + transport_total + a.get("price", 0)
            current_total = hotel_total + transport_total
            if current_total < min_amount <= combo_total:
                savings = _calc_potential_savings(c, combo_total)
                net = savings - a.get("price", 0)
                if net > 0:
                    bundles.append({
                        "coupon_name": c["name"],
                        "strategy": "combo",
                        "action": f"加购{a['name']}门票（¥{a['price']}）触发「{c['name']}」",
                        "extra_cost": a["price"],
                        "new_savings": savings,
                        "net_benefit": net,
                        "message": (
                            f"加一张 **{a['name']}** 门票（¥{a['price']}），"
                            f"就能触发「{c['name']}」省 ¥{savings}，"
                            f"等于净省 ¥{net} 还多玩一个景点！"
                        )
                    })

    return sorted(bundles, key=lambda x: x["net_benefit"], reverse=True)


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Coupon Upsell Engine — 凑单/拆单优化")
    parser.add_argument("--selection-file", required=True)
    parser.add_argument("--coupons-file", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    selection = load_json(args.selection_file)
    coupons = load_json(args.coupons_file)

    near_misses = find_near_miss_coupons(selection, coupons)
    upsells = generate_upsell_suggestions(selection, near_misses)
    bundles = find_bundle_opportunities(selection, coupons)

    result = {
        "generated_at": date.today().isoformat(),
        "near_miss_coupons": near_misses,
        "near_miss_count": len(near_misses),
        "upsell_suggestions": upsells,
        "upsell_count": len(upsells),
        "sweet_spot_count": len([u for u in upsells if u["is_sweet_spot"]]),
        "bundle_opportunities": bundles,
        "bundle_count": len(bundles),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"🔍 凑单引擎分析完成")
    print(f"  近触发券: {len(near_misses)} 张")
    print(f"  升级建议: {len(upsells)} 个 ({result['sweet_spot_count']} 个超值)")
    print(f"  组合机会: {len(bundles)} 个")
    print()

    for u in upsells[:3]:
        tag = "🌟 超值!" if u["is_sweet_spot"] else "💡"
        print(f"  {tag} {u['message']}")

    for b in bundles[:2]:
        print(f"  📦 {b['message']}")

    print()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
