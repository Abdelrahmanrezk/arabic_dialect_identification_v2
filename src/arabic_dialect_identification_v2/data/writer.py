"""Saving the prepared tables and the preparation report to disk.

All three files are written together: either every file is saved, or none
of them is changed. This avoids a mix of old and new outputs after a failure.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from arabic_dialect_identification_v2.data.config import OutputSettings
from arabic_dialect_identification_v2.data.record_filter import FilterResult


class DatasetWritingError(Exception):
    """Raised when the outputs cannot be written, or would overwrite files without permission."""


@dataclass(frozen=True)
class WrittenFiles:
    """Where each output file was saved."""

    train_path: Path
    evaluate_path: Path
    report_path: Path


class ParquetDatasetWriter:
    """Write the kept train and evaluate tables as Parquet, and the report as JSON.

    Safety rules:
        * Existing outputs are never overwritten unless ``overwrite=True``.
          The check happens before anything is written.
        * Each file is first written under a temporary name and only renamed
          into place once all three have been written successfully.

    Example:
        writer = ParquetDatasetWriter(config.output)
        written = writer.write(result, provenance={"config": "config/data_preprocessing.yaml"})
    """

    TEMPORARY_SUFFIX: str = ".partial"

    def __init__(self, output: OutputSettings, overwrite: bool = False) -> None:
        """Create a writer.

        Args:
            output: Where the files go and what they are called.
            overwrite: Allow replacing outputs that already exist.
        """
        self._output = output
        self._overwrite = overwrite

    def write(self, result: FilterResult, provenance: Mapping[str, object] | None = None) -> WrittenFiles:
        """Save both tables and the report.

        Args:
            result: The filtered tables and their report (from ``RecordFilter``).
            provenance: Extra facts stored in the report for reproducibility,
                such as the settings used. Must be JSON-compatible.

        Returns:
            The paths of the three saved files.

        Raises:
            DatasetWritingError: If outputs already exist and overwriting is not
                allowed, or if any file cannot be written. On failure, no
                existing output is changed and no temporary file is left behind.
        """
        targets = WrittenFiles(
            train_path=self._output.train_path,
            evaluate_path=self._output.evaluate_path,
            report_path=self._output.report_path,
        )
        self._refuse_to_overwrite(targets)
        self._create_output_directory()

        report_document = self._build_report_document(result, provenance)
        writers: list[tuple[Path, Callable[[Path], None]]] = [
            (targets.train_path, lambda path: self._write_parquet(result.train, path)),
            (targets.evaluate_path, lambda path: self._write_parquet(result.evaluate, path)),
            (targets.report_path, lambda path: self._write_json(report_document, path)),
        ]
        staged = self._stage_all(writers)
        self._move_into_place(staged)
        return targets

    def _refuse_to_overwrite(self, targets: WrittenFiles) -> None:
        """Stop before writing anything if outputs exist and overwriting is not allowed."""
        if self._overwrite:
            return
        existing = [
            str(path) for path in (targets.train_path, targets.evaluate_path, targets.report_path) if path.exists()
        ]
        if existing:
            raise DatasetWritingError(
                f"Output file(s) already exist: {existing}. Delete them, or allow overwriting, to write new outputs."
            )

    def _create_output_directory(self) -> None:
        """Create the output folder (and any missing parents), reporting problems clearly."""
        try:
            self._output.directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise DatasetWritingError(f"Cannot create output folder '{self._output.directory}': {error}") from error

    @staticmethod
    def _build_report_document(result: FilterResult, provenance: Mapping[str, object] | None) -> dict[str, object]:
        """Combine the filter counts and the provenance into one JSON-ready dictionary."""
        return {"counts": result.report.to_dict(), "provenance": dict(provenance or {})}

    def _stage_all(self, writers: list[tuple[Path, Callable[[Path], None]]]) -> list[tuple[Path, Path]]:
        """Write every file under a temporary name. On any failure, remove all temporary files."""
        staged: list[tuple[Path, Path]] = []
        try:
            for target, write_to in writers:
                temporary = self._temporary_path(target)
                staged.append((temporary, target))
                write_to(temporary)
        except Exception as error:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            raise DatasetWritingError(f"Could not write outputs to '{self._output.directory}': {error}") from error
        return staged

    @staticmethod
    def _move_into_place(staged: list[tuple[Path, Path]]) -> None:
        """Rename each temporary file to its final name (replacing any old file)."""
        for temporary, target in staged:
            os.replace(temporary, target)

    def _temporary_path(self, target: Path) -> Path:
        """Return the temporary name used while ``target`` is being written."""
        return target.with_name(target.name + self.TEMPORARY_SUFFIX)

    @staticmethod
    def _write_parquet(table: pd.DataFrame, path: Path) -> None:
        """Save a table as Parquet without the pandas row index."""
        table.to_parquet(path, index=False, engine="pyarrow")

    @staticmethod
    def _write_json(document: Mapping[str, object], path: Path) -> None:
        """Save a dictionary as readable UTF-8 JSON (Arabic kept as Arabic letters)."""
        with path.open("w", encoding="utf-8") as report_file:
            json.dump(document, report_file, ensure_ascii=False, indent=2)
            report_file.write("\n")
