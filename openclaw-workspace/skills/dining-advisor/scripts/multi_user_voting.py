#!/usr/bin/env python3
"""Multi-User Collaborative Voting — 多画像群组决策引擎。

Enhances group_voting.py with:
  1. Multi-user preference profiles (3+ users, different tastes)
  2. Preference-to-option matching matrix
  3. "Greatest Common Divisor" (GCD) calculation — maximize collective satisfaction
  4. Auto-vote simulation based on preference alignment
  5. Fairness metrics: individual satisfaction scores + group welfare

Scenario: 管家生成3个目的地，自动发给群里3个不同画像的用户
  - 用户A: 喜欢海、预算充裕
  - 用户B: 喜欢美食、文化体验
  - 用户C: 预算低、想省钱
  → 计算最大公约数方案 → 泉州（人文+美食+海景，预算适中，3人都能接受）

Usage:
    # Analyze which option maximizes group satisfaction
    python multi_user_voting.py \\
        --options-file /tmp/candidates.json \\
        --profiles-file data/user_profiles/group_profiles.json \\
        --output /tmp/group_decision.json
"""

import json
import argparse
import os
from datetime import datetime


# ── Preference Matching ────────────────────────────────────────

def match_option_to_user(option: dict, profile: dict) -> float:
    """Calculate how well an option matches a user's preferences.

    Returns a satisfaction score from 0.0 (terrible match) to 1.0 (perfect match).
    """
    score = 0.0
    weights = 0.0

    # Preference dimensions and their weights
    dims = {
        "destination_type": 0.25,
        "budget_fit": 0.30,
        "transport_pref": 0.15,
        "food_culture": 0.15,
        "activity_level": 0.10,
        "crowd_tolerance": 0.05,
    }

    pref = profile.get("preferences", {})
    budget = profile.get("budget_range", {})

    # Destination type match
    preferred_types = pref.get("destination_types", [])
    opt_type = option.get("city_type", "")
    if any(pt in opt_type for pt in preferred_types):
        score += dims["destination_type"]
    elif preferred_types:
        score += dims["destination_type"] * 0.3  # partial match
    weights += dims["destination_type"]

    # Budget fit
    opt_budget = option.get("budget_estimate", {}).get("budget_recommended", 0)
    min_b = budget.get("min", 0)
    max_b = budget.get("max", float("inf"))
    if opt_budget <= max_b:
        if opt_budget <= min_b * 1.2:
            score += dims["budget_fit"]  # well within budget
        else:
            # Linear decay: budget fit decreases as price approaches max
            ratio = (max_b - opt_budget) / (max_b - min_b) if max_b > min_b else 0.5
            score += dims["budget_fit"] * max(0, min(1, ratio))
    weights += dims["budget_fit"]

    # Transport preference
    pref_transport = pref.get("transport", [])
    opt_transport_type = option.get("transport_type_primary", "")
    if opt_transport_type in pref_transport:
        score += dims["transport_pref"]
    elif pref_transport:
        score += dims["transport_pref"] * 0.4
    weights += dims["transport_pref"]

    # Food/culture interest
    food_interest = pref.get("food_importance", 0.5)
    opt_food_score = option.get("food_culture_score", 0.5)
    score += dims["food_culture"] * (1 - abs(food_interest - opt_food_score))
    weights += dims["food_culture"]

    # Activity level
    activity_pref = pref.get("activity_level", "moderate")
    activity_map = {"relaxed": 0.3, "moderate": 0.6, "active": 1.0}
    opt_activity = activity_map.get(option.get("activity_level", "moderate"), 0.6)
    user_activity = activity_map.get(activity_pref, 0.6)
    score += dims["activity_level"] * (1 - abs(user_activity - opt_activity) / 0.7)
    weights += dims["activity_level"]

    return round(score / weights, 4) if weights > 0 else 0.5


# ── GCD Calculator ─────────────────────────────────────────────

def find_greatest_common_divisor(options: list, profiles: list) -> dict:
    """Calculate the option that maximizes collective group satisfaction.

    Uses three metrics:
      1. Gini-equalized score (penalize options where someone is very unhappy)
      2. Raw average score
      3. Minimum satisfaction (worst-off member)

    GCD score = avg(scores) × (1 - gini(scores)) × (1 + min(scores))
    """
    results = []

    for opt in options:
        scores = [match_option_to_user(opt, p) for p in profiles]
        avg = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        # Gini coefficient: 0 = perfect equality, 1 = max inequality
        gini = _gini(scores)

        # GCD score: reward high average AND fairness AND floor
        gcd_score = avg * (1 - gini * 0.5) * (0.5 + min_score)

        results.append({
            "option": opt,
            "option_label": opt.get("city_name", opt.get("label", "?")),
            "individual_scores": [
                {"user_name": p["name"], "user_id": p["id"], "score": round(s, 3)}
                for p, s in zip(profiles, scores)
            ],
            "avg_satisfaction": round(avg, 4),
            "min_satisfaction": round(min_score, 4),
            "max_satisfaction": round(max_score, 4),
            "gini_coefficient": round(gini, 4),
            "gcd_score": round(gcd_score, 4),
            "fairness": "公平" if gini < 0.2 else ("可接受" if gini < 0.35 else "有争议"),
        })

    # Sort by GCD score descending
    results.sort(key=lambda x: x["gcd_score"], reverse=True)

    winner = results[0]
    runner_up = results[1] if len(results) > 1 else None

    return {
        "analysis_time": datetime.now().isoformat(),
        "total_options": len(options),
        "total_users": len(profiles),
        "user_profiles": [{"name": p["name"], "preferences": p.get("preferences", {})}
                          for p in profiles],
        "results": results,
        "winner": {
            "option": winner["option"],
            "label": winner["option_label"],
            "gcd_score": winner["gcd_score"],
            "avg_satisfaction": winner["avg_satisfaction"],
            "reason": _generate_reason(winner, runner_up, results),
        },
        "recommendation": _build_recommendation(winner, profiles),
    }


def _gini(scores: list) -> float:
    """Calculate Gini coefficient for a list of scores."""
    n = len(scores)
    if n <= 1 or sum(scores) == 0:
        return 0.0
    sorted_scores = sorted(scores)
    cumsum = 0
    total = sum(sorted_scores)
    for i, s in enumerate(sorted_scores):
        cumsum += s
        # Gini = (2 * sum(i*s_i)) / (n * sum(s_i)) - (n+1)/n
    # Using formula: G = sum(|xi - xj|) / (2 * n^2 * mean)
    mean = total / n
    diff_sum = sum(abs(si - sj) for i, si in enumerate(scores) for sj in scores)
    gini = diff_sum / (2 * n * n * mean) if mean > 0 else 0
    return gini


def _generate_reason(winner: dict, runner_up: dict, all_results: list) -> str:
    """Generate human-readable reason for the GCD choice."""
    label = winner["option_label"]
    scores = winner["individual_scores"]
    score_str = ", ".join(f"{s['user_name']}={s['score']:.0%}" for s in scores)

    lines = [
        f"「{label}」是 {len(scores)} 人的最大公约数方案。",
        f"满意度分布: {score_str}",
    ]

    if runner_up:
        diff = winner["gcd_score"] - runner_up["gcd_score"]
        lines.append(
            f"比第二名「{runner_up['option_label']}」GCD高 {diff:.3f}，"
            f"主要优势是 {_compare_advantage(winner, runner_up)}。"
        )

    if winner["gini_coefficient"] < 0.2:
        lines.append("分歧很小，所有人满意度接近，是理想的选择。")
    elif winner["gini_coefficient"] < 0.35:
        lines.append("存在一些分歧但可调和，建议追加一轮微调投票。")

    return " ".join(lines)


def _compare_advantage(winner: dict, runner_up: dict) -> str:
    if winner["min_satisfaction"] > runner_up["min_satisfaction"]:
        return "最低满意度更高（没人被牺牲）"
    if winner["gini_coefficient"] < runner_up["gini_coefficient"]:
        return "满意度更均衡（分歧更小）"
    return "综合得分更高"


def _build_recommendation(winner: dict, profiles: list) -> str:
    label = winner["option_label"]
    scores = winner["individual_scores"]
    happiest = max(scores, key=lambda x: x["score"])
    saddest = min(scores, key=lambda x: x["score"])

    lines = [
        f"🏆 推荐方案: **{label}**",
        "",
        f"综合满意度: {winner['avg_satisfaction']:.0%} | 公平性: {winner['fairness']}",
        "",
    ]

    if happiest["score"] > 0.8:
        lines.append(f"  {happiest['user_name']} 最喜欢这个方案（{happiest['score']:.0%}）")
    if saddest["score"] < 0.5:
        lines.append(f"  {saddest['user_name']} 满意度偏低（{saddest['score']:.0%}），"
                      f"建议在行程中额外安排{saddest['user_name']}喜欢的活动作为补偿。")

    return "\n".join(lines)


# ── Auto-Vote Simulator ────────────────────────────────────────

def simulate_group_votes(options: list, profiles: list) -> list:
    """Simulate how each user would vote based on their preferences.

    Returns a list of emoji reactions suitable for group_voting.py --tally.
    """
    emoji_pool = ["1️⃣", "2️⃣", "3️⃣"]
    reactions = []

    for p in profiles:
        scores = [match_option_to_user(opt, p) for opt in options[:3]]
        best_idx = scores.index(max(scores))
        reactions.append({
            "voter_id": p["id"],
            "voter_name": p["name"],
            "emoji": emoji_pool[best_idx],
            "option_index": best_idx,
            "scores": {f"opt_{i+1}": round(s, 3) for i, s in enumerate(scores)},
        })

    return reactions


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Multi-User Collaborative Voting — 多画像GCD决策")
    parser.add_argument("--options-file", required=True,
                        help="Candidate options JSON (from matcher.py output)")
    parser.add_argument("--profiles-file", default="",
                        help="Group member profiles JSON")
    parser.add_argument("--output", required=True)
    parser.add_argument("--simulate-votes", action="store_true",
                        help="Also simulate individual votes for group_voting.py")
    args = parser.parse_args()

    with open(args.options_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    options = data if isinstance(data, list) else data.get("candidate_cities", data.get("options", []))
    if not options:
        print(json.dumps({"error": "No options found in file"}, ensure_ascii=False))
        return

    # Load or generate profiles
    if args.profiles_file and os.path.exists(args.profiles_file):
        with open(args.profiles_file, "r", encoding="utf-8") as f:
            profiles = json.load(f)
    else:
        # Default 3-person group
        profiles = [
            {"id": "user_a", "name": "小海",
             "preferences": {"destination_types": ["海边", "海滩"],
                             "transport": ["high_speed_rail", "flight"],
                             "food_importance": 0.5, "activity_level": "relaxed"},
             "budget_range": {"min": 2000, "max": 5000}},
            {"id": "user_b", "name": "吃货小王",
             "preferences": {"destination_types": ["美食", "人文"],
                             "transport": ["high_speed_rail"],
                             "food_importance": 0.95, "activity_level": "moderate"},
             "budget_range": {"min": 1500, "max": 3500}},
            {"id": "user_c", "name": "省钱小张",
             "preferences": {"destination_types": ["自然", "古镇", "海边", "城市"],
                             "transport": ["regular_train", "high_speed_rail"],
                             "food_importance": 0.3, "activity_level": "active"},
             "budget_range": {"min": 800, "max": 2000}},
        ]

    # Add transport_type_primary and food_culture_score to options if missing
    for opt in options:
        transports = opt.get("transport_options", [])
        if transports and "transport_type_primary" not in opt:
            opt["transport_type_primary"] = transports[0].get("type", "high_speed_rail")
        if "food_culture_score" not in opt:
            city_type = opt.get("city_type", "")
            if "美食" in city_type:
                opt["food_culture_score"] = 0.9
            elif "人文" in city_type:
                opt["food_culture_score"] = 0.7
            elif "海边" in city_type or "海滨" in city_type:
                opt["food_culture_score"] = 0.5
            else:
                opt["food_culture_score"] = 0.5
        if "activity_level" not in opt:
            opt["activity_level"] = "moderate"

    # Compute GCD
    result = find_greatest_common_divisor(options, profiles)

    if args.simulate_votes:
        result["simulated_votes"] = simulate_group_votes(options, profiles)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(result["recommendation"])
    print()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
