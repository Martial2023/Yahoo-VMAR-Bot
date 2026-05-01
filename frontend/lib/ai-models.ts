/**
 * Catalogue of AI models exposed in the dashboard.
 *
 * The dashboard stores `openrouterId` in `bot_settings.ai_model` because the
 * Python backend forwards that value to the OpenRouter API verbatim. The `id`
 * is only used as the React `key` and `Select` value (display id).
 *
 * If OpenRouter's slug for a model changes, edit `openrouterId` here — no
 * backend change is needed.
 */

export type AIProvider = "Anthropic" | "OpenAI" | "Google" | "xAI";

export type AIModel = {
  /** Display id used as React key and Select value. */
  id: string;
  /** Human-friendly name shown in the dropdown. */
  name: string;
  /** Logical grouping in the dropdown. */
  provider: AIProvider;
  /** Exact slug sent to OpenRouter (`provider/model-version`). */
  openrouterId: string;
};

export const AI_MODELS: AIModel[] = [
  // ---- Anthropic ----
  {
    id: "claude-opus-4-5",
    name: "Claude Opus 4.5",
    provider: "Anthropic",
    openrouterId: "anthropic/claude-opus-4.5",
  },
  {
    id: "claude-sonnet-4-5",
    name: "Claude Sonnet 4.5",
    provider: "Anthropic",
    openrouterId: "anthropic/claude-sonnet-4.5",
  },
  {
    id: "claude-haiku-4-5",
    name: "Claude Haiku 4.5",
    provider: "Anthropic",
    openrouterId: "anthropic/claude-haiku-4.5",
  },
  // ---- OpenAI ----
  {
    id: "gpt-5-1-codex",
    name: "GPT-5.1 Codex",
    provider: "OpenAI",
    openrouterId: "openai/gpt-5.1-codex",
  },
  {
    id: "gpt-5-1",
    name: "GPT 5.1",
    provider: "OpenAI",
    openrouterId: "openai/gpt-5.1",
  },
  // ---- Google ----
  {
    id: "gemini-3-0-pro",
    name: "Gemini 3.0 Pro",
    provider: "Google",
    openrouterId: "google/gemini-3.0-pro",
  },
  // ---- xAI ----
  {
    id: "grok-4-1-fast",
    name: "Grok 4.1 Fast",
    provider: "xAI",
    openrouterId: "x-ai/grok-4.1-fast",
  },
];

/** Ordered list of providers as they appear in the dropdown. */
export const AI_PROVIDERS: AIProvider[] = ["Anthropic", "OpenAI", "Google", "xAI"];

/** Find the model whose `openrouterId` matches `value`, falling back gracefully. */
export function findModelByOpenrouterId(value: string): AIModel | undefined {
  return AI_MODELS.find((m) => m.openrouterId === value);
}
