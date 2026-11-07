"""The data-preparation pipeline: load → clean → filter → write.

This module only connects the parts. Each part does its own job:
    QadiCsvLoader        reads and checks one raw CSV
    ArabicTextCleaner    cleans one tweet
    RecordFilter         drops empty, duplicate and overlapping rows
    ParquetDatasetWriter saves the tables and the report
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd

from arabic_dialect_identification_v2.data.cleaner import ArabicTextCleaner
from arabic_dialect_identification_v2.data.config import DataPreparationConfig
from arabic_dialect_identification_v2.data.loader import QadiCsvLoader
from arabic_dialect_identification_v2.data.record_filter import FilterReport, RecordFilter
from arabic_dialect_identification_v2.data.writer import ParquetDatasetWriter, WrittenFiles

logger = logging.getLogger(__name__)


class DataPreparationPipeline:
    """Run the whole preparation step in the agreed order.

    The pipeline receives its parts instead of creating them (dependency
    injection), so tests can swap any part. Use :meth:`from_config` to build
    the standard pipeline from the settings file.

    Example:
        config = DataPreparationConfig.from_yaml("config/data_preprocessing.yaml")
        pipeline = DataPreparationPipeline.from_config(config)
        written, report = pipeline.run()
    """

    HASH_CHUNK_BYTES: int = 1024 * 1024

    def __init__(
        self,
        config: DataPreparationConfig,
        loader: QadiCsvLoader,
        cleaner: ArabicTextCleaner,
        record_filter: RecordFilter,
        writer: ParquetDatasetWriter,
    ) -> None:
        """Create a pipeline from ready-made parts.

        Args:
            config: All validated settings (used for input paths and provenance).
            loader: Reads the raw CSV files.
            cleaner: Cleans each tweet.
            record_filter: Drops rows after cleaning.
            writer: Saves the outputs.
        """
        self._config = config
        self._loader = loader
        self._cleaner = cleaner
        self._record_filter = record_filter
        self._writer = writer

    @classmethod
    def from_config(cls, config: DataPreparationConfig, overwrite: bool = False) -> DataPreparationPipeline:
        """Build the standard pipeline, creating each part from its section of the settings.

        Args:
            config: All validated settings.
            overwrite: Allow replacing existing output files.

        Returns:
            A pipeline ready to :meth:`run`.
        """
        return cls(
            config=config,
            loader=QadiCsvLoader(config.source),
            cleaner=ArabicTextCleaner(config.cleaning),
            record_filter=RecordFilter(
                config.row_policy,
                text_column=config.source.text_column,
                label_column=QadiCsvLoader.LABEL_COLUMN,
            ),
            writer=ParquetDatasetWriter(config.output, overwrite=overwrite),
        )

    def run(self) -> tuple[WrittenFiles, FilterReport]:
        """Load, clean, filter and write. Raw files are only read, never changed.

        Returns:
            Where the outputs were saved, and the counts of what was removed.

        Raises:
            DataLoadingError: If a raw file fails the data contract.
            DatasetWritingError: If the outputs cannot be written.
        """
        source = self._config.source

        logger.info("Loading raw files")
        train = self._loader.load(source.train_path)
        evaluate = self._loader.load(source.evaluate_path)

        logger.info("Cleaning text (%s train rows, %s evaluate rows)", len(train), len(evaluate))
        cleaned_train = self._clean_text_column(train)
        cleaned_evaluate = self._clean_text_column(evaluate)

        logger.info("Filtering rows")
        result = self._record_filter.apply(cleaned_train, cleaned_evaluate)

        logger.info("Writing outputs to %s", self._config.output.directory)
        written = self._writer.write(result, provenance=self._build_provenance())
        return written, result.report

    def _clean_text_column(self, table: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of ``table`` whose text column has been cleaned. The input is not changed."""
        text_column = self._config.source.text_column
        return table.assign(**{text_column: table[text_column].map(self._cleaner.clean)})

    def _build_provenance(self) -> dict[str, object]:
        """Collect what is needed to reproduce the outputs: the settings and fingerprints of the inputs."""
        source = self._config.source
        return {
            "settings": self._config.model_dump(mode="json"),
            "inputs": {
                "train": {"path": str(source.train_path), "sha256": self._file_sha256(source.train_path)},
                "evaluate": {"path": str(source.evaluate_path), "sha256": self._file_sha256(source.evaluate_path)},
            },
        }

    @classmethod
    def _file_sha256(cls, path: Path) -> str:
        """Return the SHA-256 fingerprint of a file, reading it in chunks to save memory."""
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(cls.HASH_CHUNK_BYTES), b""):
                digest.update(chunk)
        return digest.hexdigest()
