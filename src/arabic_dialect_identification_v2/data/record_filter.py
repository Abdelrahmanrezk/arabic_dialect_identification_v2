"""Row-level rules applied after text cleaning: empty rows, duplicates and train/evaluate overlap.

The filter only removes whole rows. It never changes text or labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from arabic_dialect_identification_v2.data.config import RowPolicySettings


@dataclass(frozen=True)
class SplitFilterCounts:
    """What happened to one table (train or evaluate) during filtering.

    Attributes:
        input_rows: Rows received by the filter.
        empty_dropped: Rows dropped because the cleaned text was empty.
        duplicates_dropped: Rows dropped because the same text appeared earlier in the same table.
        conflicting_label_texts: Texts that appeared more than once with different labels.
            These are still de-duplicated; the number is reported so it can be reviewed.
        overlap_dropped: Train rows dropped because their text also appears in evaluate.
            Always 0 for evaluate.
        output_rows: Rows kept.
        rows_per_dialect: Rows kept for each dialect label.
    """

    input_rows: int
    empty_dropped: int
    duplicates_dropped: int
    conflicting_label_texts: int
    overlap_dropped: int
    output_rows: int
    rows_per_dialect: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class FilterReport:
    """Counts for both tables, ready to be saved as JSON."""

    train: SplitFilterCounts
    evaluate: SplitFilterCounts

    def to_dict(self) -> dict[str, dict[str, object]]:
        """Return the report as plain dictionaries (for JSON)."""
        return {"train": asdict(self.train), "evaluate": asdict(self.evaluate)}


@dataclass(frozen=True)
class FilterResult:
    """The kept rows of both tables, plus the report describing what was removed."""

    train: pd.DataFrame
    evaluate: pd.DataFrame
    report: FilterReport


class RecordFilter:
    """Apply the agreed row policy to cleaned train and evaluate tables.

    Order of steps:
        1. Drop rows whose cleaned text is empty (both tables).
        2. Drop repeated texts within each table, keeping the first row (both tables).
        3. Drop train rows whose text also appears in evaluate (train only).

    Each step can be switched off in the ``row_policy`` settings.
    Evaluate is filtered first so that step 3 compares against the final evaluate texts.

    Example:
        record_filter = RecordFilter(config.row_policy, text_column="text", label_column="dialect")
        result = record_filter.apply(cleaned_train, cleaned_evaluate)
    """

    def __init__(self, row_policy: RowPolicySettings, text_column: str, label_column: str) -> None:
        """Create a filter.

        Args:
            row_policy: Which steps are switched on.
            text_column: Column holding the cleaned text.
            label_column: Column holding the dialect label (used for counts only).
        """
        self._row_policy = row_policy
        self._text_column = text_column
        self._label_column = label_column

    def apply(self, train: pd.DataFrame, evaluate: pd.DataFrame) -> FilterResult:
        """Filter both tables and report what was removed.

        The input tables are not changed; new tables are returned.

        Args:
            train: Cleaned training table.
            evaluate: Cleaned evaluation table.

        Returns:
            The kept rows of both tables and a report of every count.

        Raises:
            ValueError: If a table is missing the text or label column.
        """
        self._check_columns(train, "train")
        self._check_columns(evaluate, "evaluate")

        kept_evaluate, evaluate_counts = self._filter_one_table(evaluate, texts_to_exclude=None)
        excluded_texts = set(kept_evaluate[self._text_column]) if self._row_policy.drop_train_evaluate_overlap else None
        kept_train, train_counts = self._filter_one_table(train, texts_to_exclude=excluded_texts)

        return FilterResult(
            train=kept_train,
            evaluate=kept_evaluate,
            report=FilterReport(train=train_counts, evaluate=evaluate_counts),
        )

    def _filter_one_table(
        self, table: pd.DataFrame, texts_to_exclude: set[str] | None
    ) -> tuple[pd.DataFrame, SplitFilterCounts]:
        """Run the enabled steps on one table and count the rows each step removes."""
        input_rows = len(table)

        after_empty = self._drop_empty_texts(table) if self._row_policy.drop_empty_texts else table
        conflicting = self._count_conflicting_label_texts(after_empty)
        after_duplicates = (
            self._drop_duplicate_texts(after_empty) if self._row_policy.drop_duplicate_texts else after_empty
        )
        after_overlap = (
            self._drop_texts(after_duplicates, texts_to_exclude) if texts_to_exclude is not None else after_duplicates
        )
        kept = after_overlap.reset_index(drop=True)

        counts = SplitFilterCounts(
            input_rows=input_rows,
            empty_dropped=input_rows - len(after_empty),
            duplicates_dropped=len(after_empty) - len(after_duplicates),
            conflicting_label_texts=conflicting,
            overlap_dropped=len(after_duplicates) - len(after_overlap),
            output_rows=len(kept),
            rows_per_dialect=self._rows_per_label(kept),
        )
        return kept, counts

    def _drop_empty_texts(self, table: pd.DataFrame) -> pd.DataFrame:
        """Keep only rows whose text has at least one non-space character."""
        has_text = table[self._text_column].str.strip() != ""
        return table[has_text]

    def _drop_duplicate_texts(self, table: pd.DataFrame) -> pd.DataFrame:
        """Keep the first row for each distinct text."""
        return table.drop_duplicates(subset=self._text_column, keep="first")

    def _drop_texts(self, table: pd.DataFrame, texts: set[str]) -> pd.DataFrame:
        """Remove rows whose text is in ``texts``."""
        return table[~table[self._text_column].isin(texts)]

    def _count_conflicting_label_texts(self, table: pd.DataFrame) -> int:
        """Count texts that appear with more than one different label."""
        labels_per_text = table.groupby(self._text_column)[self._label_column].nunique()
        return int((labels_per_text > 1).sum())

    def _rows_per_label(self, table: pd.DataFrame) -> dict[str, int]:
        """Return how many rows each label has, sorted by label."""
        counts = table[self._label_column].value_counts().sort_index()
        return {str(label): int(count) for label, count in counts.items()}

    def _check_columns(self, table: pd.DataFrame, table_name: str) -> None:
        """Stop with a clear message if a needed column is missing."""
        missing = [column for column in (self._text_column, self._label_column) if column not in table.columns]
        if missing:
            raise ValueError(f"The {table_name} table is missing column(s): {missing}")
