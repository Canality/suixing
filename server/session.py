"""会话管理 — Agent核心逻辑: 意图路由、LLM协调、工具执行"""

import json
import time
from datetime import datetime
from server.prompts import build_system_prompt
from server.llm import chat_with_tools, chat
from server.tools import TOOLS, execute_tool_call
from server.event_bus import bus

MAX_HISTORY = 30  # 最大保留消息数

# 全局工具去重缓存: 10秒内相同调用不重复执行
_dedup: dict[str, float] = {}


def _dedup_key(tool_name: str, args: dict) -> str:
    return f"{tool_name}:{json.dumps(args, ensure_ascii=False, sort_keys=True)}"


def _is_duplicate(tool_name: str, args: dict, window: int = 10) -> bool:
    now = time.time()
    key = _dedup_key(tool_name, args)
    if key in _dedup and (now - _dedup[key]) < window:
        return True
    _dedup[key] = now
    # 清理过期条目
    stale = [k for k, v in _dedup.items() if now - v > window]
    for k in stale:
        del _dedup[k]
    return False


class Session:
    """单次对话会话，管理多轮对话状态。"""

    def __init__(self, session_id: str):
        self.id = session_id
        self.history: list[dict] = []
        self.created_at = datetime.now()
        self.turn_count = 0

    # ── 公开 API ──────────────────────────────────────────────

    async def handle_message(self, user_message: str) -> str:
        """处理用户消息，返回Agent回复。支持多轮工具调用(ReAct循环)。"""
        self.turn_count += 1
        system_prompt = build_system_prompt()

        await bus.emit_thinking("正在分析用户意图...")

        self._append("user", user_message)

        # ReAct 循环: LLM可连续调多轮工具，直到返回纯文本
        max_rounds = 5
        for round_num in range(max_rounds):
            result = chat_with_tools(
                system_prompt=system_prompt,
                user_message="" if round_num > 0 else user_message,
                tools=TOOLS,
                history=self.history,
            )

            if not result.get("ok"):
                await bus.emit_error(f"LLM调用失败: {result.get('error', '')}")
                if round_num == 0:
                    reply = self._fallback_reply(user_message)
                    self._update_proactive_context(user_message, reply)
                    return reply
                break

            # 纯文本 → 这是最终回复
            if result.get("type") != "tool_call":
                reply = result.get("reply", "")
                self._append("assistant", reply)
                await bus.emit_reply(reply)
                self._trim()
                self._log_memory(user_message, reply)
                self._update_proactive_context(user_message, reply)
                return reply

            # 工具调用 → 执行后继续循环
            tool_calls = result["tool_calls"]

            # 去重过滤
            unique_calls = []
            dropped = 0
            for tc in tool_calls:
                fn = tc["function"]
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                if not _is_duplicate(fn["name"], args):
                    unique_calls.append(tc)
                else:
                    dropped += 1

            if dropped:
                await bus.emit_thinking(f"已过滤 {dropped} 个重复工具调用")

            # 全部重复 → 跳过这轮，让LLM继续
            if not unique_calls:
                await bus.emit_thinking("所有工具调用均为重复，要求直接回复...")
                self._append("assistant", "所有工具调用均为重复。请基于已有信息直接回复用户。")
                continue

            await bus.emit_thinking(f"第{round_num + 1}轮: 执行 {len(unique_calls)} 个工具调用...")

            self._append("assistant", result.get("content") or "", unique_calls)

            # 执行工具
            tool_results = []
            for tc in unique_calls:
                fn = tc["function"]
                tool_name = fn["name"]
                try:
                    tool_args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}

                await bus.emit_tool_call(tool_name, tool_args)
                try:
                    tool_result = execute_tool_call(tool_name, tool_args)
                except Exception as e:
                    tool_result = {"error": f"工具执行异常: {e}"}
                    await bus.emit_error(f"{tool_name} 执行失败")
                await bus.emit_tool_result(tool_name, tool_result)

                tool_results.append({
                    "tool_call_id": tc["id"],
                    "role": "tool",
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

            self.history.extend(tool_results)

        # 超过最大轮数 → 强制生成回复
        await bus.emit_thinking("达到最大工具调用轮数，生成最终回复...")
        final = chat(system_prompt=system_prompt, user_message="请基于已获取的数据回复用户。", history=self.history)
        if final.get("ok"):
            reply = final["reply"]
        else:
            reply = self._fallback_reply(user_message)
        self._append("assistant", reply)
        await bus.emit_reply(reply)
        self._trim()
        self._update_proactive_context(user_message, reply)
        return reply

    # ── Watchdog 触发 ──────────────────────────────────────────

    async def trigger_watch(self, task) -> str:
        """Watchdog 触发后 LLM 自主推理入口 (复用 handle_message 的 ReAct 循环)。"""

        await bus.emit_thinking(f"🔔 监控触发: {task.target_name} — {task.condition}")

        trigger_msg = f"""🔔 后台监控触发！监控目标: {task.target_name}，条件: {task.condition}。
用户原始意图: {task.context}
行动指令: {task.trigger_instruction}
请自主调工具获取最新数据，生成主动推送消息（不要输出思考过程，直接说事），串联下一步。"""

        reply = await self.handle_message(trigger_msg)
        return reply

    # ── 内部辅助 ──────────────────────────────────────────────

    def _log_memory(self, user_msg: str, reply: str):
        """异步记录会话日志（非阻塞，异常静默吞掉）。"""
        try:
            from server.memory import memory
            summary = f"用户: {user_msg[:80]}... → Agent: {reply[:80]}..."
            memory.log_interaction(summary, [])
        except Exception:
            pass  # 日志失败不影响主流程

    def _update_proactive_context(self, user_msg: str, reply: str):
        """更新 ProactiveBrain 的对话上下文。"""
        try:
            from server.proactive import update_context
            # 提取回复摘要（取第一句）
            summary = reply.split("\n")[0][:120] if reply else ""
            update_context(user_msg, summary)
        except Exception:
            pass

    def _append(self, role: str, content: str, tool_calls: list = None):
        msg: dict = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)

    def _trim(self):
        """裁剪历史，保证不超过MAX_HISTORY条，且不拆散tool消息。"""
        if len(self.history) <= MAX_HISTORY:
            return
        # 找到安全切割点: 不能切断 tool_call→tool_result 链
        cut = len(self.history) - MAX_HISTORY
        # 让cut落在user消息上 (新的一轮开始)
        for i in range(cut, min(cut + 5, len(self.history))):
            if self.history[i].get("role") == "user":
                cut = i
                break
        self.history = self.history[cut:]

    # ── 兜底回复 ──────────────────────────────────────────────

    def _fallback_reply(self, user_message: str) -> str:
        msg = user_message.lower()
        if any(w in msg for w in ["饿", "吃", "餐厅", "火锅", "外卖"]):
            return (
                "我可以帮你搜索附近餐厅！不过LLM服务暂时不可用。\n"
                "建议打开 **大众点评App** 搜索望京附近的餐厅 [大众点评]"
            )
        if any(w in msg for w in ["去", "打车", "怎么走", "路", "通勤"]):
            return (
                "我可以帮你规划路线！不过LLM服务暂时不可用。\n"
                "建议打开 **高德地图** 查看实时路线 [高德]"
            )
        if any(w in msg for w in ["天气", "玩", "活动", "电影", "周末"]):
            return (
                "我可以帮你查看天气和活动！不过LLM服务暂时不可用。\n"
                "建议打开 **猫眼App** 看看有什么好玩的 [猫眼]"
            )
        return (
            "你好！我是随行，你的本地生活管家。\n"
            "我可以帮你找餐厅、规划路线、推荐周末活动。\n"
            '试试说「我饿了」「怎么去798」「周末有什么好玩的」？'
        )

    def _format_tool_results(self, tool_results: list) -> str:
        lines = []
        for tr in tool_results:
            try:
                data = json.loads(tr["content"])
            except json.JSONDecodeError:
                continue
            if "recommendations" in data:
                recs = data["recommendations"][:3]
                lines.append(f"🍜 找到 {len(recs)} 家餐厅: {', '.join(r['name'] for r in recs)}")
            elif "weather" in data:
                w = data["weather"]
                lines.append(f"🌤️ {w.get('condition','')} {w.get('temperature','')}°C")
            elif "routes" in data:
                r = data["routes"][0] if data["routes"] else {}
                lines.append(f"🚗 推荐{r.get('mode','')}: {r.get('duration_min','')}分钟")
            elif "activities" in data:
                acts = data["activities"][:3]
                lines.append(f"🎬 找到 {len(acts)} 个活动: {', '.join(a['name'] for a in acts)}")
        return "\n".join(lines) if lines else "已为你查询完毕。"


# 全局会话存储
_sessions: dict[str, Session] = {}


def get_or_create_session(session_id: str = "main") -> Session:
    if session_id not in _sessions:
        _sessions[session_id] = Session(session_id)
    return _sessions[session_id]
