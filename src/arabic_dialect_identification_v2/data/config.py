"""Settings for the QADI data-preparation step.

The settings live in a YAML file (``config/data_preprocessing.yaml``).
This module reads that file once, checks every value, and returns a
typed, read-only object that the rest of the pipeline can trust.
"""

from __future__ import annotations

import codecs
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class ConfigurationError(Exception):
    """Raised when the settings file is missing, unreadable, or invalid."""


class _StrictSettings(BaseModel):
    """Shared base: values cannot change after loading, and unknown keys are rejected.

    Rejecting unknown keys catches typos in the YAML file
    (for example ``max_leter_repeats``) instead of silently ignoring them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceSettings(_StrictSettings):
    """Where the raw CSV files are and what they must contain."""

    train_path: Path
    evaluate_path: Path
    encoding: str = "utf-8-sig"
    expected_columns: tuple[str, ...] = Field(min_length=1)
    text_column: str

    @field_validator("encoding")
    @classmethod
    def _encoding_must_exist(cls, encoding: str) -> str:
        try:
            codecs.lookup(encoding)
        except LookupError as error:
            raise ValueError(f"unknown encoding '{encoding}'") from error
        return encoding

    @field_validator("expected_columns")
    @classmethod
    def _columns_must_be_unique(cls, columns: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(columns)) != len(columns):
            raise ValueError(f"expected_columns contains duplicates: {list(columns)}")
        return columns

    @model_validator(mode="after")
    def _text_column_must_be_expected(self) -> SourceSettings:
        if self.text_column not in self.expected_columns:
            raise ValueError(
                f"text_column '{self.text_column}' is not in expected_columns {list(self.expected_columns)}"
            )
        return self


class OutputSettings(_StrictSettings):
    """Where the cleaned files and the report are written."""

    directory: Path
    train_file_name: str
    evaluate_file_name: str
    report_file_name: str

    @field_validator("train_file_name", "evaluate_file_name")
    @classmethod
    def _must_be_parquet(cls, file_name: str) -> str:
        if not file_name.endswith(".parquet"):
            raise ValueError(f"'{file_name}' must end with .parquet")
        return file_name

    @field_validator("report_file_name")
    @classmethod
    def _must_be_json(cls, file_name: str) -> str:
        if not file_name.endswith(".json"):
            raise ValueError(f"'{file_name}' must end with .json")
        return file_name

    @property
    def train_path(self) -> Path:
        """Full path of the cleaned train file."""
        return self.directory / self.train_file_name

    @property
    def evaluate_path(self) -> Path:
        """Full path of the cleaned evaluate file."""
        return self.directory / self.evaluate_file_name

    @property
    def report_path(self) -> Path:
        """Full path of the JSON report."""
        return self.directory / self.report_file_name


class CleaningSettings(_StrictSettings):
    """Values used by the Arabic text-cleaning rules."""

    placeholders: tuple[str, ...]
    max_letter_repeats: int = Field(ge=1)
    max_symbol_repeats: int = Field(ge=1)
    protected_word_fragment: str = Field(min_length=1)

    @field_validator("placeholders")
    @classmethod
    def _placeholders_must_not_be_blank(cls, placeholders: tuple[str, ...]) -> tuple[str, ...]:
        if any(not placeholder.strip() for placeholder in placeholders):
            raise ValueError("placeholders must not contain empty strings")
        return placeholders


class RowPolicySettings(_StrictSettings):
    """Which rows are dropped after cleaning."""

    drop_empty_texts: bool
    drop_duplicate_texts: bool
    drop_train_evaluate_overlap: bool


class DataPreparationConfig(_StrictSettings):
    """All settings for the data-preparation step, grouped by purpose.

    Create it with :meth:`from_yaml` rather than directly, so that file
    and format problems are reported as :class:`ConfigurationError`.
    """

    source: SourceSettings
    output: OutputSettings
    cleaning: CleaningSettings
    row_policy: RowPolicySettings

    @classmethod
    def from_yaml(cls, config_path: Path | str) -> DataPreparationConfig:
        """Read, parse and validate a settings file.

        Args:
            config_path: Path to the YAML settings file.

        Returns:
            A validated, read-only settings object.

        Raises:
            ConfigurationError: If the file does not exist, is not valid YAML,
                is not a mapping, or contains missing, unknown or invalid values.
        """
        path = Path(config_path)
        raw_settings = cls._read_yaml_mapping(path)
        try:
            return cls.model_validate(raw_settings)
        except ValidationError as error:
            raise ConfigurationError(f"Invalid settings in '{path}':\n{error}") from error

    @staticmethod
    def _read_yaml_mapping(path: Path) -> dict[str, Any]:
        """Return the YAML file's top-level mapping, or raise ConfigurationError."""
        if not path.is_file():
            raise ConfigurationError(f"Settings file not found: '{path}'")
        try:
            with path.open(encoding="utf-8") as settings_file:
                content = yaml.safe_load(settings_file)
        except yaml.YAMLError as error:
            raise ConfigurationError(f"Settings file is not valid YAML: '{path}'\n{error}") from error
        if not isinstance(content, dict):
            raise ConfigurationError(f"Settings file must contain a mapping of sections: '{path}'")
        return content
