#!/usr/bin/env python3
"""Real-time Price Verifier — 浏览器自动抓取 + 结果解析闭环。

Closes the loop: stale data → scraping plan → browser execution → parsed results → confidence upgrade.

Architecture:
  1. Accepts a scraping plan from realtime_scraper.py
  2. Executes browser tasks via OpenClaw browser extension (or simulated demo mode)
  3. Parses HTML/screenshot results into structured price data
  4. Merges verified prices into the selection, upgrading confidence scores
  5. Flags any discrepancies between local data and real-time prices

Modes:
  --mode simulated : Uses mock browser responses for demo (no browser needed)
  --mode openclaw  : Generates OpenClaw browser tool calls for agent execution

Usage:
  # Demo mode (self-contained)
  python realtime_price_verifier.py \\
      --scrape-plan /tmp/scrape_plan.json \\
      --selection-file /tmp/final_selection.json \\
      --mode simulated \\
      --output /tmp/verified_selection.json

  # OpenClaw mode (generates tool calls for agent)
  python realtime_price_verifier.py \\
      --scrape-plan /tmp/scrape_plan.json \\
      --mode openclaw \\
      --output /tmp/browser_tasks.json
"""

import json
import argparse
import os
import sys
import random
from datetime import datetime, date

# ── Simulated Browser Response Data ────────────────────────────

# Realistic price variations for demo purposes (±15% from local data)
SIMULATED_PRICE_VARIANCE = {
    "hotel": 0.12,      # hotel prices can vary ±12%
    "transport": 0.05,  # transport prices relatively stable ±5%
    "attraction": 0.03, # attraction ticket prices stable ±3%
    "restaurant": 0.15  # restaurant prices vary ±15%
}

SIMULATED_AVAILABILITY = {
    "hotel": 0.85,      # 85% chance available
    "transport": 0.70,  # 70% during holiday
    "attraction": 0.95, # 95% available
}


def simulate_browser_fetch(url: str, category: str) -> dict:
    """Simulate a browser fetch for demo purposes.

    In production, this would use OpenClaw's browser tool to navigate
    to the URL, wait for content to load, and extract data.
    """
    success_chance = SIMULATED_AVAILABILITY.get(category, 0.90)
    if random.random() > success_chance:
        return {"status": "failed", "error": "Page load timeout or data not found"}

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "page_title": f"美团{category}搜索结果",
        "extracted_items": [],
        "source": "simulated_headless_browser"
    }


def simulate_hotel_results(local_hotels: list) -> list:
    """Simulate hotel search results with realistic price variations."""
    results = []
    for h in local_hotels[:5]:
        variance = 1.0 + random.uniform(-SIMULATED_PRICE_VARIANCE["hotel"],
                                          SIMULATED_PRICE_VARIANCE["hotel"])
        realtime_price = round(h.get("price_per_night", 300) * variance)
        results.append({
            "name": h.get("name", ""),
            "local_price": h.get("price_per_night", 0),
            "realtime_price": realtime_price,
            "price_diff": realtime_price - h.get("price_per_night", 0),
            "price_diff_pct": round((variance - 1.0) * 100, 1),
            "available": random.random() > 0.15,
            "badge": random.choice(["限时特惠", "今日特价", "只剩2间", None, None]),
            "rating": h.get("rating", 4.0) + random.uniform(-0.2, 0.2),
        })
    return results


def simulate_transport_results(local_transports: list) -> list:
    """Simulate transport search results."""
    results = []
    for t in local_transports[:3]:
        variance = 1.0 + random.uniform(-SIMULATED_PRICE_VARIANCE["transport"],
                                          SIMULATED_PRICE_VARIANCE["transport"])
        realtime_price = round(t.get("price", 300) * variance)
        results.append({
            "id": t.get("id", ""),
            "route": f"{t.get('from', '')} → {t.get('to', '')}",
            "local_price": t.get("price", 0),
            "realtime_price": realtime_price,
            "price_diff": realtime_price - t.get("price", 0),
            "available": random.random() > 0.30,
            "remaining_seats": random.randint(0, 50) if random.random() > 0.30 else 0,
        })
    return results


def simulate_attraction_results(local_attractions: list) -> list:
    """Simulate attraction ticket search results."""
    results = []
    for a in local_attractions[:5]:
        variance = 1.0 + random.uniform(-SIMULATED_PRICE_VARIANCE["attraction"],
                                          SIMULATED_PRICE_VARIANCE["attraction"])
        realtime_price = round(a.get("price", 50) * variance)
        if a.get("price", 0) == 0:
            realtime_price = 0  # Free stays free
        results.append({
            "name": a.get("name", ""),
            "local_price": a.get("price", 0),
            "realtime_price": realtime_price,
            "price_diff": realtime_price - a.get("price", 0),
            "available": True,
        })
    return results


# ── Price Verification Engine ──────────────────────────────────

def verify_prices(selection: dict, scrape_plan: dict, mode: str = "simulated") -> dict:
    """Execute the scraping plan and verify prices against local data.

    Returns a verification report with:
      - verified_prices: real-time prices for each category
      - discrepancies: where local data differs from real-time
      - confidence_upgrade: new confidence scores
      - execution_log: what happened
    """
    execution_log = []
    verified = {}
    discrepancies = []

    hotel = selection.get("hotel", {})
    transport = selection.get("transport", {})
    attractions = selection.get("attractions", [])

    # ── Hotel Verification ──────────────────────────────────────
    hotel_cat = next((c for c in scrape_plan.get("categories", [])
                      if c["category"] == "hotel"), None)
    if hotel_cat and mode == "simulated":
        hotel_results = simulate_hotel_results([hotel])
        execution_log.append({
            "category": "hotel",
            "tasks_executed": len(hotel_cat.get("tasks", [])),
            "results_found": len(hotel_results),
            "mode": mode
        })
        verified["hotel"] = hotel_results
        if hotel_results:
            rt = hotel_results[0]
            diff = rt["price_diff"]
            if abs(diff) > 0:
                direction = "上涨" if diff > 0 else "下降"
                discrepancies.append({
                    "category": "hotel",
                    "item": hotel.get("name", ""),
                    "local_price": rt["local_price"],
                    "realtime_price": rt["realtime_price"],
                    "diff": diff,
                    "message": f"酒店价格{direction} ¥{abs(diff)}: "
                               f"本地¥{rt['local_price']} → 实时¥{rt['realtime_price']}"
                })

    # ── Transport Verification ──────────────────────────────────
    transport_cat = next((c for c in scrape_plan.get("categories", [])
                          if c["category"] in ("transport", "transport_train")), None)
    if transport_cat and mode == "simulated":
        transport_results = simulate_transport_results([transport])
        execution_log.append({
            "category": "transport",
            "tasks_executed": len(transport_cat.get("tasks", [])),
            "results_found": len(transport_results),
            "mode": mode
        })
        verified["transport"] = transport_results
        if transport_results:
            rt = transport_results[0]
            diff = rt["price_diff"]
            if abs(diff) > 0:
                direction = "上涨" if diff > 0 else "下降"
                discrepancies.append({
                    "category": "transport",
                    "item": transport.get("id", ""),
                    "local_price": rt["local_price"],
                    "realtime_price": rt["realtime_price"],
                    "diff": diff,
                    "available": rt.get("available", False),
                    "remaining": rt.get("remaining_seats", 0),
                    "message": f"车票价格{direction} ¥{abs(diff)}: "
                               f"本地¥{rt['local_price']} → 实时¥{rt['realtime_price']}"
                               + (f" (仅剩{rt['remaining_seats']}张!)"
                                  if rt.get("remaining_seats", 99) < 10 else "")
                })

    # ── Attraction Verification ─────────────────────────────────
    att_cat = next((c for c in scrape_plan.get("categories", [])
                    if c["category"] == "attraction"), None)
    if att_cat and mode == "simulated":
        att_results = simulate_attraction_results(attractions)
        execution_log.append({
            "category": "attraction",
            "tasks_executed": len(att_cat.get("tasks", [])),
            "results_found": len(att_results),
            "mode": mode
        })
        verified["attraction"] = att_results

    # ── Confidence Upgrade ──────────────────────────────────────
    total_tasks = sum(e["tasks_executed"] for e in execution_log)
    total_results = sum(e["results_found"] for e in execution_log)

    if total_results >= total_tasks * 0.8:
        # All categories returned results → high confidence
        new_confidence = {"score": 0.80, "label": "实时验证通过", "color": "green"}
    elif total_results >= 1:
        new_confidence = {"score": 0.60, "label": "部分验证通过", "color": "yellow"}
    else:
        new_confidence = {"score": 0.40, "label": "验证失败(数据过期)", "color": "red"}

    # ── Build Updated Selection ─────────────────────────────────
    updated_selection = dict(selection)
    if verified.get("hotel"):
        updated_selection["_verified_hotel_prices"] = verified["hotel"]
    if verified.get("transport"):
        updated_selection["_verified_transport_prices"] = verified["transport"]

    return {
        "verification_id": f"VRF-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "verification_time": datetime.now().isoformat(),
        "mode": mode,
        "execution_log": execution_log,
        "verified_prices": verified,
        "discrepancies": discrepancies,
        "discrepancy_count": len(discrepancies),
        "total_tasks_executed": total_tasks,
        "total_results_found": total_results,
        "confidence": new_confidence,
        "updated_selection": updated_selection,
        "summary": generate_summary(discrepancies, new_confidence, selection)
    }


def generate_openclaw_tasks(scrape_plan: dict) -> list:
    """Convert scraping plan into OpenClaw browser tool calls."""
    tasks = []
    for cat in scrape_plan.get("categories", []):
        for task in cat.get("tasks", []):
            tasks.append({
                "tool": "browser",
                "action": task.get("browser_action", "navigate"),
                "url": task.get("url", ""),
                "wait_for": task.get("wait_for", ""),
                "extract": task.get("extract", {}),
                "priority": task.get("priority", "medium"),
                "on_success": task.get("on_success", ""),
                "on_failure": task.get("on_failure", ""),
            })
    return tasks


def generate_summary(discrepancies: list, confidence: dict, selection: dict) -> str:
    """Generate human-readable verification summary."""
    total_diff = sum(d.get("diff", 0) for d in discrepancies)
    city = selection.get("city_name", "")

    lines = []
    lines.append(f"🔍 实时价格验证完成 — {city}")

    if not discrepancies:
        lines.append("✅ 本地数据与实时价格一致，可信度高。")
    else:
        direction = "涨" if total_diff > 0 else "降"
        lines.append(f"⚠️ 发现 {len(discrepancies)} 处差异，整体价格比本地数据{direction}了 ¥{abs(total_diff)}。")
        for d in discrepancies:
            lines.append(f"  • {d['message']}")

    lines.append(f"📊 信心指数: {confidence['label']} ({confidence['score']})")
    lines.append("💡 以上价格来自模拟实时抓取，实际出行请前往12306和美团App确认。")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Real-time Price Verifier — 浏览器自动抓取闭环")
    parser.add_argument("--scrape-plan", required=True,
                        help="Scraping plan JSON from realtime_scraper.py")
    parser.add_argument("--selection-file", default="",
                        help="Current selection JSON (for price comparison)")
    parser.add_argument("--mode", choices=["simulated", "openclaw"], default="simulated")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.scrape_plan, "r", encoding="utf-8") as f:
        scrape_plan = json.load(f)

    if args.mode == "openclaw":
        tasks = generate_openclaw_tasks(scrape_plan)
        result = {
            "mode": "openclaw",
            "generated_at": datetime.now().isoformat(),
            "total_tasks": len(tasks),
            "tasks": tasks,
            "instructions": "Pass these tasks to OpenClaw's browser tool. "
                            "Execute in order, capture screenshots, parse results."
        }
    else:
        selection = {}
        if args.selection_file and os.path.exists(args.selection_file):
            with open(args.selection_file, "r", encoding="utf-8") as f:
                selection = json.load(f)
        result = verify_prices(selection, scrape_plan, mode="simulated")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(result.get("summary", ""), file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
