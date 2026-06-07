"""MemoryManager 测试 — 用户画像读写、Layer2摘要、Layer3查询"""

import io
import sys

# Fix Unicode output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
from server.memory import memory, MemoryManager

passed = 0
failed = 0


def test(name: str, condition: bool):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


print("=" * 60)
print("Memory Manager Tests")
print("=" * 60)

# ── Profile 读写 ──────────────────────────────────────────────

print("\n[Profile Read/Write]")

profile = memory.load_profile()
test("load_profile 返回 dict", isinstance(profile, dict))
test("包含 food 域", "food" in profile)
test("包含 residence 域", "residence" in profile)
test("包含 transport 域", "transport" in profile)
test("包含 weather 域", "weather" in profile)
test("包含 entertainment 域", "entertainment" in profile)
test("cuisines_liked 包含川菜", "川菜" in profile.get("food", {}).get("cuisines_liked", ""))

# ── remember 追加型 ───────────────────────────────────────────

print("\n[remember - append]")

old_cuisines = profile.get("food", {}).get("cuisines_liked", "")
result = memory.remember("food", "cuisines_liked", "粤菜", "confirmed")
test("remember 返回 ok", result.get("ok") is True)
test("追加后包含新值", "粤菜" in result.get("value", ""))

# ── remember 覆盖型 ───────────────────────────────────────────

print("\n[remember - overwrite]")

result = memory.remember("basic", "name", "测试用户", "confirmed")
test("覆盖型返回 ok", result.get("ok") is True)
test("覆盖型值更新", result.get("value") == "测试用户")

# 恢复
memory.remember("basic", "name", "小明", "confirmed")

# ── Layer 2: get_summary ──────────────────────────────────────

print("\n[Layer 2: get_summary]")

summary = memory.get_summary()
test("summary 包含用户名", "小明" in summary)
test("summary 包含位置", "望京" in summary or "SOHO" in summary)
test("summary 包含口味", "川菜" in summary)
test("summary 包含预算", "¥" in summary)

# ── Layer 3: get_detail ──────────────────────────────────────

print("\n[Layer 3: get_detail]")

detail = memory.get_detail("上次吃的餐厅")
test("get_detail 返回字符串", isinstance(detail, str))
test("get_detail 非空", len(detail) > 0)

detail2 = memory.get_detail("wishlist")
test("wishlist 查询非空", len(detail2) > 0)

detail3 = memory.get_detail("预算")
test("预算查询包含¥", "¥" in detail3)

# ── 缓存 TTL ──────────────────────────────────────────────────

print("\n[Cache TTL]")

m2 = MemoryManager()
p1 = m2.load_profile()
p2 = m2.load_profile()
test("缓存命中 (同一实例返回相同对象)", p1 is p2)

# ── 日志记录 ──────────────────────────────────────────────────

print("\n[Logging]")

import os
from server.config import WORKSPACE_DIR
memory.log_interaction("测试: 用户询问火锅推荐 → Agent推荐海底捞", [])
log_dir = os.path.join(WORKSPACE_DIR, "memory")
test("memory 目录存在", os.path.exists(log_dir))

# ── save_profile ──────────────────────────────────────────────

print("\n[save_profile]")

memory.remember("food", "cuisines_liked", "川菜, 湘菜, 北京菜, 日料", "confirmed")
profile2 = memory.load_profile()
test("save后load数据一致", "川菜" in profile2.get("food", {}).get("cuisines_liked", ""))

# Clean up test cuisine addition
memory.remember("food", "cuisines_liked", "川菜, 湘菜, 北京菜, 日料", "confirmed")

# ── Results ───────────────────────────────────────────────────

print("\n" + "=" * 60)
print(f"Memory Results: {passed} passed, {failed} failed, {passed + failed} total")
if failed:
    exit(1)
