from __future__ import annotations

import math

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from app.services import frames


def test_aggregate_uses_totals_for_percentages_and_rates(game_logs):
    result = frames.aggregate(game_logs)

    assert result["games"] == 3
    assert result["wins"] == 2
    assert result["starts"] == 2
    assert result["shooting"]["FG_PCT"] == round(20 / 47, 4)
    assert result["shooting"]["EFG_PCT"] == round((20 + 0.5 * 7) / 47, 4)
    assert result["per_game"]["PTS"] == round(56 / 3, 2)
    assert result["per_75"]["PTS"] == round(56 * 75 / 180, 2)


def test_aggregate_missing_advanced_metric_is_not_zero_filled(game_logs):
    result = frames.aggregate(game_logs)

    expected = round((120 * 72 + 112 * 60) / (72 + 60), 1)
    assert result["shooting"]["OFF_RATING"] == expected
    assert result["shooting"]["OFF_RATING"] > 100


def test_aggregate_falls_back_to_estimated_possessions(game_logs):
    logs = game_logs.drop(columns=["POSS"])
    result = frames.aggregate(logs)
    expected = 47 + 0.44 * 11 + 6
    assert result["possessions"] == round(expected, 1)
    assert result["per_100"]["PTS"] == round(56 * 100 / expected, 2)


def test_empty_aggregate_is_stable():
    assert frames.aggregate(pd.DataFrame()) == {"games": 0}


def test_filters_compose_before_last_n(game_logs):
    filters = frames.LogFilters(
        season="2025-26", location="home", outcome="W", last_n=1,
        date_from="2025-10-01", date_to="2025-10-31",
    )
    filtered = frames.apply_filters(game_logs, filters)
    assert filtered["GAME_ID"].tolist() == ["0022500003"]


def test_starter_and_opponent_filters(game_logs):
    bench = frames.apply_filters(game_logs, frames.LogFilters(
        season="2025-26", starter=False, opponent="nyk",
    ))
    assert bench["GAME_ID"].tolist() == ["0022500002"]


def test_unknown_starter_data_does_not_drop_every_game(game_logs):
    logs = game_logs.copy()
    logs["STARTED"] = None
    filtered = frames.apply_filters(logs, frames.LogFilters(
        season="2025-26", starter=True,
    ))
    assert len(filtered) == len(logs)


@given(
    numerator=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    denominator=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_safe_division_matches_rounded_ratio(numerator, denominator):
    value = frames._safe_div(numerator, denominator)
    assert value is not None
    assert math.isclose(value, round(numerator / denominator, 4))


def test_safe_division_returns_none_for_zero():
    assert frames._safe_div(5, 0) is None
