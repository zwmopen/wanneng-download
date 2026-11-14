"""Adaptive, bounded retry timing for the ordered public-media downloader."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import random
import re


_PERMANENT_MARKERS = (
    "404",
    "not found",
    "deleted",
    "private",
    "login required",
    "captcha",
    "verification required",
    "unsupported",
    "需要登录",
    "跳转登录",
    "验证码",
    "已删除",
    "已失效",
    "主页链接",
    "暂不支持",
    "无法匿名解析",
)
_THROTTLE_MARKERS = (
    "429",
    "too many requests",
    "rate limit",
    "rate-limit",
    "retry-after",
    "retry_after",
    "频率过高",
    "请求过于频繁",
    "访问频繁",
    "限流",
    "风控",
    "服务繁忙",
)
_NETWORK_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "network is unreachable",
    "name resolution",
    "dns",
    "502",
    "503",
    "504",
    "网络中断",
    "连接失败",
    "连接超时",
    "网络波动",
)


def classify_failure(error):
    """Return a conservative failure class without guessing at access status."""
    message = str(error or "").lower()
    if any(marker in message for marker in _PERMANENT_MARKERS):
        return "permanent"
    if any(marker in message for marker in _THROTTLE_MARKERS):
        return "throttle"
    if any(marker in message for marker in _NETWORK_MARKERS):
        return "network"
    return "unknown"


def _retry_after_seconds(error):
    message = str(error or "")
    match = re.search(r"(?im)^\s*retry[-_ ]after\s*[:=]\s*(.+?)\s*$", message)
    if not match:
        return None
    value = match.group(1).strip().strip("\"'")
    if value.isdigit():
        return float(value)
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


class AdaptiveRetryPolicy:
    """One bounded retry for transient failures, with a longer 429 cooldown."""

    max_retries = 1
    max_retry_after = 900.0

    @staticmethod
    def should_retry(error, retries_done=0):
        return (
            retries_done < AdaptiveRetryPolicy.max_retries
            and classify_failure(error) in {"throttle", "network"}
        )

    @staticmethod
    def retry_delay(
        error,
        retry_number=1,
        rng=random.uniform,
        throttle_base=30.0,
        network_base=8.0,
        unknown_base=30.0,
    ):
        retry_after = _retry_after_seconds(error)
        if retry_after is not None:
            return min(retry_after, AdaptiveRetryPolicy.max_retry_after)

        kind = classify_failure(error)
        if kind == "throttle":
            low = min(throttle_base * (2 ** max(0, retry_number - 1)), 600.0)
            high = min(low * 1.35, AdaptiveRetryPolicy.max_retry_after)
        elif kind == "network":
            low = min(network_base * (2 ** max(0, retry_number - 1)), 180.0)
            high = min(low * 1.5, 300.0)
        else:
            low = min(unknown_base * (2 ** max(0, retry_number - 1)), 300.0)
            high = min(low * 1.5, 450.0)
        return rng(low, high)

    @staticmethod
    def next_item_delay(success, error="", rng=random.uniform):
        if success:
            return rng(8.0, 15.0)
        kind = classify_failure(error)
        if kind == "throttle":
            return rng(30.0, 60.0)
        if kind == "network":
            return rng(8.0, 18.0)
        if kind == "permanent":
            return rng(2.0, 5.0)
        return rng(5.0, 10.0)
