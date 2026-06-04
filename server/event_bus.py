"""SSE 事件总线 — 实时推送 Agent 思考过程到前端技术面板"""

import asyncio
import json
from datetime import datetime


class EventBus:
    """简易SSE事件总线。每个前端连接一个Queue。"""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._queues:
            self._queues.remove(q)

    async def emit(self, event_type: str, data: dict):
        """向所有订阅者推送事件。"""
        payload = json.dumps({
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }, ensure_ascii=False)
        dead = []
        for q in self._queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._queues.remove(q)

    async def emit_thinking(self, message: str):
        await self.emit("thinking", {"message": message})

    async def emit_tool_call(self, tool: str, args: dict):
        await self.emit("tool_call", {"tool": tool, "args": args})

    async def emit_tool_result(self, tool: str, result: dict):
        await self.emit("tool_result", {"tool": tool, "result": result})

    async def emit_skill(self, skill: str):
        await self.emit("skill", {"skill": skill})

    async def emit_reply(self, text: str):
        await self.emit("reply", {"text": text})

    async def emit_error(self, message: str):
        await self.emit("error", {"message": message})

    async def emit_watch_created(self, task_id: str, target_name: str, watch_type: str, condition: str):
        await self.emit("watch_created", {
            "task_id": task_id,
            "target_name": target_name,
            "type": watch_type,
            "condition": condition,
        })

    async def emit_watch_triggered(self, task_id: str, target_name: str, condition: str, reply: str):
        await self.emit("watch_triggered", {
            "task_id": task_id,
            "target_name": target_name,
            "condition": condition,
            "reply": reply,
        })

    async def emit_watch_update(self, task_id: str, target_name: str, status: dict):
        await self.emit("watch_update", {
            "task_id": task_id,
            "target_name": target_name,
            "status": status,
        })


# 全局单例
bus = EventBus()
