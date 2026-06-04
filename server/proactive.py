"""LLM驱动的主动通知引擎 — 理解用户意图+痛点，自主判断是否推送。

每 N 秒:
1. 读取用户画像 + 最近对话摘要 + 沙盒事件
2. 交给 LLM 自主判断: "事件是否触及用户痛点/影响用户计划?"
3. 如果 LLM 认为值得通知 → 生成推送消息 → 通过 SSE 推送到前端
"""

import json
import sys
import time
import threading
from datetime import datetime
from server.llm import chat
from server.memory import memory
from mock_backend.event_engine import get_recent_events


# ── 轻量会话上下文（供 ProactiveBrain 读取） ──────────────

_last_context: str = ""
_context_lock = threading.Lock()


def update_context(user_msg: str, reply_summary: str):
    """Session 每轮对话后调用，更新上下文供 ProactiveBrain 使用。"""
    global _last_context
    with _context_lock:
        t = datetime.now().strftime("%H:%M")
        _last_context = f"[{t}] 用户说: {user_msg[:120]}\n[{t}] 助手回复: {reply_summary[:120]}"


def _get_context() -> str:
    with _context_lock:
        return _last_context


# ── Prompt 构建 ──────────────────────────────────────────

def _build_proactive_prompt(profile_text: str, recent_events: list, context: str, last_notify: str = "") -> str:
    events_text = ""
    for e in recent_events[-12:]:
        t = e.get("time", "")
        if isinstance(t, str) and len(t) >= 16:
            t = t[11:16]
        else:
            t = ""
        events_text += f"- [{t}] {e.get('message', '')}\n"

    if not events_text:
        events_text = "(暂无新事件)"

    # 从画像中提取户外相关偏好
    outdoor_hint = ""
    if any(w in profile_text for w in ["骑行", "跑步", "户外", "公园", "野餐", "骑车"]):
        outdoor_hint = "\n**用户有户外活动偏好，天气变化(雨/高温/空气质量差)必须通知！**"
    if "怕热" in profile_text:
        outdoor_hint += "\n**用户怕热，温度>32°C必须通知！**"

    return f"""你是随行(SuiXing)的主动通知大脑。检查环境变化，判断是否主动推送消息。

## 用户画像
{profile_text}
{outdoor_hint}

## 最近对话
{context or "(暂无对话)"}

## 最新环境事件
{events_text}

## 上次已通知用户
{last_notify if last_notify else "(从未通知过)"}

**如果最新事件与上次通知是同类型同原因，不要重复通知——回复 SILENT。**

## 判断标准
满足以下任一条件就通知:
1. 天气变坏(雨/雷阵雨/高温) + 用户有户外计划或户外偏好 → 必须通知
2. 用户想去的场所关闭/异常 → 必须通知
3. 空气质量变差 + 户外活动偏好 → 通知
4. 用户关注的餐厅排队激增 → 通知

不通知的情况:
- 天气变化但与用户无关（用户在室内/无户外偏好）
- 事件发生在用户不关心的区域或类型

## 回复格式（严格）
- 不需要通知: 只回复 `SILENT`
- 需要通知: 回复 `NOTIFY: <推送消息>`

推送消息格式: "小明，<发生什么>，<建议>"
消息不超过80字，emoji最多1个。

当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} (北京时区)
"""


# ── ProactiveBrain ────────────────────────────────────────

class ProactiveBrain:

    def __init__(self):
        self._last_event_time = ""  # 上次处理到的最新事件时间
        self._lock = threading.Lock()
        self._notification_callback = None
        self._check_count = 0
        self._last_notify_msg = ""  # 上次通知内容，防止重复推送同类消息

    def set_callback(self, callback):
        self._notification_callback = callback

    def check(self) -> str | None:
        """执行一次主动检查。返回推送消息或 None。"""
        try:
            self._check_count += 1

            # 1. 用户画像
            profile = memory.get_summary()
            if not profile or "(尚无记录)" in profile:
                if self._check_count <= 3:
                    print(f"[ProactiveBrain] 第{self._check_count}次检查: 无用户画像，跳过")
                return None

            # 2. 最近事件 — 检查是否有新事件(按时间而非计数)
            events = get_recent_events(limit=50)
            if not events:
                return None

            newest_time = events[-1].get("time", "")
            if newest_time == self._last_event_time and self._check_count > 1:
                return None  # 没有新事件，跳过(节省API调用)
            self._last_event_time = newest_time

            # 3. 防重复: 如果上次已通知过，告诉LLM避免重复
            last_notify = self._last_notify_msg

            # 4. 最近对话上下文
            context = _get_context()

            # 5. 交给LLM判断
            prompt = _build_proactive_prompt(profile, events, context, last_notify)
            print(f"[ProactiveBrain] 第{self._check_count}次检查: {len(events)}条事件, ctx={len(context)}chars", flush=True)

            result = chat(
                system_prompt=prompt,
                user_message="请检查以上事件，判断是否需要通知用户。",
                history=[],
            )

            if not result.get("ok"):
                print(f"[ProactiveBrain] LLM调用失败: {result.get('error', '')}", flush=True)
                return None

            reply = result.get("reply", "").strip()
            print(f"[ProactiveBrain] LLM回复({len(reply)}chars): {reply[:120]}", flush=True)

            if reply.upper().startswith("SILENT"):
                return None

            if "NOTIFY:" in reply.upper():
                idx = reply.upper().find("NOTIFY:") + 7
                msg = reply[idx:].strip()
                if msg:
                    self._last_notify_msg = msg
                    print(f"[ProactiveBrain] 决定通知: {msg[:80]}", flush=True)
                    return msg

            return None

        except Exception as e:
            print(f"[ProactiveBrain] 异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None


# 全局单例
brain = ProactiveBrain()


def start_proactive_loop(interval: float = 30.0, on_notify=None):
    """启动后台主动通知线程。"""
    brain.set_callback(on_notify)

    def loop():
        time.sleep(10)  # 首次等10秒让系统初始化
        print("[ProactiveBrain] 主动通知循环已启动", flush=True)
        while True:
            time.sleep(interval)
            try:
                msg = brain.check()
                if msg and on_notify:
                    print(f"[ProactiveBrain] 推送通知到SSE", flush=True)
                    on_notify(msg)
            except Exception as e:
                print(f"[ProactiveBrain] 循环异常: {e}", flush=True)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
