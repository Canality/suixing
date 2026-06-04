#!/usr/bin/env python3
"""Group chat voting state machine for collaborative travel decisions.

Handles:
  1. Presenting options for group vote
  2. Tallying emoji reactions (👍/👎, 1️⃣/2️⃣/3️⃣)
  3. Timeout-based auto-resolution
  4. Quorum detection (all members voted)

Usage:
  python group_voting.py \
      --init --options-file /tmp/vote_options.json \
      --group-size 3 \
      --output /tmp/vote_session.json

  python group_voting.py \
      --tally --session-file /tmp/vote_session.json \
      --reactions-file /tmp/reactions.json \
      --output /tmp/vote_result.json
"""

import json
import argparse
import os
from datetime import datetime, timezone, timedelta


def init_vote_session(options: list, group_size: int, timeout_minutes: int = 10) -> dict:
    """Create a new voting session with formatted poll messages."""
    if len(options) < 2:
        return {"error": "need at least 2 options", "session": None}

    emoji_pool = ["1️⃣", "2️⃣", "3️⃣"]
    poll_options = []
    for i, opt in enumerate(options[:3]):
        poll_options.append({
            "id": f"opt_{i+1}",
            "emoji": emoji_pool[i],
            "label": opt.get("label", f"Option {i+1}"),
            "summary": opt.get("summary", ""),
            "details": opt.get("details", {}),
            "votes": 0
        })

    session = {
        "session_id": f"vote_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "open",
        "group_size": group_size,
        "timeout_minutes": timeout_minutes,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)).isoformat(),
        "options": poll_options,
        "voter_ids": [],
        "quorum_reached": False,
        "winner": None
    }

    poll_message = _format_poll_message(poll_options, session["session_id"])

    return {
        "session": session,
        "poll_message": poll_message,
        "agent_script": _build_agent_script(poll_options, group_size, timeout_minutes)
    }


def _format_poll_message(options: list, session_id: str) -> str:
    lines = ["📊 **群聊投票：选哪个方案？**", ""]
    for opt in options:
        lines.append(f"{opt['emoji']} **{opt['label']}**")
        lines.append(f"   {opt['summary']}")
        lines.append("")
    lines.append(f"👥 共 X 人参与投票 | ⏰ X 分钟后截止")
    lines.append(f"📋 会话: `{session_id}`")
    return "\n".join(lines)


def _build_agent_script(options: list, group_size: int, timeout_min: int) -> str:
    """Generate conversational script for the Agent to follow."""
    lines = []
    lines.append("# 群聊投票 Agent 执行脚本")
    lines.append("")
    lines.append("## 第一轮：抛出方案")
    lines.append("")
    lines.append("发送投票消息（不要直接贴JSON），用自然语言：")
    lines.append("")
    lines.append(f'> "大家看看这三个方案！咱们{group_size}个人一起投个票——')
    lines.append(f'> 觉得哪个方案好就点对应的emoji，{timeout_min}分钟后截止。"')
    lines.append("")

    for i, opt in enumerate(options):
        lines.append(f"**{opt['emoji']} {opt['label']}**")
        lines.append(f"{opt['summary']}")
        lines.append("")

    lines.append("## 第二轮：中间提醒（如超过半数时间无人投票）")
    lines.append("")
    lines.append(f'> "还有人要看吗？现在{options[0]["emoji"]}领先，有不同意见的快投票~"')
    lines.append("")

    lines.append("## 第三轮：投票截止 → 执行 --tally")
    lines.append("")
    lines.append("统计结果，宣布获胜方案。然后自动进入行程生成。")

    return "\n".join(lines)


def tally_votes(session: dict, reactions: list, member_ids: list) -> dict:
    """Tally emoji reactions and determine winner."""
    if session.get("status") == "closed":
        return {"error": "session already closed", "result": session}

    emoji_to_opt = {opt["emoji"]: opt["id"] for opt in session["options"]}

    vote_counts = {opt["id"]: 0 for opt in session["options"]}
    voters = set()

    for r in reactions:
        emoji = r.get("emoji", "")
        voter = r.get("voter_id", "")
        if emoji in emoji_to_opt:
            opt_id = emoji_to_opt[emoji]
            vote_counts[opt_id] += 1
            voters.add(voter)

    for opt in session["options"]:
        opt["votes"] = vote_counts[opt["id"]]

    session["voter_ids"] = list(voters)
    session["total_votes"] = len(voters)
    session["group_size"] = max(session.get("group_size", 1), len(member_ids))
    session["quorum_reached"] = len(voters) >= session["group_size"]
    session["status"] = "closed"
    session["closed_at"] = datetime.now(timezone.utc).isoformat()

    # Determine winner: most votes, ties broken by first option
    winner = max(session["options"], key=lambda o: o["votes"])
    max_votes = winner["votes"]

    # Check for tie
    tied = [o for o in session["options"] if o["votes"] == max_votes]
    if len(tied) > 1 and max_votes > 0:
        winner = tied[0]  # First listed wins ties
        session["tie_broken"] = True
        session["tie_options"] = [t["id"] for t in tied]
    else:
        session["tie_broken"] = False

    session["winner"] = {
        "option_id": winner["id"],
        "label": winner["label"],
        "votes": winner["votes"],
        "details": winner.get("details", {})
    }

    result_message = _format_result_message(session)

    return {
        "result": session,
        "result_message": result_message,
        "next_action": f"Winner: {winner['label']}. Proceed to itinerary generation with {winner['details']}."
    }


def _format_result_message(session: dict) -> str:
    lines = ["📊 **投票结果**", ""]

    total = session.get("total_votes", 0)
    for opt in session["options"]:
        pct = f"{opt['votes'] / total * 100:.0f}%" if total > 0 else "0%"
        bar = "█" * opt["votes"] + "░" * (total - opt["votes"]) if total > 0 else "░░░"
        lines.append(f"{opt['emoji']} **{opt['label']}**：{opt['votes']}票 {pct}")
        lines.append(f"   {bar}")
        lines.append("")

    if session.get("quorum_reached"):
        lines.append(f"✅ {session['group_size']}/{session['group_size']}人已投票，全员达成共识！")
    else:
        lines.append(f"👥 {total}/{session.get('group_size', '?')}人已投票")

    if session.get("tie_broken"):
        tied_labels = session.get("tie_options", [])
        lines.append(f"⚡ 票数持平，选择第一个提出的方案：**{session['winner']['label']}**")

    winner = session.get("winner", {})
    lines.append("")
    lines.append(f"🏆 获胜方案：**{winner.get('label', 'N/A')}**（{winner.get('votes', 0)}票）")
    lines.append("")
    lines.append("接下来我会按这个方案生成详细行程。")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Group chat voting state machine")
    sub = parser.add_subparsers(dest="command")

    # --init mode
    init_parser = sub.add_parser("init", help="Create new voting session")
    init_parser.add_argument("--options-file", required=True, help="JSON file with option definitions")
    init_parser.add_argument("--group-size", type=int, default=3, help="Number of group members")
    init_parser.add_argument("--timeout-minutes", type=int, default=10, help="Vote timeout in minutes")
    init_parser.add_argument("--output", required=True, help="Output vote session JSON")

    # --tally mode
    tally_parser = sub.add_parser("tally", help="Tally votes and determine winner")
    tally_parser.add_argument("--session-file", required=True, help="Vote session JSON from init")
    tally_parser.add_argument("--reactions", required=True, help="JSON array of {emoji, voter_id} reactions")
    tally_parser.add_argument("--member-ids", required=True, help="JSON array of group member IDs")
    tally_parser.add_argument("--output", required=True, help="Output vote result JSON")

    args = parser.parse_args()

    if args.command == "init":
        with open(args.options_file, "r", encoding="utf-8") as f:
            options = json.load(f)

        result = init_vote_session(
            options if isinstance(options, list) else options.get("options", []),
            args.group_size,
            args.timeout_minutes
        )

        if result.get("session"):
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result["session"], f, ensure_ascii=False, indent=2)

        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "tally":
        with open(args.session_file, "r", encoding="utf-8") as f:
            session = json.load(f)

        with open(args.reactions, "r", encoding="utf-8") as f:
            reactions = json.load(f)

        with open(args.member_ids, "r", encoding="utf-8") as f:
            member_ids = json.load(f)

        result = tally_votes(
            session,
            reactions if isinstance(reactions, list) else [],
            member_ids if isinstance(member_ids, list) else []
        )

        if result.get("result"):
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result["result"], f, ensure_ascii=False, indent=2)

        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
