const BASE_URL =
  import.meta.env.VITE_LOCAL_SERVER_ROUTE ?? "http://127.0.0.1:5001";
import type { LLMConfig } from "../types/types";
import type { EvaluationResult, GuardrailRule } from "../types/stream";

// ─── Types ────────────────────────────────────────────────────────────────────
export interface SSEOptions {
  onMessage: (data: string) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
  eventType?: string; // listen to a named event (default: "message")
  withCredentials?: boolean;
}

/**
 * Generate guardrail rules from failed evaluation results.
 * POSTs to /generate-guardrails; returns the list of rules or [] on error.
 */
export async function generateGuardrails(
  failedResults: EvaluationResult[],
): Promise<GuardrailRule[]> {
  try {
    const response = await fetch(BASE_URL + "/generate-guardrails", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ failed_results: failedResults }),
    });
    if (!response.ok) return [];
    const data = (await response.json()) as { guardrails?: GuardrailRule[] };
    return Array.isArray(data.guardrails) ? data.guardrails : [];
  } catch (e) {
    const errMsg = e instanceof Error ? e.message : String(e);
    const isNetworkErr = /fetch|network|loaded|connection|refused/i.test(errMsg);
    const msg = isNetworkErr
      ? `Cannot reach backend at ${BASE_URL}. Is it running?`
      : errMsg || "Failed to generate guardrails";
    throw new Error(msg);
  }
}

/**
 * Establishes connection with SSE server. Sends POST to /stream.
 * If body is provided it is sent as-is; otherwise builds from config (behavior, description, etc.).
 */
export async function connectSSE(
  config: LLMConfig,
  options: SSEOptions,
  body?: Record<string, unknown>,
): Promise<() => void> {
  const { onMessage, onError, onOpen, onClose } = options;

  const controller = new AbortController();
  const payload =
    body != null && Object.keys(body).length > 0
      ? body
      : {
          behavior: config.personality_statement,
          description: config.description,
          system_prompts: config.system_prompts,
          disallowed_topics: config.disallowed_topics,
          llm_link: config.llm_link,
          num_cases: 5,
        };

  try {
    const response = await fetch(BASE_URL + "/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      signal: controller.signal,
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    onOpen?.();

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) throw new Error("No response body");

    // Read stream chunks
    (async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });

          // Parse SSE format: each line is "data: <payload>"
          const lines = chunk.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6).trim();
              if (data && data !== "[DONE]") {
                onMessage(data);
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          onError?.(err.message);
        }
      } finally {
        onClose?.();
      }
    })();
  } catch (err) {
    onError?.(err);
  }

  // Return cleanup / disconnect function
  return () => {
    controller.abort();
  };
}
