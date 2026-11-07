"""End-to-end tests for the pipeline and the prepare command, using small made-up CSV files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from arabic_dialect_identification_v2.data.config import DataPreparationConfig
from arabic_dialect_identification_v2.data.pipeline import DataPreparationPipeline
from arabic_dialect_identification_v2.data.prepare import main

HEADER = "id,dialect,dialect_l_encoded,text\n"
TRAIN_CSV = (
    HEADER
    + "1,EG,3,حسابشخصي ازيك يا جماعة!!!\n"
    + "2,EG,3,رابطويب\n"  # empty after cleaning
    + "3,SA,13,هلا والله\n"
    + "4,SA,13,هلا   والله\n"  # duplicate after cleaning
    + "5,LY,8,تمام 😂😂\n"  # also in evaluate after cleaning
    + "6,KW,6,أحمد جـــميل\n"
)
EVALUATE_CSV = HEADER + "10,LY,8,تمام 😂\n" + "11,SY,15,كيفك\n"


def _settings(raw_dir: Path, output_dir: Path) -> dict:
    return {
        "source": {
            "train_path": str(raw_dir / "train.csv"),
            "evaluate_path": str(raw_dir / "evaluate.csv"),
            "encoding": "utf-8-sig",
            "expected_columns": ["id", "dialect", "dialect_l_encoded", "text"],
            "text_column": "text",
        },
        "output": {
            "directory": str(output_dir),
            "train_file_name": "train.parquet",
            "evaluate_file_name": "evaluate.parquet",
            "report_file_name": "preparation_report.json",
        },
        "cleaning": {
            "placeholders": ["حسابشخصي", "حسابشخصى", "رابطويب"],
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


@pytest.fixture
def project(tmp_path: Path) -> dict[str, Path]:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "train.csv").write_bytes(TRAIN_CSV.encode("utf-8-sig"))
    (raw_dir / "evaluate.csv").write_bytes(EVALUATE_CSV.encode("utf-8-sig"))
    output_dir = tmp_path / "processed"
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.safe_dump(_settings(raw_dir, output_dir), allow_unicode=True), encoding="utf-8")
    return {"raw_dir": raw_dir, "output_dir": output_dir, "config_path": config_path}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(project: dict[str, Path], overwrite: bool = False):
    config = DataPreparationConfig.from_yaml(project["config_path"])
    return DataPreparationPipeline.from_config(config, overwrite=overwrite).run()


def test_pipeline_writes_cleaned_and_filtered_outputs(project: dict[str, Path]) -> None:
    written, _ = _run(project)
    train = pd.read_parquet(written.train_path)
    evaluate = pd.read_parquet(written.evaluate_path)

    assert train["id"].tolist() == [1, 3, 6]
    assert train["text"].tolist() == ["ازيك يا جماعة!", "هلا والله", "احمد جميل"]
    assert evaluate["id"].tolist() == [10, 11]
    assert evaluate["text"].tolist() == ["تمام 😂", "كيفك"]


def test_outputs_keep_the_four_contract_columns_and_types(project: dict[str, Path]) -> None:
    written, _ = _run(project)
    train = pd.read_parquet(written.train_path)
    assert list(train.columns) == ["id", "dialect", "dialect_l_encoded", "text"]
    assert train["id"].dtype == "int64"
    assert train["dialect_l_encoded"].dtype == "int64"


def test_labels_are_unchanged_for_kept_rows(project: dict[str, Path]) -> None:
    written, _ = _run(project)
    train = pd.read_parquet(written.train_path).set_index("id")
    assert train.loc[1, "dialect"] == "EG" and train.loc[1, "dialect_l_encoded"] == 3
    assert train.loc[6, "dialect"] == "KW" and train.loc[6, "dialect_l_encoded"] == 6


def test_report_counts_match_what_happened(project: dict[str, Path]) -> None:
    _, report = _run(project)
    assert report.train.input_rows == 6
    assert report.train.empty_dropped == 1
    assert report.train.duplicates_dropped == 1
    assert report.train.overlap_dropped == 1
    assert report.train.output_rows == 3


def test_no_train_text_appears_in_evaluate(project: dict[str, Path]) -> None:
    written, _ = _run(project)
    train_texts = set(pd.read_parquet(written.train_path)["text"])
    evaluate_texts = set(pd.read_parquet(written.evaluate_path)["text"])
    assert train_texts.isdisjoint(evaluate_texts)


def test_raw_files_are_byte_for_byte_unchanged(project: dict[str, Path]) -> None:
    raw_files = sorted(project["raw_dir"].iterdir())
    before = {path.name: _sha256(path) for path in raw_files}
    _run(project)
    after = {path.name: _sha256(path) for path in sorted(project["raw_dir"].iterdir())}
    assert after == before


def test_report_file_records_settings_and_input_fingerprints(project: dict[str, Path]) -> None:
    written, _ = _run(project)
    report = json.loads(written.report_path.read_text(encoding="utf-8"))
    provenance = report["provenance"]
    assert provenance["settings"]["cleaning"]["max_letter_repeats"] == 2
    assert provenance["inputs"]["train"]["sha256"] == _sha256(project["raw_dir"] / "train.csv")
    assert report["counts"]["train"]["output_rows"] == 3


def test_running_twice_gives_identical_outputs(project: dict[str, Path]) -> None:
    written, _ = _run(project)
    first = {path: _sha256(path) for path in (written.train_path, written.evaluate_path, written.report_path)}
    _run(project, overwrite=True)
    second = {path: _sha256(path) for path in first}
    assert second == first


def test_command_succeeds_and_prints_summary(project: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--config", str(project["config_path"])])
    assert exit_code == 0
    assert "train: 6 in → 3 out" in capsys.readouterr().out


def test_command_refuses_to_overwrite_without_flag(
    project: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(project["config_path"])]) == 0
    assert main(["--config", str(project["config_path"])]) == 1
    assert "already exist" in capsys.readouterr().err
    assert main(["--config", str(project["config_path"]), "--overwrite"]) == 0


def test_command_reports_missing_settings_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--config", str(tmp_path / "missing.yaml")]) == 1
    assert "not found" in capsys.readouterr().err


def test_command_reports_bad_raw_data(project: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    (project["raw_dir"] / "train.csv").write_bytes((HEADER + "abc,EG,3,نص\n").encode("utf-8-sig"))
    assert main(["--config", str(project["config_path"])]) == 1
    assert "not whole numbers" in capsys.readouterr().err
    assert not project["output_dir"].exists()


def test_pipeline_uses_the_loader_label_column(project: dict[str, Path]) -> None:
    _, report = _run(project)
    assert set(report.train.rows_per_dialect) == {"EG", "SA", "KW"}
