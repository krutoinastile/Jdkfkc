"""History screen helpers."""

from __future__ import annotations

HISTORY_FILTERS: dict[str, str] = {
    "all": "Все",
    "win": "✅ Win",
    "loss": "❌ Loss",
    "open": "🔄 Open",
}

HISTORY_PERIODS: dict[int, str] = {
    0: "Всё",
    7: "7д",
    30: "30д",
    90: "90д",
}


def parse_history_callback(data: str) -> tuple[str, int, int]:
    """Parse hist:{filter}:{days}:{page}"""
    parts = data.split(":")
    if len(parts) >= 4 and parts[0] == "hist":
        filt = parts[1] if parts[1] in HISTORY_FILTERS else "all"
        days = int(parts[2]) if parts[2].isdigit() else 0
        page = int(parts[3]) if parts[3].isdigit() else 0
        return filt, days, page
    return "all", 0, 0


def history_callback(filter_name: str, days: int, page: int) -> str:
    return f"hist:{filter_name}:{days}:{page}"
