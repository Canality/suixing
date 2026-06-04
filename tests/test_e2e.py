"""端到端测试 — 测试完整Agent链路: 会话管理、配置、提示词、工具执行、事件总线。

需要 Mock Server 在 localhost:8010 运行。
"""

import json
import os
import sys
import io
import urllib.request
import urllib.error

# Fix Unicode output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MOCK_API = os.environ.get("MOCK_API_URL", "http://localhost:8010")

pass_count = 0
fail_count = 0


def test(name: str, condition: bool):
    global pass_count, fail_count
    if condition:
        print(f"  ✅ {name}")
        pass_count += 1
    else:
        print(f"  ❌ {name} FAILED")
        fail_count += 1


def api_get(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{MOCK_API}{path}", timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def api_post(path: str, body: dict) -> dict:
    try:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{MOCK_API}{path}", data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def run_tests():
    global pass_count, fail_count
    print("=" * 60)
    print("E2E 测试")
    print("=" * 60)

    # ===================================================================
    # 服务器健康
    # ===================================================================
    print("\n🏥 Server Health")
    h = api_get("/api/health")
    test("Health endpoint ok", h.get("ok") is True)
    test("Health返回service名称", h.get("service") == "SuiXing Demo Server")

    info = api_get("/api/info")
    test("Info有3个技能", len(info.get("skills", [])) == 3)
    test("Info包含dining-advisor", "dining-advisor" in info.get("skills", []))
    test("Info包含commute-planner", "commute-planner" in info.get("skills", []))
    test("Info包含leisure-scout", "leisure-scout" in info.get("skills", []))

    # ===================================================================
    # 配置加载
    # ===================================================================
    print("\n⚙️ Configuration")
    from server.config import (
        LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
        WORKSPACE_DIR, MOCK_API_URL, HOST, PORT,
        load_workspace_file, load_skill_md, get_skill_scripts_dir,
    )
    test("LLM API Key已加载", len(LLM_API_KEY) > 0)
    test("LLM Base URL正确", "deepseek.com" in LLM_BASE_URL)
    test("LLM Model已设置", len(LLM_MODEL) > 0)
    test("Workspace目录存在", os.path.isdir(WORKSPACE_DIR))
    test("Workspace目录名正确", os.path.basename(WORKSPACE_DIR) == "openclaw-workspace")

    # Workspace文件
    soul = load_workspace_file("SOUL.md")
    test("SOUL.md已加载", len(soul) > 0)
    test("SOUL.md包含随行", "随行" in soul)

    agents = load_workspace_file("AGENTS.md")
    test("AGENTS.md已加载", len(agents) > 0)

    anti = load_workspace_file("anti_hallucination_prompt.md")
    test("anti_hallucination已加载", len(anti) > 0)
    test("anti_hallucination含来源标签", "[大众点评]" in anti)

    user_md = load_workspace_file("USER.md")
    test("USER.md已加载", len(user_md) > 0)

    # Skill文件
    for skill in ["dining-advisor", "commute-planner", "leisure-scout"]:
        md = load_skill_md(skill)
        test(f"Skill {skill} SKILL.md已加载", len(md) > 0)
        sd = get_skill_scripts_dir(skill)
        test(f"Skill {skill} scripts目录存在", os.path.isdir(sd))
        py_files = [f for f in os.listdir(sd) if f.endswith(".py")]
        test(f"Skill {skill} 有Python脚本", len(py_files) > 0)

    # ===================================================================
    # Prompt构建
    # ===================================================================
    print("\n📝 Prompt Building")
    from server.prompts import build_system_prompt, build_skill_prompt
    sys_prompt = build_system_prompt()
    test("System prompt已构建", len(sys_prompt) > 500)
    test("System prompt含随行", "随行" in sys_prompt)
    test("System prompt含SuiXing", "SuiXing" in sys_prompt)
    test("System prompt含反幻觉", "反幻觉" in sys_prompt)
    test("System prompt含dining-advisor", "dining-advisor" in sys_prompt)
    test("System prompt含来源标签", "[大众点评]" in sys_prompt or "[美团]" in sys_prompt)

    # Skill prompt
    dining_p = build_skill_prompt("dining-advisor")
    test("dining-advisor skill prompt有内容", len(dining_p) > 0)
    test("dining-advisor prompt含触发词", "火锅" in dining_p)

    commute_p = build_skill_prompt("commute-planner")
    test("commute-planner skill prompt有内容", len(commute_p) > 0)

    leisure_p = build_skill_prompt("leisure-scout")
    test("leisure-scout skill prompt有内容", len(leisure_p) > 0)

    # ===================================================================
    # 会话管理
    # ===================================================================
    print("\n💬 Session Management")
    from server.session import get_or_create_session, _sessions

    # 重置
    _sessions.clear()

    s1 = get_or_create_session("test_1")
    test("创建新会话", s1 is not None)
    test("会话ID正确", s1.id == "test_1")
    test("新会话历史为空", len(s1.history) == 0)

    s1_again = get_or_create_session("test_1")
    test("获取同一会话返回相同实例", s1 is s1_again)

    s2 = get_or_create_session("test_2")
    test("创建不同会话", s2.id == "test_2")
    test("不同会话不同实例", s1 is not s2)

    # 回退回复
    reply = s1._fallback_reply("我饿了想吃火锅")
    test("回退回复含餐厅提示", "餐" in reply or "店" in reply or "食" in reply)

    reply2 = s1._fallback_reply("怎么去798")
    test("回退回复含出行提示", "路" in reply2 or "打车" in reply2)

    reply3 = s1._fallback_reply("你好")
    test("回退回复含问候", "你好" in reply3 or "随行" in reply3)

    _sessions.clear()

    # ===================================================================
    # 工具执行
    # ===================================================================
    print("\n🔧 Tool Execution")
    from server.tools import execute_tool_call, TOOLS

    test("TOOLS定义有9个工具", len(TOOLS) == 9)
    tool_names = [t["function"]["name"] for t in TOOLS]
    test("包含search_restaurants", "search_restaurants" in tool_names)
    test("包含check_queue", "check_queue" in tool_names)
    test("包含plan_route", "plan_route" in tool_names)
    test("包含search_activities", "search_activities" in tool_names)
    test("包含get_weather", "get_weather" in tool_names)

    # 执行search_restaurants
    r = execute_tool_call("search_restaurants", {"area": "望京", "cuisine": "川菜"})
    test("search_restaurants含recommendations", "recommendations" in r)
    test("search_restaurants含total_found", "total_found" in r)

    # 执行check_queue
    q = execute_tool_call("check_queue", {"action": "check", "restaurant_id": "r001"})
    test("check_queue含status_text", "status_text" in q)

    # 执行plan_route
    rt = execute_tool_call("plan_route", {"origin": "望京SOHO", "destination": "798艺术区"})
    test("plan_route含routes", "total_routes" in rt)

    # 执行search_activities
    a = execute_tool_call("search_activities", {"category": "电影"})
    test("search_activities含activities", "activities" in a)

    # 执行get_weather
    w = execute_tool_call("get_weather", {})
    test("get_weather含weather", "weather" in w)

    # 未知工具
    unknown = execute_tool_call("unknown_tool", {})
    test("未知工具返回error", "error" in unknown)

    # create_watch
    wc = execute_tool_call("create_watch", {
        "watch_type": "queue_threshold", "target_name": "测试监控",
        "condition": "queue_length <= 5", "trigger_instruction": "测试触发"
    })
    test("create_watch返回ok", wc.get("ok") is True)
    test("create_watch有task_id", "task_id" in wc)

    # remember
    rm = execute_tool_call("remember", {
        "category": "food", "key": "cuisines_liked", "value": "川菜", "confidence": "confirmed"
    })
    test("remember返回ok", rm.get("ok") is True)

    # get_user_profile
    gp = execute_tool_call("get_user_profile", {"query": "上次吃的餐厅"})
    test("get_user_profile返回ok", gp.get("ok") is True)
    test("get_user_profile有result", "result" in gp)

    # ===================================================================
    # 事件总线
    # ===================================================================
    print("\n📡 Event Bus")
    import asyncio
    from server.event_bus import bus, EventBus

    # 创建新总线(避免与SSE冲突)
    test_bus = EventBus()
    test("新总线队列为空", len(test_bus._queues) == 0)

    q1 = test_bus.subscribe()
    test("订阅创建队列", q1 is not None)
    test("订阅后队列数+1", len(test_bus._queues) == 1)

    q2 = test_bus.subscribe()
    test("多次订阅队列累加", len(test_bus._queues) == 2)

    # 发送事件
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(test_bus.emit_thinking("test thinking"))
        event = loop.run_until_complete(asyncio.wait_for(q1.get(), timeout=1))
        test("事件发送成功", event is not None)
        parsed = json.loads(event)
        test("事件类型为thinking", parsed["type"] == "thinking")
        test("事件包含timestamp", "timestamp" in parsed)
    except (asyncio.TimeoutError, Exception):
        test("事件发送成功", False)
        test("事件类型为thinking", False)
        test("事件包含timestamp", False)
    finally:
        loop.close()

    # 取消订阅
    test_bus.unsubscribe(q1)
    test("取消订阅后队列数-1", len(test_bus._queues) == 1)
    test_bus.unsubscribe(q2)
    test("全部取消后队列为空", len(test_bus._queues) == 0)

    # ===================================================================
    # Heartbeat API
    # ===================================================================
    print("\n💓 Heartbeat API")
    hb = api_get("/api/heartbeat/status")
    test("Heartbeat有current_time", "current_time" in hb)
    test("Heartbeat有meal_period", "meal_period" in hb)
    test("Heartbeat有weather字段", "weather" in hb)
    test("Heartbeat有monitors对象", "monitors" in hb)
    test("Heartbeat monitors有meal/queue/weather", all(
        k in hb["monitors"] for k in ["meal", "queue", "weather"]
    ))

    # ===================================================================
    # Session Reset API
    # ===================================================================
    print("\n🔄 Session Reset API")
    # First create a session
    api_post("/api/chat", {"message": "你好", "session_id": "reset_test"})
    reset = api_post("/api/reset", {"session_id": "reset_test"})
    test("Reset API返回ok", reset.get("ok") is True)

    # ===================================================================
    # 数据来源标签验证 (反幻觉)
    # ===================================================================
    print("\n🏷️ Source Label Verification")
    # 验证所有API返回数据带来源标签
    w_resp = api_get("/api/weather")
    test("Weather API有source_label", "source_label" in w_resp)

    r_resp = api_get("/api/restaurants?limit=1")
    # Restaurant API返回餐厅列表, source_label由skill脚本添加
    test("Restaurant API返回数据", r_resp.get("total", 0) > 0)

    # 所有API响应格式一致
    info_resp = api_get("/api/info")
    test("Info API格式正确", "name" in info_resp and "version" in info_resp)

    # ===================================================================
    print(f"\n{'=' * 60}")
    print(f"E2E结果: {pass_count} 通过, {fail_count} 失败, 共 {pass_count + fail_count} 项")
    return fail_count == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
