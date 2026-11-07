"""Tests for DataPreparationConfig. Uses only small, made-up settings files."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from arabic_dialect_identification_v2.data.config import ConfigurationError, DataPreparationConfig

PROJECT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "data_preprocessing.yaml"


def _valid_settings() -> dict:
    """A complete, valid settings mapping that each test can tweak."""
    return {
        "source": {
            "train_path": "data/raw/train/train.csv",
            "evaluate_path": "data/raw/evaluate/test.csv",
            "encoding": "utf-8-sig",
            "expected_columns": ["id", "dialect", "dialect_l_encoded", "text"],
            "text_column": "text",
        },
        "output": {
            "directory": "data/processed",
            "train_file_name": "train.parquet",
            "evaluate_file_name": "evaluate.parquet",
            "report_file_name": "preparation_report.json",
        },
        "cleaning": {
            "placeholders": ["حسابشخصي", "رابطويب"],
            "max_letter_repeats": 2,
            "max_symbol_repeats": 1,
            "protected_word_fragment": "لله",
        },
        "row_policy": {
            "drop_empty_texts": True,
            "drop_duplicate_texts": True,
            "drop_train_evaluate_overlap": True,
        },
    }


def _write_yaml(tmp_path: Path, settings: object) -> Path:
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    return path


def test_project_config_file_is_valid() -> None:
    config = DataPreparationConfig.from_yaml(PROJECT_CONFIG)
    assert config.source.text_column == "text"
    assert config.cleaning.max_letter_repeats == 2


def test_loads_valid_settings_into_typed_values(tmp_path: Path) -> None:
    config = DataPreparationConfig.from_yaml(_write_yaml(tmp_path, _valid_settings()))

    assert config.source.train_path == Path("data/raw/train/train.csv")
    assert config.source.expected_columns == ("id", "dialect", "dialect_l_encoded", "text")
    assert config.output.train_path == Path("data/processed/train.parquet")
    assert config.output.report_path == Path("data/processed/preparation_report.json")
    assert config.cleaning.placeholders == ("حسابشخصي", "رابطويب")


def test_settings_cannot_be_changed_after_loading(tmp_path: Path) -> None:
    config = DataPreparationConfig.from_yaml(_write_yaml(tmp_path, _valid_settings()))
    with pytest.raises(ValidationError, match="frozen"):
        config.cleaning.max_letter_repeats = 5  # type: ignore[misc]


def test_missing_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        DataPreparationConfig.from_yaml(tmp_path / "does_not_exist.yaml")


def test_broken_yaml_raises_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("source: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="not valid YAML"):
        DataPreparationConfig.from_yaml(path)


def test_non_mapping_yaml_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="mapping"):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, ["just", "a", "list"]))


def test_missing_section_is_rejected(tmp_path: Path) -> None:
    settings = _valid_settings()
    del settings["cleaning"]
    with pytest.raises(ConfigurationError, match="cleaning"):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))


def test_unknown_key_is_rejected_to_catch_typos(tmp_path: Path) -> None:
    settings = _valid_settings()
    settings["cleaning"]["max_leter_repeats"] = 2
    with pytest.raises(ConfigurationError, match="max_leter_repeats"):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))


def test_text_column_must_be_one_of_expected_columns(tmp_path: Path) -> None:
    settings = _valid_settings()
    settings["source"]["text_column"] = "tweet"
    with pytest.raises(ConfigurationError, match="text_column"):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))


def test_duplicate_expected_columns_are_rejected(tmp_path: Path) -> None:
    settings = _valid_settings()
    settings["source"]["expected_columns"] = ["id", "text", "text"]
    with pytest.raises(ConfigurationError, match="duplicates"):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))


@pytest.mark.parametrize("key", ["max_letter_repeats", "max_symbol_repeats"])
def test_repeat_limits_must_be_at_least_one(tmp_path: Path, key: str) -> None:
    settings = _valid_settings()
    settings["cleaning"][key] = 0
    with pytest.raises(ConfigurationError, match=key):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))


def test_blank_placeholder_is_rejected(tmp_path: Path) -> None:
    settings = _valid_settings()
    settings["cleaning"]["placeholders"] = ["حسابشخصي", "  "]
    with pytest.raises(ConfigurationError, match="placeholders"):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))


@pytest.mark.parametrize(
    ("key", "bad_name", "expected"),
    [
        ("train_file_name", "train.csv", ".parquet"),
        ("evaluate_file_name", "evaluate.csv", ".parquet"),
        ("report_file_name", "report.txt", ".json"),
    ],
)
def test_output_file_names_must_have_right_extension(tmp_path: Path, key: str, bad_name: str, expected: str) -> None:
    settings = _valid_settings()
    settings["output"][key] = bad_name
    with pytest.raises(ConfigurationError, match=expected):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))


def test_unknown_encoding_is_rejected(tmp_path: Path) -> None:
    settings = _valid_settings()
    settings["source"]["encoding"] = "utf8-sigg"
    with pytest.raises(ConfigurationError, match="unknown encoding 'utf8-sigg'"):
        DataPreparationConfig.from_yaml(_write_yaml(tmp_path, settings))
