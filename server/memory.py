"""用户记忆管理 — 持久化用户画像读写 + Layer 2 摘要生成 + Layer 3 按需查询。

三层架构:
  Layer 1: 核心身份 + 行为规则 (由 prompts.py 管理)
  Layer 2: 用户画像一行摘要 (MemoryManager.get_summary, 30分钟TTL)
  Layer 3: 按需查询详情 (MemoryManager.get_detail, LLM 调 get_user_profile 触发)
"""

import json
import os
import re
import time
from datetime import datetime
from server.config import WORKSPACE_DIR

USER_PROFILE_PATH = os.path.join(WORKSPACE_DIR, "USER.md")
MEMORY_LOG_DIR = os.path.join(WORKSPACE_DIR, "memory")

# 哪些字段是追加型 (新值合并到原值，不覆盖)
APPEND_FIELDS = {
    "cuisines_liked", "cuisines_disliked", "allergies", "recent_visits",
    "sports", "movies", "activities", "nearby_districts",
    "frequent_apps", "wishlist",
}


class MemoryManager:
    """管理用户画像的持久化读写 + 摘要生成。"""

    def __init__(self):
        self._profile_cache: dict | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = 60  # profile 缓存60秒

    # ── Profile 读写 ────────────────────────────────────────────

    def load_profile(self) -> dict:
        """解析 USER.md 为结构化 dict，带 TTL 缓存。"""
        now = time.time()
        if self._profile_cache is not None and (now - self._cache_time) < self._cache_ttl:
            return self._profile_cache

        profile = {}
        if not os.path.exists(USER_PROFILE_PATH):
            return profile

        current_section = "_header"
        with open(USER_PROFILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip()
                # Section header
                if line.startswith("## "):
                    section_name = line[3:].strip()
                    # Map Chinese section names to keys
                    section_map = {
                        "基本": "basic", "食": "food", "衣": "weather",
                        "住": "residence", "行": "transport", "娱": "entertainment",
                        "近期状态": "status",
                    }
                    current_section = section_map.get(section_name, section_name)
                    if current_section not in profile:
                        profile[current_section] = {}
                    continue
                # Key-value line
                m = re.match(r"^- (\w+):\s*(.*)", line)
                if m:
                    key = m.group(1)
                    value = m.group(2).strip()
                    if current_section == "_header":
                        continue
                    if current_section not in profile:
                        profile[current_section] = {}
                    profile[current_section][key] = value

        self._profile_cache = profile
        self._cache_time = now
        return profile

    def save_profile(self, profile: dict):
        """写回 USER.md，保留 markdown 格式。"""
        section_meta = [
            ("基本", "basic", ["name", "location", "timezone"]),
            ("食", "food", ["cuisines_liked", "cuisines_disliked", "allergies",
             "spice_level", "budget_lunch", "budget_dinner", "budget_weekend",
             "dining_habit", "frequent_apps", "recent_visits"]),
            ("衣", "weather", ["temp_tolerance", "rain_behavior", "outdoor_weather"]),
            ("住", "residence", ["home", "work", "nearby_districts"]),
            ("行", "transport", ["commute", "mode_preference", "commute_budget_ride", "departure"]),
            ("娱", "entertainment", ["sports", "movies", "activities", "social", "wishlist"]),
            ("近期状态", "status", ["work_busy", "last_updated"]),
        ]

        lines = ["# USER · 用户画像（动态更新 — LLM 通过 remember 工具读写）", ""]
        for title, key, fields in section_meta:
            lines.append(f"## {title}")
            section = profile.get(key, {})
            for field_name in fields:
                value = section.get(field_name, "")
                lines.append(f"- {field_name}: {value}")
            lines.append("")

        # Update cache
        self._profile_cache = profile
        self._cache_time = time.time()

        # Ensure workspace directory exists
        os.makedirs(os.path.dirname(USER_PROFILE_PATH), exist_ok=True)
        with open(USER_PROFILE_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── 记忆更新 ────────────────────────────────────────────────

    def remember(self, category: str, key: str, value: str, confidence: str = "confirmed") -> dict:
        """更新用户画像中的某个字段。返回更新结果。

        category: basic | food | weather | residence | transport | entertainment | status
        """
        profile = self.load_profile()
        section = profile.setdefault(category, {})

        old_value = section.get(key, "")

        if key in APPEND_FIELDS and old_value:
            # 追加型: 合并新值到原值
            existing = {v.strip() for v in old_value.split(",") if v.strip()}
            new_items = {v.strip() for v in value.split(",") if v.strip()}
            merged = existing | new_items
            section[key] = ", ".join(sorted(merged))
        else:
            # 覆盖型
            section[key] = value

        # Update last_updated timestamp
        if "status" not in profile:
            profile["status"] = {}
        profile["status"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        self.save_profile(profile)
        return {
            "ok": True,
            "category": category,
            "key": key,
            "value": section[key],
            "previous": old_value,
            "confidence": confidence,
        }

    # ── Layer 2: 摘要生成 ────────────────────────────────────────

    def get_summary(self) -> str:
        """生成 Layer 2 摘要 — 一行约150 tokens的精简画像。"""
        p = self.load_profile()

        parts = []
        # 基本
        name = p.get("basic", {}).get("name", "用户")
        location = p.get("basic", {}).get("location", "北京")
        parts.append(f"用户: {name}")

        # 住
        residence = p.get("residence", {})
        home = residence.get("home", "")
        work = residence.get("work", "")
        if home and work:
            parts.append(f"常驻{home.split('(')[0] if '(' in home else home}/工作{work.split('(')[0] if '(' in work else work}")
        elif home:
            parts.append(f"常驻{home.split('(')[0] if '(' in home else home}")

        # 食
        food = p.get("food", {})
        liked = food.get("cuisines_liked", "")
        disliked = food.get("cuisines_disliked", "")
        allergies = food.get("allergies", "")
        spice = food.get("spice_level", "")
        parts_food = []
        if liked:
            parts_food.append(f"喜{liked}")
        if disliked:
            parts_food.append(f"忌{disliked}")
        if allergies and allergies != "无":
            parts_food.append(f"过敏{allergies}")
        if spice:
            parts_food.append(f"辣度{spice}")
        if parts_food:
            parts.append("/".join(parts_food))

        # 预算
        bl = food.get("budget_lunch", "")
        bd = food.get("budget_dinner", "")
        bw = food.get("budget_weekend", "")
        budget_parts = []
        if bl:
            budget_parts.append(f"午¥{bl}")
        if bd:
            budget_parts.append(f"晚¥{bd}")
        if bw:
            budget_parts.append(f"末¥{bw}")
        if budget_parts:
            parts.append("/".join(budget_parts))

        # 行
        transport = p.get("transport", {})
        mode = transport.get("mode_preference", "")
        commute = transport.get("commute", "")
        if commute or mode:
            t = f"通勤{commute}" if commute else ""
            if mode:
                t += f"({mode})"
            parts.append(t.strip())

        # 娱
        ent = p.get("entertainment", {})
        sports = ent.get("sports", "")
        movies = ent.get("movies", "")
        acts = ent.get("activities", "")
        ent_parts = []
        if sports:
            ent_parts.append(sports)
        if movies:
            ent_parts.append(f"电影{movies}")
        if ent_parts:
            parts.append("+".join(ent_parts))

        # 天气/衣
        weather = p.get("weather", {})
        temp = weather.get("temp_tolerance", "")
        rain = weather.get("rain_behavior", "")
        if temp:
            parts.append(temp)
        if rain:
            parts.append(rain)

        return " | ".join(parts)

    # ── Layer 3: 按需查询 ────────────────────────────────────────

    def get_detail(self, query: str) -> str:
        """按需查询用户画像详情。LLM 调 get_user_profile 时触发。"""
        p = self.load_profile()
        query_lower = query.lower()

        results = []

        # 关键词匹配
        keywords_map = {
            "上次": self._fmt_section(p, "food", "recent_visits"),
            "餐厅": self._fmt_section(p, "food", "recent_visits"),
            "想吃": self._fmt_section(p, "entertainment", "wishlist"),
            "wishlist": self._fmt_section(p, "entertainment", "wishlist"),
            "预算": f"午餐¥{p.get('food',{}).get('budget_lunch','')} 晚餐¥{p.get('food',{}).get('budget_dinner','')} 周末¥{p.get('food',{}).get('budget_weekend','')}",
            "忌口": self._fmt_section(p, "food", "cuisines_disliked"),
            "过敏": self._fmt_section(p, "food", "allergies"),
            "通勤": self._fmt_section(p, "transport", None),
            "出行": self._fmt_section(p, "transport", None),
            "兴趣": self._fmt_section(p, "entertainment", None),
            "运动": self._fmt_section(p, "entertainment", "sports"),
            "天气偏好": self._fmt_section(p, "weather", None),
        }

        for keyword, result in keywords_map.items():
            if keyword in query_lower and result:
                results.append(result)

        if not results:
            # 返回完整画像作为兜底
            return self.get_summary()

        return " | ".join(results)

    def _fmt_section(self, profile: dict, section: str, field: str | None = None) -> str:
        """格式化 profile 的某个 section 为可读字符串。"""
        s = profile.get(section, {})
        if not s:
            return ""
        if field:
            return s.get(field, "")
        # Format all fields in section
        return ", ".join(f"{k}: {v}" for k, v in s.items() if v)

    # ── 每日日志 ────────────────────────────────────────────────

    def log_interaction(self, summary: str, updates: list[dict]):
        """记录每日会话日志到 memory/YYYY-MM-DD.md。"""
        os.makedirs(MEMORY_LOG_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(MEMORY_LOG_DIR, f"{today}.md")

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n## {timestamp}\n{summary}\n"
        if updates:
            entry += "\n### 记忆更新\n"
            for u in updates:
                entry += f"- {u.get('category','')}/{u.get('key','')}: {u.get('value','')} ({u.get('confidence','')})\n"

        # Append or create
        if os.path.exists(log_path):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        else:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"# {today} 会话日志\n{entry}")


# 全局单例
memory = MemoryManager()
