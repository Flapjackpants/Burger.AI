const BASE_URL = import.meta.env.VITE_LOCAL_SERVER_ROUTE;

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SSEOptions {
  onMessage: (data: string) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
  eventType?: string; // listen to a named event (default: "message")
  withCredentials?: boolean;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  headers?: Record<string, string>;
}

export interface ApiResponse<T = unknown> {
  data: T | null;
  error: string | null;
  status: number;
}

// ─── SSE ─────────────────────────────────────────────────────────────────────

/**
 * Opens an SSE connection to the given endpoint.
 * Returns a cleanup function to close the connection.
 *
 * @example
 * const close = connectSSE("/stream", {
 *   onMessage: (data) => console.log(data),
 *   onError: (e) => console.error(e),
 * });
 *
 * // Later, to close:
 * close();
 */
export function connectSSE(endpoint: string, options: SSEOptions): () => void {
  const {
    onMessage,
    onError,
    onOpen,
    onClose,
    eventType = "message",
    withCredentials = false,
  } = options;

  const url = `${BASE_URL}${endpoint}`;
  const source = new EventSource(url, { withCredentials });

  source.onopen = () => {
    onOpen?.();
  };

  // Named event listener (e.g. event: update)
  source.addEventListener(eventType, (event: MessageEvent) => {
    try {
      const parsed = tryParseJSON(event.data);
      onMessage(parsed ?? event.data);
    } catch {
      onMessage(event.data);
    }
  });

  // Fallback for unnamed "message" events when eventType is custom
  if (eventType !== "message") {
    source.onmessage = (event: MessageEvent) => {
      try {
        const parsed = tryParseJSON(event.data);
        onMessage(parsed ?? event.data);
      } catch {
        onMessage(event.data);
      }
    };
  }

  source.onerror = (error: Event) => {
    onError?.(error);

    // If the server closed the stream, readyState becomes CLOSED
    if (source.readyState === EventSource.CLOSED) {
      onClose?.();
    }
  };

  // Return cleanup function
  return () => {
    source.close();
    onClose?.();
  };
}

// ─── Regular HTTP requests ────────────────────────────────────────────────────

/**
 * Generic fetch wrapper for standard JSON requests.
 *
 * @example
 * const { data, error } = await request<{ message: string }>("/api/hello");
 */
export async function request<T = unknown>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const { method = "GET", body, headers = {} } = options;

  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    const data: T = await response.json();

    return {
      data,
      error: null,
      status: response.status,
    };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Unknown error",
      status: 0,
    };
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Safely parses a JSON string. Returns null if parsing fails.
 */
function tryParseJSON<T = unknown>(value: string): T | null {
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}
