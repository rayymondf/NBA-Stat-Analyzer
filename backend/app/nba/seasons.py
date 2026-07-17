"""Season string helpers. NBA seasons are labeled like "2025-26"."""
from datetime import date


def current_season(today: date | None = None) -> str:
    today = today or date.today()
    # New season starts in October; before that we're still in the prior season.
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def previous_season(season: str) -> str:
    start = int(season[:4]) - 1
    return f"{start}-{str(start + 1)[-2:]}"


def season_start_year(season: str) -> int:
    return int(season[:4])


def is_current_season(season: str) -> bool:
    return season == current_season()


DEFAULT_SEASONS = [current_season(), previous_season(current_season())]
