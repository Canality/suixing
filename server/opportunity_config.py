"""机遇事件子分类 + 用户开关配置。

6个子类别，各自独立开关。状态持久化在内存中（Demo环境）。
"""

# 子分类定义
CATEGORIES = {
    "ticket_show":       {"label": "演出门票", "icon": "🎫", "default": True},
    "ticket_movie":      {"label": "电影票",   "icon": "🎬", "default": True},
    "ticket_exhibition": {"label": "展览门票", "icon": "🖼", "default": True},
    "restaurant_table":  {"label": "餐厅空桌", "icon": "🍲", "default": True},
    "discount":          {"label": "特价优惠", "icon": "💰", "default": False},
    "flash_event":       {"label": "限时活动", "icon": "⚡", "default": False},
}

# 事件类型 → 子分类映射
EVENT_TO_SUBCAT: dict[str, str] = {
    # 演出
    "life_ticket_released_vip": "ticket_show",
    "life_flash_discount":      "ticket_show",  # 密室折扣也是娱乐票
    # 电影
    "ticket_released":          "ticket_movie",
    # 展览
    "ticket_available":         "ticket_exhibition",
    # 餐厅
    "life_flash_table":         "restaurant_table",
    "table_opened":             "restaurant_table",
    "restaurant_reopened":      "restaurant_table",
    # 优惠
    "daily_special":            "discount",
    "life_coupon_expiring":     "discount",
    "life_member_expiring":     "discount",
    # 限时活动
    "life_last_chance":         "flash_event",
    "life_social_group_ride":   "flash_event",
}

# 开关状态（启动时按默认值初始化）
_toggles: dict[str, bool] = {k: v["default"] for k, v in CATEGORIES.items()}


def is_enabled(event_type: str) -> bool:
    """检查某事件类型的子分类开关是否打开。"""
    subcat = EVENT_TO_SUBCAT.get(event_type)
    if subcat is None:
        return True  # 未映射的事件默认放行
    return _toggles.get(subcat, True)


def get_config() -> dict:
    """返回完整配置（供API使用）。"""
    return {
        "categories": {k: {**v, "enabled": _toggles[k]} for k, v in CATEGORIES.items()},
    }


def toggle(subcat: str, enabled: bool) -> bool:
    """切换子分类开关。返回是否成功。"""
    if subcat not in _toggles:
        return False
    _toggles[subcat] = enabled
    return True
