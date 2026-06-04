#!/usr/bin/env python3
"""Feishu Chat Bridge — 飞书消息 ↔ OpenClaw Agent 对话桥接器。

接收飞书用户消息，调用 DeepSeek Agent 处理，返回回复到飞书。
支持两种模式: lark-cli (本地CLI发送) 和 webhook (飞书回调)。

Usage:
  python feishu_chat_bridge.py --mode lark-cli --user-id "ou_xxx" --message "端午想去哪玩"
  python feishu_chat_bridge.py --mode webhook --webhook-url "https://..." --message "..."
"""

import json
import argparse
import os
import re
import sys
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
ANTI_HALLUCINATION_PROMPT = os.path.join(CONFIG_DIR, "anti_hallucination_prompt.md")
AGENT_INSTRUCTIONS = os.path.join(PROJECT_ROOT, "agent_instructions.md")

# ── System Prompt Builder ──────────────────────────────────────

def build_system_prompt(user_message: str, user_profile: dict = None) -> str:
    """Build a concise system prompt with anti-hallucination rules injected."""
    anti_hallucination_rules = ""
    if os.path.exists(ANTI_HALLUCINATION_PROMPT):
        with open(ANTI_HALLUCINATION_PROMPT, "r", encoding="utf-8") as f:
            content = f.read()
            # Extract only the key rules (rules 1-8, the source/labeling rules)
            anti_hallucination_rules = content[:3000]

    profile_text = ""
    if user_profile:
        profile_text = f"\n## 用户资料\n- 出发城市: {user_profile.get('home_city', '北京')}\n- 预算偏好: {json.dumps(user_profile.get('budget_preference', {}), ensure_ascii=False)}\n- 偏好目的地类型: {user_profile.get('destination_types', [])}\n"

    return f"""你是美团AI旅行管家。用温暖专业的语气回复用户。

## 核心规则 (最高优先级)
1. 每个具体数据点后必须标注来源: [12306] [美团] [携程] [航司官网]
2. 价格必须来自搜索结果，禁止推测("大约""通常")
3. 搜索结果为空时诚实告知，不要编造
4. 推荐方案后提醒用户去官方平台验证

{anti_hallucination_rules[:2000]}

{profile_text}

当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
回复语言: 中文
回复格式: 先给出助手回复，然后在 [管家思考:...] 中简要说明推理过程"""


# ── Agent Call ─────────────────────────────────────────────────

def call_deepseek_agent(user_message: str, system_prompt: str, api_key: str = None,
                        timeout: int = 120, max_retries: int = 2) -> dict:
    """Call DeepSeek API as the agent backend."""
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "No DEEPSEEK_API_KEY configured"}

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream": False
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return {"ok": True, "reply": content, "model": data.get("model", ""),
                    "usage": data.get("usage", {})}
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:500]}"
        except Exception as e:
            last_error = str(e)

    return {"ok": False, "error": last_error or "Unknown error",
            "reply": "抱歉，我暂时无法处理你的请求。请稍后再试，或者直接告诉我你想了解什么？"}


# ── JSON Extraction ────────────────────────────────────────────

def extract_json_from_reply(reply: str) -> dict:
    """Robust JSON extraction from agent reply with bracket handling."""
    try:
        return json.loads(reply)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block
    patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(\{.*?\})\s*\n```',
        r'\{[^{}]*"action"[^{}]*\}',
    ]
    for pattern in patterns:
        match = re.search(pattern, reply, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return {}


def extract_reply_text(reply: str) -> str:
    """Extract clean reply text, stripping [管家思考] blocks."""
    # Remove thinking blocks
    reply = re.sub(r'\[管家思考:.*?\]', '', reply, flags=re.DOTALL)
    reply = re.sub(r'\[管家思考\].*', '', reply, flags=re.DOTALL)
    # Clean up extra whitespace
    reply = '\n'.join(line for line in reply.split('\n') if line.strip())
    return reply.strip()


# ── Feishu Send ────────────────────────────────────────────────

def send_via_lark_cli(message: str, user_id: str, chat_id: str = None) -> dict:
    """Send message via lark-cli."""
    cmd = ["lark-cli", "im", "message", "send",
           "--receive-id-type", "open_id",
           "--receive-id", user_id,
           "--msg-type", "text",
           "--content", json.dumps({"text": message}, ensure_ascii=False)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
        return {"ok": result.returncode == 0, "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else ""}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_via_webhook(webhook_url: str, message: str) -> dict:
    """Send text message via Feishu webhook."""
    body = json.dumps({"msg_type": "text", "content": {"text": message}},
                      ensure_ascii=False)
    req = urllib.request.Request(
        webhook_url, data=body.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": True, "status": resp.status,
                    "body": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code,
                "body": e.read().decode("utf-8", errors="replace")}


# ── Post-Process: Official Verification Guidance ────────────────

def post_process(reply: str) -> str:
    """Append official verification guidance if reply contains recommendations."""
    triggers = ["G", "D", "CA", "CZ", "MU", "MF", "HU", "3U", "航班", "高铁",
                "酒店", "票价", "¥"]
    has_recommendation = any(t in reply for t in triggers)

    if has_recommendation and "官方" not in reply[-200:]:
        reply += ("\n\n---\n💡 以上信息来自我的实时搜索，建议你打开12306 APP或美团确认一下实时价格"
                  "和余票。节假日热门线路票走得很快，以官方实时数据为准。")

    return reply


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Feishu Chat Bridge — 飞书消息 ↔ Agent 对话桥接器")
    parser.add_argument("--mode", choices=["lark-cli", "webhook", "dry-run"],
                        default="dry-run", help="运行模式")
    parser.add_argument("--user-id", default=os.environ.get("FEISHU_USER_ID", ""),
                        help="飞书用户 open_id (lark-cli 模式)")
    parser.add_argument("--chat-id", default=os.environ.get("FEISHU_CHAT_ID", ""),
                        help="飞书群聊 chat_id")
    parser.add_argument("--webhook-url", default=os.environ.get("FEISHU_WEBHOOK_URL", ""),
                        help="飞书机器人 Webhook URL")
    parser.add_argument("--message", required=True, help="用户消息内容")
    parser.add_argument("--api-key", default="", help="DeepSeek API Key")
    parser.add_argument("--timeout", type=int, default=120, help="Agent 调用超时(秒)")
    parser.add_argument("--no-post-process", action="store_true",
                        help="跳过官方验证引导")
    args = parser.parse_args()

    # Step 1: Build system prompt
    system_prompt = build_system_prompt(args.message)

    # Step 2: Call agent
    if args.mode == "dry-run":
        result = {
            "ok": True,
            "reply": f"[Dry-run] 用户消息已收到: {args.message[:50]}...\n\n"
                     f"系统提示词长度: {len(system_prompt)} 字符\n"
                     f"Agent 调用将被跳过 (dry-run 模式)",
            "model": "dry-run",
            "usage": {}
        }
    else:
        result = call_deepseek_agent(
            args.message, system_prompt, api_key=args.api_key, timeout=args.timeout)

    if not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    reply = result["reply"]

    # Step 3: Post-process (official verification guidance)
    if not args.no_post_process:
        reply = post_process(reply)

    # Step 4: Send reply via Feishu
    send_result = {"ok": True, "mode": args.mode, "sent": False}
    if args.mode == "lark-cli" and args.user_id:
        send_result = send_via_lark_cli(reply, args.user_id, args.chat_id)
    elif args.mode == "webhook" and args.webhook_url:
        send_result = send_via_webhook(args.webhook_url, reply)

    # Step 5: Output
    output = {
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "mode": args.mode,
        "message_length": len(args.message),
        "reply_length": len(reply),
        "reply": reply,
        "model": result.get("model", ""),
        "usage": result.get("usage", {}),
        "feishu_send": send_result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
