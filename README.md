# Arabic Dialect Identification V2

Arabic dialect identification using the QCRI Arabic Dialects Identification (QADI) Corpus.

## Setup

```powershell
uv sync
```

The corpus is tracked by DVC (`data.dvc`) and is expected under `data/raw/`. No DVC remote is configured yet, so the data is not retrieved with `dvc pull`.

## Package layout

```text
src/arabic_dialect_identification_v2/
└── preprocessed_raw/            # cleaning of raw corpus text
    ├── rules.py                 # TextCleaningRule (contract), RegexReplacementRule, DiacriticRemover
    ├── rule_factory.py          # ArabicCleaningRuleFactory: the agreed rules and their order
    └── text_normalizer.py       # TextNormalizer: applies injected rules in order
tests/                           # pytest tests, mirroring the package layout
docs/                            # stories, designs, data contracts, task status
notebooks/                       # exploratory work (not imported by the package)
data/                            # corpus, tracked by DVC (not by Git)
```

## Text normalization

The rules, their order, and the reasoning behind them are recorded in [docs/data-preparation.md](docs/data-preparation.md). In summary, the normalizer:

- deletes the placeholders `حسابشخصي`/`حسابشخصى` and `رابطويب`, and removes tatweel;
- removes diacritics, except in الله;
- unifies alef forms;
- reduces repeated letters to two and repeated symbols or emoji to one;
- collapses whitespace.

```python
from arabic_dialect_identification_v2.preprocessed_raw import (
    ArabicCleaningRuleFactory,
    TextNormalizer,
)

normalizer = TextNormalizer(ArabicCleaningRuleFactory().create_rules())
normalizer.normalize("حسابشخصي جمـــيل جدااااا 😂😂😂")  # 'جميل جداا 😂'
```

The normalizer currently works on in-memory text only. A command that processes the corpus files and a DVC stage are planned in a follow-up story.

On Windows terminals, set `$env:PYTHONIOENCODING='utf-8'` before printing Arabic text.

## Tests

```powershell
uv run pytest
```

## Development workflow

The [project instructions](.github/copilot-instructions.md) define understandable, object-oriented development for both human-written and AI-generated code.

Start each implementation story with its purpose, acceptance criteria, architecture, and ordered tasks. Record the approved story and design under `docs/`. Implement and validate one class, method, or function at a time, then pause for user approval before the next unit. Integrate the full pipeline only after its individual units have been approved.

The workflow is: approve the story and design, approve branch creation, implement incrementally, review and fix findings, then separately approve commits, pushing, and PR creation. Nothing is merged automatically.

## Stage prompts

In VS Code Copilot Chat, type `/data-preparation` and provide the preparation objective, input source, and expected outputs. You can also use **Chat: Run Prompt...** to select the [data-preparation prompt](.github/prompts/data-preparation.prompt.md).

The first response inspects the available project context and proposes the story, data contract, object-oriented architecture, and tasks. It waits for approval before production implementation. This stage preserves raw corpus data and does not include model training or deployment.

Additional stage prompts will be added when requested. Validation commands must be taken from the current project configuration; the instructions do not imply that test or lint tools are already configured.
