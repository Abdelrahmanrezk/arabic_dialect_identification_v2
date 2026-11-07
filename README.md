# Arabic Dialect Identification V2

Arabic dialect identification using the QCRI Arabic Dialects Identification (QADI) Corpus.

## Setup

```powershell
uv sync
```

The raw corpus is tracked by DVC (`data/raw.dvc`) and is expected under `data/raw/`. No DVC remote is configured yet, so the data stays local and is not retrieved with `dvc pull`.

## Data preparation

Cleans the raw QADI tweets and removes empty, duplicate and overlapping rows. The full story, rules and decisions are in [docs/stories/data-preparation.md](docs/stories/data-preparation.md).

### Run it

With DVC (recommended; re-runs only when the raw data, the code, the settings or `uv.lock` change):

```powershell
uv run dvc repro
```

Directly (refuses to overwrite existing outputs unless `--overwrite` is given):

```powershell
uv run python -m arabic_dialect_identification_v2.data.prepare --config config/data_preprocessing.yaml
```

### Inputs and outputs

| | Path |
|---|---|
| Settings | `config/data_preprocessing.yaml` |
| Raw input (DVC-tracked, never modified) | `data/raw/train/strat_train_set_excel.csv`, `data/raw/evaluate/strat_test_set_excel.csv` |
| Cleaned train | `data/processed/train.parquet` |
| Cleaned evaluate | `data/processed/evaluate.parquet` |
| Report (counts, settings used, input fingerprints) | `data/processed/preparation_report.json` |

Outputs keep the four input columns: `id`, `dialect`, `dialect_l_encoded`, `text`.

### Cleaning rules (in order)

1. Replace the placeholders `حسابشخصي`, `حسابشخصى`, `رابطويب` with a space
2. Remove tatweel `ـ`
3. Remove diacritics, except in words containing `لله` (الله، والله، بالله، لله، اللهم)
4. Unify `أ إ آ ٱ` → `ا`
5. Keep at most 2 repeated letters (Arabic and Latin)
6. Keep 1 of any repeated symbol or emoji, even when separated by spaces (digits untouched)
7. Collapse whitespace

After cleaning, rows with empty text and repeated texts are dropped in each file, and train rows whose text also appears in evaluate are dropped. All values and switches are set in `config/data_preprocessing.yaml`.

### Using the cleaner in code

```python
from arabic_dialect_identification_v2.data.cleaner import ArabicTextCleaner
from arabic_dialect_identification_v2.data.config import DataPreparationConfig

config = DataPreparationConfig.from_yaml("config/data_preprocessing.yaml")
cleaner = ArabicTextCleaner(config.cleaning)
cleaner.clean("حسابشخصي جمـــيل جدااااا 😂😂😂")  # 'جميل جداا 😂'
```

On Windows terminals, set `$env:PYTHONIOENCODING='utf-8'` before printing Arabic text.

## Package layout

```text
src/arabic_dialect_identification_v2/
└── data/                    # data preparation
    ├── config.py            # DataPreparationConfig: load and validate the settings file
    ├── loader.py            # QadiCsvLoader: read one raw CSV and check the data contract
    ├── cleaner.py           # ArabicTextCleaner: the seven text-cleaning rules
    ├── record_filter.py     # RecordFilter: drop empty / duplicate / overlapping rows, count them
    ├── writer.py            # ParquetDatasetWriter: save Parquet + JSON report, all-or-nothing
    ├── pipeline.py          # DataPreparationPipeline: load → clean → filter → write
    └── prepare.py           # command-line entry point
tests/data/                  # pytest tests, one file per module, synthetic data only
config/                      # settings files
docs/stories/                # stories, designs, data contracts, task status
notebooks/                   # exploratory work (not imported by the package)
data/                        # corpus and derived data, tracked by DVC (not by Git)
dvc.yaml                     # DVC pipeline (stage: prepare)
```

## Checks

Run all three before committing. Each catches a different kind of problem:

```powershell
uv run pytest       # tests: does the code give the right results?
uv run ruff check   # linter: unused imports, import order, likely bugs, style
uv run mypy         # type checker (strict): is every value the right type where it is used?
```

- `ruff check --fix` corrects most style findings automatically (import order, missing final newline).
- Settings for both tools are in `pyproject.toml` under `[tool.ruff]` and `[tool.mypy]`.
- `notebooks/` is excluded from `ruff`, because exploratory work is kept separate from the package.
- Ruff rules `RUF001`–`RUF003` are switched off: they flag Arabic letters as "ambiguous characters", which is expected in this project.
- `mypy` checks `src/` in strict mode; tests are checked by `ruff` and by running them.

## Development workflow

The [project instructions](.github/copilot-instructions.md) define understandable, object-oriented development for both human-written and AI-generated code.

Start each implementation story with its purpose, acceptance criteria, architecture, and ordered tasks. Record the approved story and design under `docs/`. Implement and validate one class, method, or function at a time, then pause for user approval before the next unit. Integrate the full pipeline only after its individual units have been approved.

The workflow is: approve the story and design, approve branch creation, implement incrementally, review and fix findings, then separately approve commits, pushing, and PR creation. Nothing is merged automatically.

## Stage prompts

In VS Code Copilot Chat, type `/data-preparation` and provide the preparation objective, input source, and expected outputs. You can also use **Chat: Run Prompt...** to select the [data-preparation prompt](.github/prompts/data-preparation.prompt.md).

The first response inspects the available project context and proposes the story, data contract, object-oriented architecture, and tasks. It waits for approval before production implementation. This stage preserves raw corpus data and does not include model training or deployment.

Additional stage prompts will be added when requested. Validation commands must be taken from the current project configuration; the configured checks are listed under [Checks](#checks).