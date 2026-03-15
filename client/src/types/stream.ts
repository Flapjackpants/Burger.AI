/** Guardrail rule from generate-guardrails (pre_hook / post_hook / message_hook). */
export interface GuardrailRule {
  type: string;
  tool_name?: string;
  condition?: string;
  action?: string;
  message?: string;
  target_field?: string;
  /** For message_hook: phrases to match in user message (case-insensitive). */
  phrases?: string[];
}

/** Single evaluation result from the stream (one per prompt). */
export interface EvaluationResult {
  type: "result";
  category: string;
  case_index: number;
  prompt: string;
  agent_reply: string;
  tool_calls: Array<{ tool_name: string; arguments?: unknown; result?: unknown }>;
  evaluation: { passed: boolean; reason: string; score: number };
  expected_behavior?: string | null;
}

export interface ReadyPayload {
  type: "ready";
  message: string;
}

export interface DonePayload {
  type: "done";
}

export interface StreamErrorPayload {
  type: "error";
  error: string;
}

export type StreamPayload = ReadyPayload | EvaluationResult | DonePayload | StreamErrorPayload;

export function isResult(p: StreamPayload): p is EvaluationResult {
  return p.type === "result";
}

export function parseStreamPayload(data: string): StreamPayload | null {
  try {
    const raw = JSON.parse(data) as { type?: string };
    if (raw && typeof raw.type === "string") return raw as StreamPayload;
  } catch {
    /* ignore */
  }
  return null;
}

/** Category display names and short keys for charts. */
export const CATEGORY_LABELS: Record<string, string> = {
  "Sycophancy Check": "Sycophancy",
  "Prompt Injection Leak": "Prompt Injection",
  "Role-Play Drift": "Role-Play Drift",
  "PII/Sensitive Leak": "PII Leak",
  "Hallucination Variance": "Hallucination",
  "Advanced Jailbreak": "Jailbreak",
};
