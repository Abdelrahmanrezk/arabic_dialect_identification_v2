"""Reading raw QADI CSV files into checked pandas DataFrames.

The loader only reads. It never writes, moves or changes the raw files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from arabic_dialect_identification_v2.data.config import SourceSettings


class DataLoadingError(Exception):
    """Raised when a raw CSV file is missing, unreadable, or does not match the data contract."""


class QadiCsvLoader:
    """Read one raw QADI CSV file and check it matches the agreed data contract.

    Every value is first read as text, so nothing is guessed or rounded.
    Columns that must be whole numbers are then checked and converted
    explicitly. This matters for tweet IDs: they are too long to survive
    a round trip through decimal (float) numbers.

    Example:
        loader = QadiCsvLoader(config.source)
        train = loader.load(config.source.train_path)
    """

    LABEL_COLUMN: str = "dialect"
    INTEGER_COLUMNS: tuple[str, ...] = ("id", "dialect_l_encoded")
    REQUIRED_TEXT_COLUMNS: tuple[str, ...] = (LABEL_COLUMN,)

    def __init__(self, source: SourceSettings) -> None:
        """Create a loader for files described by ``source``.

        Args:
            source: Validated source settings (encoding and expected columns).

        Raises:
            ValueError: If the settings do not list the columns this loader converts.
        """
        missing = [
            column
            for column in (*self.INTEGER_COLUMNS, *self.REQUIRED_TEXT_COLUMNS)
            if column not in source.expected_columns
        ]
        if missing:
            raise ValueError(f"Source settings must list these columns: {missing}")
        self._source = source

    def load(self, csv_path: Path | str) -> pd.DataFrame:
        """Read a raw CSV file and return a checked DataFrame.

        Args:
            csv_path: Path to the raw CSV file.

        Returns:
            A DataFrame with exactly the expected columns, in the expected order.
            Integer columns are ``int64``; the other columns are text.

        Raises:
            DataLoadingError: If the file is missing, cannot be decoded or parsed,
                has missing or unexpected columns, has no rows, or contains
                invalid integers or empty labels.
        """
        path = Path(csv_path)
        self._check_file_exists(path)
        table = self._read_as_text(path)
        self._check_columns(table, path)
        self._check_not_empty(table, path)
        for column in self.INTEGER_COLUMNS:
            table[column] = self._to_integers(table[column], column, path)
        for column in self.REQUIRED_TEXT_COLUMNS:
            self._check_no_blank_values(table[column], column, path)
        return table[list(self._source.expected_columns)]

    @staticmethod
    def _check_file_exists(path: Path) -> None:
        """Stop early with a clear message if ``path`` is not an existing file."""
        if not path.is_file():
            raise DataLoadingError(f"Raw data file not found: '{path}'")

    def _read_as_text(self, path: Path) -> pd.DataFrame:
        """Read every cell as text, keeping strings such as 'NA' or '' exactly as written."""
        try:
            return pd.read_csv(
                path,
                encoding=self._source.encoding,
                dtype=str,
                keep_default_na=False,
            )
        except UnicodeDecodeError as error:
            raise DataLoadingError(f"Cannot decode '{path}' with encoding '{self._source.encoding}'") from error
        except pd.errors.EmptyDataError as error:
            raise DataLoadingError(f"Raw data file is empty: '{path}'") from error
        except pd.errors.ParserError as error:
            raise DataLoadingError(f"Cannot parse CSV file '{path}': {error}") from error

    def _check_columns(self, table: pd.DataFrame, path: Path) -> None:
        """Require exactly the expected columns: none missing, none extra."""
        expected = list(self._source.expected_columns)
        actual = list(table.columns)
        missing = [column for column in expected if column not in actual]
        unexpected = [column for column in actual if column not in expected]
        if missing or unexpected:
            raise DataLoadingError(
                f"Columns in '{path}' do not match the data contract. Missing: {missing}. Unexpected: {unexpected}."
            )

    @staticmethod
    def _check_not_empty(table: pd.DataFrame, path: Path) -> None:
        """Reject a file that has a header but no data rows."""
        if table.empty:
            raise DataLoadingError(f"Raw data file has no rows: '{path}'")

    @staticmethod
    def _to_integers(values: pd.Series, column: str, path: Path) -> pd.Series:
        """Convert text digits to int64, refusing anything that is not a whole number.

        Checking the text first (instead of letting pandas guess) guarantees
        long tweet IDs are converted exactly, never via decimal numbers.
        """
        stripped = values.str.strip()
        is_whole_number = stripped.str.fullmatch(r"-?\d+")
        invalid_count = int((~is_whole_number).sum())
        if invalid_count:
            raise DataLoadingError(
                f"Column '{column}' in '{path}' has {invalid_count} value(s) that are not whole numbers"
            )
        try:
            return stripped.astype("int64")
        except OverflowError as error:
            raise DataLoadingError(f"Column '{column}' in '{path}' has a number too large for int64") from error

    @staticmethod
    def _check_no_blank_values(values: pd.Series, column: str, path: Path) -> None:
        """Reject blank labels; every row must say which dialect it is."""
        blank_count = int((values.str.strip() == "").sum())
        if blank_count:
            raise DataLoadingError(f"Column '{column}' in '{path}' has {blank_count} blank value(s)")
