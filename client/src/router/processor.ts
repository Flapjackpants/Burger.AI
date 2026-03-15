const BASE_URL = import.meta.env.VITE_LOCAL_SERVER_ROUTE;
import type { LLMConfig } from "../types/types";

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
