import pandas as pd

from pulse.coerce import coerce_frame, to_numeric_if_clean


def test_converts_when_every_value_parses():
    s = pd.Series(["1", "2.5", None])
    out = to_numeric_if_clean(s)
    assert pd.api.types.is_float_dtype(out)
    assert out.iloc[1] == 2.5 and pd.isna(out.iloc[2])


def test_leaves_column_alone_when_any_value_fails():
    s = pd.Series(["1", "n/a", "3"])
    assert to_numeric_if_clean(s) is s


def test_numeric_passthrough():
    s = pd.Series([1, 2, 3])
    assert to_numeric_if_clean(s) is s


def test_frame_does_not_mutate_input():
    df = pd.DataFrame({"a": ["1", "2"], "b": ["x", "y"]})
    out = coerce_frame(df)
    assert out["a"].tolist() == [1, 2] and out["b"].tolist() == ["x", "y"]
    assert df["a"].tolist() == ["1", "2"]
