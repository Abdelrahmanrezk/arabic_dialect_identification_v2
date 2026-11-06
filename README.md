# Arabic Dialect Identification V2

Arabic dialect identification using the QCRI Arabic Dialects Identification (QADI) Corpus.

## Development workflow

The [project instructions](.github/copilot-instructions.md) define understandable, object-oriented development for both human-written and AI-generated code.

Start each implementation story with its purpose, acceptance criteria, architecture, and ordered tasks. Record the approved story and design under `docs/`. Implement and validate one class, method, or function at a time, then pause for user approval before the next unit. Integrate the full pipeline only after its individual units have been approved.

The workflow is: approve the story and design, approve branch creation, implement incrementally, review and fix findings, then separately approve commits, pushing, and PR creation. Nothing is merged automatically.

## Stage prompts

In VS Code Copilot Chat, type `/data-preparation` and provide the preparation objective, input source, and expected outputs. You can also use **Chat: Run Prompt...** to select the [data-preparation prompt](.github/prompts/data-preparation.prompt.md).

The first response inspects the available project context and proposes the story, data contract, object-oriented architecture, and tasks. It waits for approval before production implementation. This stage preserves raw corpus data and does not include model training or deployment.

Additional stage prompts will be added when requested. Validation commands must be taken from the current project configuration; the instructions do not imply that test or lint tools are already configured.
