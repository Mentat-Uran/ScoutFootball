"""Tests for _clean_json_value — numpy type, NaN, inf, pandas NA/NaT JSON cleaning."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from scoutfootball.api import _clean_json_value


class TestNumpyInteger:
    def test_int64(self) -> None:
        result = _clean_json_value(np.int64(42))
        assert result == 42
        assert isinstance(result, int)

    def test_int32(self) -> None:
        result = _clean_json_value(np.int32(7))
        assert result == 7
        assert isinstance(result, int)

    def test_negative_int64(self) -> None:
        result = _clean_json_value(np.int64(-1))
        assert result == -1
        assert isinstance(result, int)


class TestNumpyFloat:
    def test_float64(self) -> None:
        result = _clean_json_value(np.float64(3.14))
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-10

    def test_float32(self) -> None:
        result = _clean_json_value(np.float32(2.5))
        assert isinstance(result, float)

    def test_float64_nan(self) -> None:
        result = _clean_json_value(np.float64("nan"))
        assert result is None

    def test_float64_inf(self) -> None:
        result = _clean_json_value(np.float64("inf"))
        assert result is None

    def test_float64_neg_inf(self) -> None:
        result = _clean_json_value(np.float64("-inf"))
        assert result is None


class TestNumpyBool:
    def test_bool_true(self) -> None:
        result = _clean_json_value(np.bool_(True))
        assert result is True
        assert isinstance(result, bool)

    def test_bool_false(self) -> None:
        result = _clean_json_value(np.bool_(False))
        assert result is False
        assert isinstance(result, bool)


class TestPythonFloatSpecial:
    def test_nan(self) -> None:
        result = _clean_json_value(float("nan"))
        assert result is None

    def test_inf(self) -> None:
        result = _clean_json_value(float("inf"))
        assert result is None

    def test_neg_inf(self) -> None:
        result = _clean_json_value(-float("inf"))
        assert result is None


class TestPandasNA:
    def test_pd_na(self) -> None:
        result = _clean_json_value(pd.NA)
        assert result is None

    def test_pd_nat(self) -> None:
        result = _clean_json_value(pd.NaT)
        assert result is None


class TestNestedStructures:
    def test_dict_with_numpy_values(self) -> None:
        data = {"a": np.int64(1), "b": np.float64(2.0), "c": np.bool_(True)}
        result = _clean_json_value(data)
        assert result == {"a": 1, "b": 2.0, "c": True}

    def test_list_with_numpy_values(self) -> None:
        data = [np.int64(10), np.float64(3.5), np.bool_(False)]
        result = _clean_json_value(data)
        assert result == [10, 3.5, False]

    def test_nested_dict_list(self) -> None:
        data = {"items": [np.int64(1), {"inner": np.float64("nan")}]}
        result = _clean_json_value(data)
        assert result == {"items": [1, {"inner": None}]}

    def test_deeply_nested(self) -> None:
        data = {"a": {"b": {"c": [np.int64(99)]}}}
        result = _clean_json_value(data)
        assert result == {"a": {"b": {"c": [99]}}}


class TestJsonSerializable:
    """All cleaned results must be json.dumps-serializable."""

    def test_numpy_types_after_cleaning(self) -> None:
        data = {
            "int": np.int64(42),
            "float": np.float64(3.14),
            "bool": np.bool_(True),
            "nan": float("nan"),
            "inf": float("inf"),
            "nested": {"pd_na": pd.NA, "pd_nat": pd.NaT},
        }
        cleaned = _clean_json_value(data)
        serialized = json.dumps(cleaned)
        assert isinstance(serialized, str)
        # Verify key values survived
        parsed = json.loads(serialized)
        assert parsed["int"] == 42
        assert parsed["nan"] is None
        assert parsed["inf"] is None

    def test_list_after_cleaning(self) -> None:
        data = [np.int64(1), np.float64("nan"), np.bool_(False)]
        cleaned = _clean_json_value(data)
        serialized = json.dumps(cleaned)
        parsed = json.loads(serialized)
        assert parsed == [1, None, False]


class TestPassthrough:
    """Values that don't need cleaning should pass through unchanged."""

    def test_string(self) -> None:
        assert _clean_json_value("hello") == "hello"

    def test_int(self) -> None:
        assert _clean_json_value(42) == 42

    def test_float(self) -> None:
        assert _clean_json_value(3.14) == 3.14

    def test_none(self) -> None:
        assert _clean_json_value(None) is None

    def test_bool(self) -> None:
        assert _clean_json_value(True) is True

    def test_empty_dict(self) -> None:
        assert _clean_json_value({}) == {}

    def test_empty_list(self) -> None:
        assert _clean_json_value([]) == []
