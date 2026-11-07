"""Tests for QadiCsvLoader. Uses only small, made-up CSV files written to a temporary folder."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from arabic_dialect_identification_v2.data.config import SourceSettings
from arabic_dialect_identification_v2.data.loader import DataLoadingError, QadiCsvLoader

HEADER = "id,dialect,dialect_l_encoded,text\n"
LONG_TWEET_ID = 1119979622408556416  # longer than a float can hold exactly


def _source(encoding: str = "utf-8-sig") -> SourceSettings:
    return SourceSettings(
        train_path=Path("unused.csv"),
        evaluate_path=Path("unused.csv"),
        encoding=encoding,
        expected_columns=("id", "dialect", "dialect_l_encoded", "text"),
        text_column="text",
    )


def _write_csv(tmp_path: Path, content: str, *, encoding: str = "utf-8-sig") -> Path:
    path = tmp_path / "sample.csv"
    path.write_bytes(content.encode(encoding))
    return path


@pytest.fixture
def loader() -> QadiCsvLoader:
    return QadiCsvLoader(_source())


def test_loads_rows_with_expected_columns_and_types(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + "1,EG,3,مرحبا يا جماعة\n2,SA,13,كيفكم\n")

    table = loader.load(path)

    assert list(table.columns) == ["id", "dialect", "dialect_l_encoded", "text"]
    assert len(table) == 2
    assert table["id"].dtype == "int64"
    assert table["dialect_l_encoded"].dtype == "int64"
    assert table.loc[0, "text"] == "مرحبا يا جماعة"


def test_long_tweet_ids_are_not_rounded(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + f"{LONG_TWEET_ID},SY,15,نص\n")
    assert loader.load(path).loc[0, "id"] == LONG_TWEET_ID


def test_reads_file_without_excel_marker_too(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + "1,EG,3,نص\n", encoding="utf-8")
    assert loader.load(path).columns[0] == "id"


def test_text_that_looks_like_missing_value_is_kept(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + "1,EG,3,NA\n2,EG,3,\n")
    table = loader.load(path)
    assert table.loc[0, "text"] == "NA"
    assert table.loc[1, "text"] == ""


def test_columns_are_returned_in_contract_order(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, "text,id,dialect_l_encoded,dialect\nنص,1,3,EG\n")
    assert list(loader.load(path).columns) == ["id", "dialect", "dialect_l_encoded", "text"]


def test_raw_file_is_not_changed(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + "1,EG,3,نص\n")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    loader.load(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_missing_file_raises_clear_error(tmp_path: Path, loader: QadiCsvLoader) -> None:
    with pytest.raises(DataLoadingError, match="not found"):
        loader.load(tmp_path / "missing.csv")


def test_folder_instead_of_file_raises_clear_error(tmp_path: Path, loader: QadiCsvLoader) -> None:
    with pytest.raises(DataLoadingError, match="not found"):
        loader.load(tmp_path)


def test_completely_empty_file_raises_clear_error(tmp_path: Path, loader: QadiCsvLoader) -> None:
    with pytest.raises(DataLoadingError, match="empty"):
        loader.load(_write_csv(tmp_path, ""))


def test_header_without_rows_raises_clear_error(tmp_path: Path, loader: QadiCsvLoader) -> None:
    with pytest.raises(DataLoadingError, match="no rows"):
        loader.load(_write_csv(tmp_path, HEADER))


def test_missing_column_is_named_in_error(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, "id,dialect,text\n1,EG,نص\n")
    with pytest.raises(DataLoadingError, match="dialect_l_encoded"):
        loader.load(path)


def test_unexpected_column_is_named_in_error(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, "id,dialect,dialect_l_encoded,text,user\n1,EG,3,نص,x\n")
    with pytest.raises(DataLoadingError, match="user"):
        loader.load(path)


@pytest.mark.parametrize("bad_id", ["abc", "1.5", ""])
def test_non_integer_id_is_rejected(tmp_path: Path, loader: QadiCsvLoader, bad_id: str) -> None:
    path = _write_csv(tmp_path, HEADER + f"{bad_id},EG,3,نص\n")
    with pytest.raises(DataLoadingError, match=r"'id'.*not whole numbers"):
        loader.load(path)


def test_non_integer_label_is_rejected(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + "1,EG,three,نص\n")
    with pytest.raises(DataLoadingError, match="dialect_l_encoded"):
        loader.load(path)


def test_blank_dialect_is_rejected(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + "1, ,3,نص\n")
    with pytest.raises(DataLoadingError, match=r"'dialect'.*blank"):
        loader.load(path)


def test_wrong_encoding_raises_clear_error(tmp_path: Path, loader: QadiCsvLoader) -> None:
    path = _write_csv(tmp_path, HEADER + "1,EG,3,مرحبا\n", encoding="cp1256")
    with pytest.raises(DataLoadingError, match="Cannot decode"):
        loader.load(path)


def test_settings_without_required_columns_are_refused() -> None:
    settings = SourceSettings(
        train_path=Path("x.csv"),
        evaluate_path=Path("x.csv"),
        expected_columns=("id", "text"),
        text_column="text",
    )
    with pytest.raises(ValueError, match="dialect_l_encoded"):
        QadiCsvLoader(settings)


def test_returns_a_dataframe(tmp_path: Path, loader: QadiCsvLoader) -> None:
    assert isinstance(loader.load(_write_csv(tmp_path, HEADER + "1,EG,3,نص\n")), pd.DataFrame)
