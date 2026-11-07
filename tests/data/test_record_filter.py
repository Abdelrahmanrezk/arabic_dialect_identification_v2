"""Tests for RecordFilter. Uses only small, made-up tables."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from arabic_dialect_identification_v2.data.config import RowPolicySettings
from arabic_dialect_identification_v2.data.record_filter import RecordFilter


def _policy(empty: bool = True, duplicates: bool = True, overlap: bool = True) -> RowPolicySettings:
    return RowPolicySettings(
        drop_empty_texts=empty,
        drop_duplicate_texts=duplicates,
        drop_train_evaluate_overlap=overlap,
    )


def _table(rows: list[tuple[int, str, int, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["id", "dialect", "dialect_l_encoded", "text"])


def _filter(**policy: bool) -> RecordFilter:
    return RecordFilter(_policy(**policy), text_column="text", label_column="dialect")


@pytest.fixture
def train() -> pd.DataFrame:
    return _table(
        [
            (1, "EG", 3, "ازيك"),
            (2, "EG", 3, ""),  # empty
            (3, "SA", 13, "هلا"),
            (4, "SA", 13, "هلا"),  # duplicate, same label
            (5, "KW", 6, "شلونك"),
            (6, "SA", 13, "شلونك"),  # duplicate, different label
            (7, "LY", 8, "تمام"),  # also in evaluate
            (8, "SY", 15, "   "),  # only spaces
        ]
    )


@pytest.fixture
def evaluate() -> pd.DataFrame:
    return _table(
        [
            (100, "LY", 8, "تمام"),
            (101, "LY", 8, "تمام"),  # duplicate inside evaluate
            (102, "EG", 3, ""),  # empty
            (103, "SY", 15, "كيفك"),
        ]
    )


def test_train_keeps_only_valid_unique_non_overlapping_rows(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter().apply(train, evaluate)
    assert result.train["id"].tolist() == [1, 3, 5]


def test_evaluate_drops_empty_and_duplicates_but_not_for_overlap(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter().apply(train, evaluate)
    assert result.evaluate["id"].tolist() == [100, 103]


def test_report_counts_for_train(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    counts = _filter().apply(train, evaluate).report.train
    assert counts.input_rows == 8
    assert counts.empty_dropped == 2
    assert counts.duplicates_dropped == 2
    assert counts.conflicting_label_texts == 1
    assert counts.overlap_dropped == 1
    assert counts.output_rows == 3
    assert counts.rows_per_dialect == {"EG": 1, "KW": 1, "SA": 1}


def test_report_counts_for_evaluate(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    counts = _filter().apply(train, evaluate).report.evaluate
    assert counts.input_rows == 4
    assert counts.empty_dropped == 1
    assert counts.duplicates_dropped == 1
    assert counts.conflicting_label_texts == 0
    assert counts.overlap_dropped == 0
    assert counts.output_rows == 2
    assert counts.rows_per_dialect == {"LY": 1, "SY": 1}


def test_counts_add_up(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    report = _filter().apply(train, evaluate).report
    for counts in (report.train, report.evaluate):
        dropped = counts.empty_dropped + counts.duplicates_dropped + counts.overlap_dropped
        assert counts.input_rows - dropped == counts.output_rows
        assert sum(counts.rows_per_dialect.values()) == counts.output_rows


def test_no_output_text_is_empty_or_repeated(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter().apply(train, evaluate)
    for table in (result.train, result.evaluate):
        assert (table["text"].str.strip() != "").all()
        assert not table["text"].duplicated().any()


def test_no_train_text_appears_in_evaluate(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter().apply(train, evaluate)
    assert set(result.train["text"]).isdisjoint(set(result.evaluate["text"]))


def test_kept_rows_are_unchanged(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter().apply(train, evaluate)
    original = train.set_index("id")
    for row in result.train.itertuples(index=False):
        assert original.loc[row.id, "text"] == row.text
        assert original.loc[row.id, "dialect"] == row.dialect
        assert original.loc[row.id, "dialect_l_encoded"] == row.dialect_l_encoded


def test_input_tables_are_not_modified(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    train_before, evaluate_before = train.copy(), evaluate.copy()
    _filter().apply(train, evaluate)
    pd.testing.assert_frame_equal(train, train_before)
    pd.testing.assert_frame_equal(evaluate, evaluate_before)


def test_output_index_is_reset(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter().apply(train, evaluate)
    assert result.train.index.tolist() == list(range(len(result.train)))


def test_columns_are_kept_in_the_same_order(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter().apply(train, evaluate)
    assert list(result.train.columns) == list(train.columns)


def test_switching_off_empty_step_keeps_empty_rows(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter(empty=False).apply(train, evaluate)
    assert result.report.train.empty_dropped == 0
    assert result.report.evaluate.empty_dropped == 0
    assert (result.train["text"].str.strip() == "").any()
    assert (result.evaluate["text"].str.strip() == "").any()


def test_switching_off_duplicate_step_keeps_repeats(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter(duplicates=False).apply(train, evaluate)
    assert result.report.train.duplicates_dropped == 0
    assert result.train["text"].tolist().count("هلا") == 2


def test_switching_off_overlap_step_keeps_shared_texts(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    result = _filter(overlap=False).apply(train, evaluate)
    assert result.report.train.overlap_dropped == 0
    assert "تمام" in result.train["text"].tolist()


def test_report_converts_to_json(train: pd.DataFrame, evaluate: pd.DataFrame) -> None:
    report = _filter().apply(train, evaluate).report
    as_json = json.dumps(report.to_dict(), ensure_ascii=False)
    assert json.loads(as_json)["train"]["output_rows"] == 3


def test_missing_text_column_raises_clear_error(evaluate: pd.DataFrame) -> None:
    bad_train = pd.DataFrame({"id": [1], "dialect": ["EG"]})
    with pytest.raises(ValueError, match=r"train.*text"):
        _filter().apply(bad_train, evaluate)


def test_missing_label_column_raises_clear_error(train: pd.DataFrame) -> None:
    bad_evaluate = pd.DataFrame({"id": [1], "text": ["x"]})
    with pytest.raises(ValueError, match=r"evaluate.*dialect"):
        _filter().apply(train, bad_evaluate)


def test_tables_with_nothing_to_drop_pass_through_unchanged() -> None:
    clean_train = _table([(1, "EG", 3, "أ"), (2, "SA", 13, "ب")])
    clean_evaluate = _table([(9, "EG", 3, "ج")])
    result = _filter().apply(clean_train, clean_evaluate)
    pd.testing.assert_frame_equal(result.train, clean_train)
    assert result.report.train.output_rows == 2
