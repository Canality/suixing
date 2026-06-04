"""LLM 客户端 — 调用 DeepSeek API (兼容 OpenAI 格式)"""

import json
import re
import urllib.request
import urllib.error
from server.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def _parse_xml_tool_calls(text: str) -> list | None:
    """解析 DeepSeek 可能输出的 XML 格式工具调用 (兜底)。

    支持三种格式:
    1. <invoke name="tool_name"><parameter...>...</invoke>  (带参数)
    2. <invoke name="tool_name"/>  (自闭合, 无参数)
    3. <function_call>{"name":"x","arguments":"..."}</function_call>  (JSON格式)
    """
    calls = []
    # 格式1a: <invoke name="xxx">...</invoke> (带参数)
    for m in re.finditer(r'<invoke\s+name="(\w+)"\s*>(.*?)</invoke>', text, re.DOTALL):
        tool_name = m.group(1)
        params_block = m.group(2)
        args = {}
        for pm in re.finditer(r'<parameter\s+name="(\w+)"\s+string="true">(.*?)</parameter>', params_block):
            args[pm.group(1)] = pm.group(2)
        for pm in re.finditer(r'<parameter\s+name="(\w+)">(\d+)</parameter>', params_block):
            args[pm.group(1)] = int(pm.group(2))
        calls.append({"name": tool_name, "args": args})

    # 格式1b: <invoke name="xxx"/> (自闭合, 无参数) — 避免重复匹配格式1a的
    for m in re.finditer(r'<invoke\s+name="(\w+)"\s*/>', text):
        name = m.group(1)
        # 检查是否已被格式1a匹配过
        if not any(c["name"] == name for c in calls):
            calls.append({"name": name, "args": {}})

    # 格式2: <function_call>{"name":"x","arguments":"..."}</function_call>
    for m in re.finditer(r'<function_call>\s*(\{.*?\})\s*</function_call>', text, re.DOTALL):
        try:
            raw = m.group(1).replace('\\"', '"').replace('\\\\', '\\')
            fc = json.loads(raw)
            name = fc.get("name", "")
            args_str = fc.get("arguments", "{}")
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
            calls.append({"name": name, "args": args})
        except (json.JSONDecodeError, TypeError):
            continue

    return calls if calls else None


def _build_tool_calls(parsed_calls: list) -> list:
    """将解析出的 {name, args} 列表转为 OpenAI 格式的 tool_calls。"""
    tool_calls = []
    for i, c in enumerate(parsed_calls):
        tool_calls.append({
            "id": f"xml_{i}",
            "type": "function",
            "function": {
                "name": c["name"],
                "arguments": json.dumps(c["args"], ensure_ascii=False),
            },
        })
    return tool_calls


def chat(system_prompt: str, user_message: str,
         history: list = None, stream: bool = False,
         timeout: int = 60) -> dict:
    """调用LLM，返回回复文本。"""

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    if user_message:
        messages.append({"role": "user", "content": user_message})

    body = json.dumps({
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream": False,
    }, ensure_ascii=False)

    url = f"{LLM_BASE_URL}/chat/completions"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return {
                "ok": True,
                "reply": content,
                "model": data.get("model", ""),
                "usage": data.get("usage", {}),
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {e.code}: {body[:500]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def chat_with_tools(system_prompt: str, user_message: str,
                    tools: list, history: list = None,
                    timeout: int = 90) -> dict:
    """调用LLM(带工具)，返回工具调用或文本回复。"""

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    if user_message:
        messages.append({"role": "user", "content": user_message})

    body = json.dumps({
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
        "tools": tools,
        "tool_choice": "auto",
    }, ensure_ascii=False)

    url = f"{LLM_BASE_URL}/chat/completions"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            msg = choice.get("message", {})

            if msg.get("tool_calls"):
                return {
                    "ok": True,
                    "type": "tool_call",
                    "tool_calls": msg["tool_calls"],
                    "content": msg.get("content", ""),
                }

            # 兜底: DeepSeek 有时把 tool call 写在文本里而不是原生 tool_calls
            content = msg.get("content", "")
            xml_calls = _parse_xml_tool_calls(content)
            if xml_calls:
                return {
                    "ok": True,
                    "type": "tool_call",
                    "tool_calls": _build_tool_calls(xml_calls),
                    "content": content,
                }

            return {
                "ok": True,
                "type": "text",
                "reply": content,
                "usage": data.get("usage", {}),
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        return {"ok": False, "error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
