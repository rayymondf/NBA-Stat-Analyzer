"""Reusable public API parameter contracts."""
from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from fastapi import Path, Query
from pydantic import AfterValidator, BeforeValidator


class SeasonType(StrEnum):
    PRESEASON = "Pre Season"
    REGULAR = "Regular Season"
    PLAYOFFS = "Playoffs"


class Location(StrEnum):
    HOME = "home"
    AWAY = "away"


class Outcome(StrEnum):
    WIN = "W"
    LOSS = "L"


def _valid_season(value: str) -> str:
    start, end = value.split("-")
    if (int(start) + 1) % 100 != int(end):
        raise ValueError("season must roll forward by one year (for example 2025-26)")
    # NBA endpoints will often return an empty result for a future season.  Do
    # not let public requests turn that transient empty response into an
    # effectively permanent cache entry.
    current_start = date.today().year if date.today().month >= 10 else date.today().year - 1
    if int(start) > current_start:
        raise ValueError("season cannot be later than the current NBA season")
    return value


Season = Annotated[
    str,
    Query(pattern=r"^\d{4}-\d{2}$", examples=["2025-26"]),
    AfterValidator(_valid_season),
]
SearchQuery = Annotated[
    str,
    BeforeValidator(lambda value: str(value).strip()),
    Query(min_length=2, max_length=80),
]
PlayerId = Annotated[int, Path(gt=0)]
GameId = Annotated[str, Path(pattern=r"^\d{10}$")]
TeamAbbreviation = Annotated[
    str,
    Query(pattern=r"^[A-Za-z]{3}$"),
    AfterValidator(str.upper),
]
PositiveLimit = Annotated[int, Query(ge=1, le=100)]
OptionalDate = date | None
