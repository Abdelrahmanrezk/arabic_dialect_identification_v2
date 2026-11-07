"""Command-line entry point for the data-preparation step.

Run from the repository root:

    uv run python -m arabic_dialect_identification_v2.data.prepare --config config/data_preprocessing.yaml

Add ``--overwrite`` to replace existing outputs.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from arabic_dialect_identification_v2.data.config import ConfigurationError, DataPreparationConfig
from arabic_dialect_identification_v2.data.loader import DataLoadingError
from arabic_dialect_identification_v2.data.pipeline import DataPreparationPipeline
from arabic_dialect_identification_v2.data.record_filter import FilterReport
from arabic_dialect_identification_v2.data.writer import DatasetWritingError

DEFAULT_CONFIG = "config/data_preprocessing.yaml"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the pipeline from the command line.

    Args:
        argv: Command-line arguments (defaults to the real ones).

    Returns:
        0 on success, 1 if the settings, data or outputs had a problem.
    """
    arguments = _parse_arguments(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        config = DataPreparationConfig.from_yaml(arguments.config)
        pipeline = DataPreparationPipeline.from_config(config, overwrite=arguments.overwrite)
        written, report = pipeline.run()
    except (ConfigurationError, DataLoadingError, DatasetWritingError) as error:
        print(f"Data preparation failed: {error}", file=sys.stderr)
        return 1

    _print_summary(report)
    print(f"Saved: {written.train_path}, {written.evaluate_path}, {written.report_path}")
    return 0


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the QADI corpus: clean text and drop invalid rows.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"Settings file (default: {DEFAULT_CONFIG})")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output files")
    return parser.parse_args(argv)


def _print_summary(report: FilterReport) -> None:
    for name, counts in (("train", report.train), ("evaluate", report.evaluate)):
        print(
            f"{name}: {counts.input_rows:,} in → {counts.output_rows:,} out "
            f"(empty {counts.empty_dropped:,}, duplicates {counts.duplicates_dropped:,}, "
            f"overlap {counts.overlap_dropped:,}, conflicting-label texts {counts.conflicting_label_texts:,})"
        )


if __name__ == "__main__":
    sys.exit(main())
