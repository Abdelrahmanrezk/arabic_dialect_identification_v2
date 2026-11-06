---
name: data-preparation
description: "Plan and incrementally implement QADI data preparation with understandable object-oriented design and explicit approval gates."
argument-hint: "Describe the preparation story, input source, and expected outputs."
agent: agent
---

# Data Preparation

Follow the [project instructions](../copilot-instructions.md), including story and architecture approval, one-unit-at-a-time implementation, and separate approval for each Git action. These approvals are not granted by invoking this prompt.

Limit this stage to data preparation. Do not implement model training, evaluation of models, or deployment. Do not create a complete pipeline in one pass.

## Inspect and clarify

1. Read the relevant project configuration, existing data-handling code, and nearby tests. Verify available dependencies and validation commands rather than assuming them.
2. Check whether DVC is configured by inspecting existing DVC configuration, pipeline files, and `.dvc` pointer files. Follow the repository's existing data-versioning policy. Do not initialize DVC, install it, change remotes or tracking, run `dvc pull`/`push`/`add`/`repro`, or alter DVC metadata unless that action is part of the approved story and separately approved when it changes repository or remote state. If required corpus files are unavailable locally, report that and ask before retrieving them.
3. Inspect corpus filenames and the actual schema or header, displaying at most five sample records in total. Preserve raw files: do not modify, move, or copy them, and do not embed raw records in code, tests, documentation, or commits. If DVC is configured, keep raw corpus data out of ordinary Git tracking and use DVC only for agreed derived artifacts, following the existing repository setup.
4. Clarify the preparation objective and unresolved decisions: source format, text and label fields, label mapping, invalid or missing records, duplicates, Arabic normalization, output schema, and a separate derived-output location. Do not silently strip diacritics, change letters, or remove text that may carry dialect information.
5. Determine whether existing official splits must be preserved or new train, validation, and test splits are needed. Agree split proportions, seed, stratification, and grouping where applicable. Identify leakage risks from duplicate texts, authors, or other shared sources using available metadata; state limitations where metadata is missing. Fit learned preprocessing on training data only.

## Propose the story and design

Present and record under `docs/`:

- The story's purpose, expected outcome, scope, non-goals, assumptions, and measurable acceptance criteria.
- A lightweight object-oriented architecture showing responsibilities, inputs, outputs, collaborators, and data flow. Consider loading, validation, preparation, and splitting responsibilities only where needed; do not introduce a class or interface merely to fill a template.
- Ordered tasks mapped to acceptance criteria, with dependencies, validation, documentation, integration, review, and PR preparation.
- An agreed data contract: record schema, label policy, transformations, rejection policy, output location and format, and split policy when applicable.
- A validation plan using synthetic fixtures, covering agreed record policies, label integrity, deterministic transformations, raw-data preservation, and disjoint splits where applicable.

Stop here and wait for explicit approval of the story, design, and tasks. Do not begin production implementation or Git actions in this first response.

## Continue only after approval

1. Follow the shared branch-approval workflow before production implementation.
2. Explain and implement one class, method, or function and its focused tests at a time. Run available relevant checks, explain the result, and wait for approval before the next unit.
3. Write only agreed derived outputs to the separate output location. Do not overwrite existing artifacts without approval. Report aggregate input, accepted, rejected, duplicate, label, and split counts as applicable, with configuration and provenance needed for reproducibility; do not dump corpus contents.
4. After the units are approved, integrate and validate the preparation pipeline as a separate task. Update task status, design decisions, public docstrings, and README commands to reflect actual behavior.
5. Complete review and address in-scope findings before requesting separate approvals for commits, pushing, and PR creation. Do not automatically merge.

At each pause, report the completed task, how the code works, checks actually run and their results, outstanding decisions or failures, and the next proposed unit. At stage completion, summarize acceptance-criteria coverage and any remaining blockers. Never claim unconfigured or unexecuted checks passed.