"""LLM驱动的主动通知引擎 — 理解用户意图+痛点，自主判断是否推送。

不同于 watchdog（僵硬的 if-then 条件），ProactiveBrain 每 N 秒:
1. 读取用户画像 + 最近对话上下文
2. 读取沙盒最新事件(天气变化/排队变化/活动状态等)
3. 交给 LLM 自主判断: "这些事件是否触及用户痛点/影响用户计划?"
4. 如果 LLM 认为值得通知 → 生成推送消息 → 通过 SSE 推送到前端
"""

import json
import time
import threading
from datetime import datetime
from server.llm import chat
from server.memory import memory
from mock_backend.event_engine import get_recent_events
from mock_backend.mock_data import get_weather_state, get_restaurant_state


def _build_proactive_prompt(profile_text: str, recent_events: list, active_plans: str) -> str:
    """构建主动判断的 system prompt。"""
    events_text = ""
    for e in recent_events[-15:]:  # 最近15条事件
        t = e.get("time", "")[-8:-3] if e.get("time") else ""
        events_text += f"- [{t}] {e.get('message', '')}\n"

    if not events_text:
        events_text = "(暂无新事件)"

    return f"""你是随行(SuiXing)的主动通知大脑。你的任务是: 定期检查环境变化，判断是否需要主动推送消息给用户。

## 用户画像
{profile_text}

## 用户近期计划
{active_plans or "(暂无)"}

## 最近环境事件
{events_text}

## 判断标准（必须同时满足才通知）
1. **相关性**: 事件是否影响用户已表达的计划/意图？
2. **痛点匹配**: 事件是否触及以下用户痛点？
   - 用户怕热 → 温度突升/高温预警
   - 用户怕排队 → 餐厅排队人数激增
   - 用户有预算 → 价格变化
   - 雨天 → 用户计划了户外活动(骑行/跑步/公园)
   - 空气质量差 → 用户计划了户外活动
3. **时效性**: 事件是否需要用户立即知道并采取行动？

## 回复格式（严格）
- 如果**不需要通知**: 只回复 `SILENT`
- 如果**需要通知**: 回复 `NOTIFY: <推送消息>`

推送消息要求:
- 用"小明"称呼用户
- 一句话说清发生了什么变化
- 给出具体建议(改时间/换地点/备选方案)
- 不要超过80个字
- 不要用emoji超过2个

当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} (北京时区)
"""


class ProactiveBrain:
    """LLM自主判断的主动通知引擎。"""

    def __init__(self):
        self._last_event_count = 0
        self._lock = threading.Lock()
        self._notification_callback = None  # fn(message: str)

    def set_callback(self, callback):
        self._notification_callback = callback

    def check(self) -> str | None:
        """执行一次主动检查。返回推送消息或 None。"""
        try:
            # 1. 获取用户画像
            profile = memory.get_summary()
            if not profile or profile == "(尚无记录)":
                return None  # 没有用户画像，不打扰

            # 2. 获取用户近期计划 (从记忆系统提取)
            active_plans = memory.get_active_plans()

            # 3. 获取最近事件
            events = get_recent_events(limit=50)
            # 没有新事件，跳过
            new_count = len(events)
            if new_count <= self._last_event_count:
                return None
            self._last_event_count = new_count

            # 4. 交给LLM判断
            prompt = _build_proactive_prompt(profile, events, active_plans)
            result = chat(
                system_prompt=prompt,
                user_message="请检查以上事件，判断是否需要通知用户。",
                history=[],
            )

            if not result.get("ok"):
                return None

            reply = result.get("reply", "").strip()

            if reply.startswith("NOTIFY:"):
                msg = reply[7:].strip()
                return msg if msg else None
            return None

        except Exception:
            return None


# 全局单例
brain = ProactiveBrain()


def start_proactive_loop(interval: float = 30.0, on_notify=None):
    """启动后台主动通知线程。on_notify(message) 在LLM决定推送时被调用。

    interval: 检查间隔(秒)。Demo 环境 30 秒，生产环境可调大到 5 分钟。
    """
    brain.set_callback(on_notify)

    def loop():
        # 首次等待30秒让系统初始化
        time.sleep(30)
        while True:
            time.sleep(interval)
            try:
                msg = brain.check()
                if msg and on_notify:
                    on_notify(msg)
            except Exception:
                pass

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
