# Project Instructions

## Purpose and current setup

This project develops Arabic dialect identification using the QCRI Arabic Dialects Identification (QADI) Corpus. It is a Python package using Python python3.10, 3.11, 3.12, 3.13 or newer, `uv` for dependency management, and `pyproject.toml`/`uv.lock` for project configuration and dependency versions. The corpus files are under `data/`; inspect the corpus format and existing handling by listing file names, reading the schema or header, and printing at most 5 sample records before using or changing the files.

## Design and implementation

- Prefer clear, maintainable, typed Python and a structured package layout as the project grows. Define the package layout in the first change that introduces new modules, and record it in the README. Place tests under `tests/` and exploratory work under `notebooks/` or `scripts/exploration/`.
- Understandability comes first for both human-written and AI-generated code. Use descriptive names, explicit control flow, small methods, and clear public docstrings; avoid clever shortcuts. Explain unfamiliar decisions in plain language when implementing or reviewing code.
- Use object-oriented design for domain behavior and pipeline orchestration, not a chain of standalone functions as the main architecture. Give each class one clear responsibility. Small entry-point functions and stateless helpers are acceptable when a class would add no useful responsibility or state.
- Prefer composition and dependency injection. Introduce interfaces or abstract base classes when they establish a useful shared contract; avoid unnecessary abstraction and deep inheritance.
- Keep responsibilities separated. Do not put research or exploratory code in production modules under the package source directory. Place it in `notebooks/` or `scripts/exploration/` and do not import it from package code.
- Follow established project patterns. Do not assume a framework, API, model format, or deployment tool is required unless the project or task specifies it.
- Preserve raw corpus data. Do not modify, move, or copy raw corpus files, and do not print their full contents, commit them to version control, or include them in generated code, tests, or documentation unless the task explicitly requires it.

## Story, architecture, and tasks

- Before production code changes, present a complete story: user or research need, intended outcome, scope, non-goals, assumptions, and measurable acceptance criteria. Ask about unresolved requirements instead of inventing them.
- Describe the architecture before implementation: class responsibilities, collaborators, inputs and outputs, data flow, ownership boundaries, and relevant tradeoffs. Keep the design proportional to the story; a diagram is optional, not a reason to add complexity.
- Break the story into ordered, small tasks tied to acceptance criteria. Include dependencies, focused validation, documentation, integration, review, and pull-request preparation. Record the approved story and design under `docs/` and keep task status and decisions current there.
- Obtain approval for the story, architecture, and task list before implementing. Clearly distinguish completed, remaining, and blocked tasks. Do not mark the story complete while acceptance criteria or required checks remain unmet.

## Incremental implementation

- Implement one understandable unit at a time: one class, method, or function. Choose a method instead of a whole class when the class is too large to explain and review comfortably. Do not generate the full pipeline in one pass.
- Before each unit, explain its responsibility, inputs, outputs, collaborators, and the task it satisfies. Keep accompanying tests and documentation focused on that unit.
- After each unit, run the relevant available checks, explain what changed and how it works, report check results and open issues, and wait for explicit user approval before implementing the next unit. Approval for the story does not waive this pause.
- Assemble the full pipeline only after its constituent units have been approved, treating integration as a separate task with focused validation and its own approval pause.

## Branch, review, and pull request

- Follow this order for implementation stories: approved story and design, approved branch creation, incremental implementation and validation, code review, fixes and revalidation, approved commits and push, then an approved pull request.
- Ask for separate explicit approval before each branch creation, commit, push, and pull-request creation. State the target and intended action. A request to implement code is not approval for these Git actions. Do not merge automatically.
- Before implementation, inspect the current branch and working tree, propose a branch name tied to the story, and obtain approval to create it. Preserve unrelated changes and never reset or discard the user's work.
- Review human-written and AI-generated changes against the same standards: correctness, understandable object-oriented design, data integrity, acceptance criteria, regressions, tests, and documentation. Report findings by severity with file references; fix in-scope findings and rerun relevant checks before PR creation.
- Use the repository's PR template when present. Include the story, architecture summary, completed tasks, validation evidence, and any unresolved limitations in the PR description. Never claim a review, check, push, or PR succeeded without evidence; report unavailable tools or permissions as blockers.

## Stage prompts

- Keep reusable stage-specific prompts under `.github/prompts/` and reference these shared instructions instead of duplicating them. Create further stage prompts only when requested.
- Start data-preparation work with [the data-preparation prompt](prompts/data-preparation.prompt.md). It covers preparation only, not model training or deployment, and must follow the same story, unit-approval, and Git gates.

## Changes and validation

- Make focused changes. Update README.md when behavior, setup, commands, or package layout changes, and update docstrings for any public function or class whose behavior changes.
- Use `uv` and keep `uv.lock` consistent with dependency changes in `pyproject.toml`.
- Check the project’s current configuration for available tests and validation commands. Run relevant configured checks; do not assume or report that unconfigured checks have passed.
- Report what changed, which checks ran, and any unresolved assumptions or failures.