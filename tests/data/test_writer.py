"""Tests for ParquetDatasetWriter. Writes only small, made-up tables to a temporary folder."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from arabic_dialect_identification_v2.data.config import OutputSettings
from arabic_dialect_identification_v2.data.record_filter import FilterReport, FilterResult, SplitFilterCounts
from arabic_dialect_identification_v2.data.writer import DatasetWritingError, ParquetDatasetWriter

LONG_TWEET_ID = 1119979622408556416


def _output(directory: Path) -> OutputSettings:
    return OutputSettings(
        directory=directory,
        train_file_name="train.parquet",
        evaluate_file_name="evaluate.parquet",
        report_file_name="preparation_report.json",
    )


def _counts(rows: int) -> SplitFilterCounts:
    return SplitFilterCounts(
        input_rows=rows,
        empty_dropped=0,
        duplicates_dropped=0,
        conflicting_label_texts=0,
        overlap_dropped=0,
        output_rows=rows,
        rows_per_dialect={"SA": rows},
    )


def _result() -> FilterResult:
    train = pd.DataFrame(
        {"id": [LONG_TWEET_ID, 2], "dialect": ["SA", "SA"], "dialect_l_encoded": [13, 13], "text": ["هلا", "والله"]}
    )
    evaluate = pd.DataFrame({"id": [9], "dialect": ["SA"], "dialect_l_encoded": [13], "text": ["كيفك"]})
    return FilterResult(train=train, evaluate=evaluate, report=FilterReport(train=_counts(2), evaluate=_counts(1)))


def _all_files(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_writes_three_files(tmp_path: Path) -> None:
    written = ParquetDatasetWriter(_output(tmp_path)).write(_result())
    assert written.train_path == tmp_path / "train.parquet"
    assert _all_files(tmp_path) == ["evaluate.parquet", "preparation_report.json", "train.parquet"]


def test_parquet_files_round_trip_exactly(tmp_path: Path) -> None:
    result = _result()
    written = ParquetDatasetWriter(_output(tmp_path)).write(result)
    train_back = pd.read_parquet(written.train_path)
    pd.testing.assert_frame_equal(train_back, result.train, check_dtype=False)
    assert train_back.loc[0, "id"] == LONG_TWEET_ID
    assert train_back["id"].dtype == "int64"
    assert train_back["dialect_l_encoded"].dtype == "int64"


def test_row_index_is_not_saved_as_a_column(tmp_path: Path) -> None:
    written = ParquetDatasetWriter(_output(tmp_path)).write(_result())
    assert list(pd.read_parquet(written.train_path).columns) == ["id", "dialect", "dialect_l_encoded", "text"]


def test_report_contains_counts_and_provenance(tmp_path: Path) -> None:
    provenance = {"config": "config/data_preprocessing.yaml", "placeholders": ["حسابشخصي"]}
    written = ParquetDatasetWriter(_output(tmp_path)).write(_result(), provenance=provenance)
    report = json.loads(written.report_path.read_text(encoding="utf-8"))
    assert report["counts"]["train"]["output_rows"] == 2
    assert report["counts"]["evaluate"]["rows_per_dialect"] == {"SA": 1}
    assert report["provenance"] == provenance


def test_report_keeps_arabic_readable(tmp_path: Path) -> None:
    written = ParquetDatasetWriter(_output(tmp_path)).write(_result(), provenance={"word": "حسابشخصي"})
    assert "حسابشخصي" in written.report_path.read_text(encoding="utf-8")


def test_report_without_provenance_has_empty_section(tmp_path: Path) -> None:
    written = ParquetDatasetWriter(_output(tmp_path)).write(_result())
    assert json.loads(written.report_path.read_text(encoding="utf-8"))["provenance"] == {}


def test_missing_output_folder_is_created(tmp_path: Path) -> None:
    nested = tmp_path / "data" / "processed"
    ParquetDatasetWriter(_output(nested)).write(_result())
    assert (nested / "train.parquet").is_file()


def test_existing_outputs_are_not_overwritten_by_default(tmp_path: Path) -> None:
    existing = tmp_path / "train.parquet"
    existing.write_text("old content", encoding="utf-8")
    with pytest.raises(DatasetWritingError, match="already exist"):
        ParquetDatasetWriter(_output(tmp_path)).write(_result())
    assert existing.read_text(encoding="utf-8") == "old content"
    assert _all_files(tmp_path) == ["train.parquet"]


def test_overwrite_true_replaces_existing_outputs(tmp_path: Path) -> None:
    (tmp_path / "train.parquet").write_text("old content", encoding="utf-8")
    written = ParquetDatasetWriter(_output(tmp_path), overwrite=True).write(_result())
    assert len(pd.read_parquet(written.train_path)) == 2


def test_no_temporary_files_are_left_after_success(tmp_path: Path) -> None:
    ParquetDatasetWriter(_output(tmp_path)).write(_result())
    assert not any(name.endswith(".partial") for name in _all_files(tmp_path))


def test_failed_write_leaves_no_new_or_partial_files(tmp_path: Path) -> None:
    unwritable = pd.DataFrame({"mixed": [1, "text"]})  # pyarrow cannot store mixed types in one column
    result = _result()
    bad_result = FilterResult(train=result.train, evaluate=unwritable, report=result.report)

    with pytest.raises(DatasetWritingError, match="Could not write"):
        ParquetDatasetWriter(_output(tmp_path)).write(bad_result)
    assert _all_files(tmp_path) == []


def test_failed_overwrite_keeps_old_outputs_untouched(tmp_path: Path) -> None:
    old_train = tmp_path / "train.parquet"
    old_train.write_text("old content", encoding="utf-8")
    unwritable = pd.DataFrame({"mixed": [1, "text"]})
    result = _result()
    bad_result = FilterResult(train=result.train, evaluate=unwritable, report=result.report)

    with pytest.raises(DatasetWritingError):
        ParquetDatasetWriter(_output(tmp_path), overwrite=True).write(bad_result)
    assert old_train.read_text(encoding="utf-8") == "old content"
    assert _all_files(tmp_path) == ["train.parquet"]


def test_output_folder_that_cannot_be_created_raises_clear_error(tmp_path: Path) -> None:
    blocker = tmp_path / "processed"
    blocker.write_text("this is a file, not a folder", encoding="utf-8")
    with pytest.raises(DatasetWritingError, match="Cannot create output folder"):
        ParquetDatasetWriter(_output(blocker)).write(_result())
