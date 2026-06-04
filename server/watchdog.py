"""后台监控引擎 — LLM定义条件，Watchdog评估条件，触发后交还LLM推理。

职责边界:
- Watchdog: 程序化评估条件（可靠、高效，不调LLM）
- LLM: 定义条件 + 触发后推理（灵活、智能）
"""

import re
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from mock_backend.mock_data import get_restaurant_state, get_weather_state, get_activity_state


@dataclass
class WatchTask:
    id: str
    type: str                  # queue_threshold | weather_change | ticket_available | time_point
    target_id: str             # 餐厅ID / 活动ID / 留空
    target_name: str           # 显示名称
    condition: str             # LLM定义的触发条件表达式
    trigger_instruction: str   # 触发后LLM的行动指令
    context: str               # 用户原始意图上下文
    session_id: str = "main"
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    triggered_at: str = ""


class Watchdog:
    """后台监控引擎。程序化评估LLM定义的条件，触发后回调上层。"""

    def __init__(self):
        self._tasks: dict[str, WatchTask] = {}
        self._lock = threading.Lock()

    # ── 任务管理 ──────────────────────────────────────────────

    def add_task(self, task: WatchTask):
        with self._lock:
            self._tasks[task.id] = task

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks and self._tasks[task_id].status == "active":
                self._tasks[task_id].status = "done"
                return True
            return False

    def list_tasks(self, session_id: str = None) -> list[WatchTask]:
        with self._lock:
            tasks = list(self._tasks.values())
            if session_id:
                tasks = [t for t in tasks if t.session_id == session_id]
            return [t for t in tasks if t.status == "active"]

    def get_task(self, task_id: str) -> WatchTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    # ── 条件评估 ──────────────────────────────────────────────

    def evaluate_all(self) -> list[WatchTask]:
        """评估所有活跃任务，返回触发的任务列表。"""
        triggered: list[WatchTask] = []
        with self._lock:
            for task in list(self._tasks.values()):
                if task.status != "active":
                    continue
                if self._evaluate(task):
                    task.status = "triggered"
                    task.triggered_at = datetime.now().isoformat()
                    triggered.append(task)
        return triggered

    def _evaluate(self, task: WatchTask) -> bool:
        try:
            if task.type == "queue_threshold":
                return self._eval_queue(task)
            elif task.type == "weather_change":
                return self._eval_weather(task)
            elif task.type == "ticket_available":
                return self._eval_ticket(task)
            elif task.type == "time_point":
                return self._eval_time(task)
        except Exception:
            return False
        return False

    def _eval_queue(self, task: WatchTask) -> bool:
        state = get_restaurant_state().get(task.target_id, {})
        data = {"queue_length": state.get("queue_length", 999)}
        return self._check_condition(data, task.condition)

    def _eval_weather(self, task: WatchTask) -> bool:
        state = get_weather_state()
        return self._check_condition(state, task.condition)

    def _eval_ticket(self, task: WatchTask) -> bool:
        state = get_activity_state().get(task.target_id, {})
        return self._check_condition(state, task.condition)

    def _eval_time(self, task: WatchTask) -> bool:
        now = datetime.now()
        return self._check_condition({"hour": now.hour, "minute": now.minute}, task.condition)

    def _check_condition(self, data: dict, condition: str) -> bool:
        """安全评估LLM定义的简单条件表达式。

        支持: field(.subfield)* op value
          例: queue_length <= 5, forecast.evening in ('雨','雷阵雨')
          op ∈ {<=, >=, ==, !=, <, >, in, not in}
        """
        pattern = r"^([\w.]+)\s*(<=|>=|==|!=|<|>|not in|in)\s*(.+)$"
        m = re.match(pattern, condition.strip())
        if not m:
            return False
        field_path, op, value_str = m.groups()

        # 支持 dot notation: forecast.evening → data["forecast"]["evening"]
        actual = data
        for part in field_path.split("."):
            if isinstance(actual, dict) and part in actual:
                actual = actual[part]
            else:
                return False
        value_str = value_str.strip()

        # 解析比较值
        if value_str.startswith("(") and value_str.endswith(")"):
            inner = value_str[1:-1]
            expected = [v.strip().strip("'\"") for v in inner.split(",")]
        elif value_str.isdigit():
            expected = int(value_str)
        elif value_str.replace(".", "", 1).replace("-", "", 1).isdigit():
            expected = float(value_str) if "." in value_str else int(value_str)
        else:
            expected = value_str.strip("'\"")

        if op == "<=": return actual <= expected
        if op == ">=": return actual >= expected
        if op == "<":  return actual < expected
        if op == ">":  return actual > expected
        if op == "==": return actual == expected
        if op == "!=": return actual != expected
        if op == "in":     return actual in expected
        if op == "not in": return actual not in expected
        return False


# 全局单例
watchdog = Watchdog()


def start_watchdog_loop(interval: float = 15.0, on_trigger=None):
    """启动后台监控线程。on_trigger(task) 在触发时被调用。"""

    def loop():
        while True:
            time.sleep(interval)
            try:
                triggered = watchdog.evaluate_all()
                for task in triggered:
                    if on_trigger:
                        on_trigger(task)
            except Exception:
                pass

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
