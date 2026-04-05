# Codex CLI + Groq Integration Action Plan

## Goal

Turn the existing God Mode app into a GUI frontend for a local Codex CLI runtime, while keeping Groq as the underlying LLM provider through Codex's custom model provider support.

## Target Architecture

1. React web app remains the chat UI and renders streaming text, status, evidence, and artifacts.
2. FastAPI remains the transport layer and session/settings surface.
3. Backend gains a runtime switch:
   - `langgraph`: existing internal orchestration path
   - `codex_cli`: external Codex CLI path
4. Codex CLI is executed non-interactively with JSON event streaming.
5. Groq is injected into Codex as a custom OpenAI-compatible provider using the Groq API key and base URL.

## Execution Steps

1. Add normalized runtime settings for external agent execution.
2. Add a Codex adapter that:
   - builds the Codex command
   - injects Groq provider config
   - streams Codex JSONL events
   - maps terminal/runtime events into the existing Vercel AI SDK stream format
3. Update `/api/chat` to route requests to either LangGraph or Codex based on saved settings.
4. Update `/api/models` so the frontend receives Codex-compatible model choices when the Codex runtime is active.
5. Extend the settings UI with:
   - runtime selector
   - Codex executable path
   - Codex model
   - Codex sandbox / approval mode
   - Groq-backed provider guidance
6. Document local setup requirements and smoke-test the build.

## Constraints

- Do not remove the current LangGraph path.
- Keep the existing frontend streaming contract intact.
- Avoid storing secrets in source; use the existing settings persistence.
- Prefer runtime-generated Codex config over requiring a global user config edit.

## Risks

- Codex JSON event types may evolve between CLI releases.
- Some Codex features may still contact OpenAI services for non-inference metadata even when the model provider is custom.
- Groq model availability and naming can change independently of the UI defaults.
- Tool approval semantics differ between the in-app backend and the Codex runtime.

## Verification

- FastAPI imports and builds cleanly.
- Web app TypeScript build passes.
- `codex exec --json` accepts the generated custom provider configuration.
- Saving settings and switching runtimes does not break the existing chat UI.
