import { useState, useEffect, useRef } from "react";
import { connectSSE } from "./router/processor"; // your connectSSE function
import type { LLMConfig } from "./types/types";

const config: LLMConfig = {
  personality_statement: "You are a helpful assistant",
  description: "A test chatbot",
  system_prompts: [],
  disallowed_topics: [],
  llm_link: "http://127.0.0.1:5002",
};

function App() {
  const [output, setOutput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(0);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sessionId === 0) return; // don't run on initial mount

    let disconnect: (() => void) | null = null;

    const start = async () => {
      setIsStreaming(true);
      setOutput("");

      disconnect = await connectSSE(config, {
        onMessage: (chunk) => {
          setOutput((prev) => prev + chunk);
          // auto scroll to bottom as chunks arrive
          outputRef.current?.scrollTo(0, outputRef.current.scrollHeight);
        },
        onOpen: () => console.log("stream opened"),
        onClose: () => setIsStreaming(false),
        onError: (err) => {
          console.error(err);
          setIsStreaming(false);
        },
      });
    };

    start();

    return () => {
      disconnect?.();
    };
  }, [sessionId]);

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "2rem" }}>
      <h1>Stream Tester</h1>

      {/* Output box */}
      <div
        ref={outputRef}
        style={{
          border: "1px solid #ccc",
          borderRadius: 8,
          padding: "1rem",
          minHeight: 200,
          maxHeight: 500,
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          fontFamily: "monospace",
          marginBottom: "1rem",
          background: "#f9f9f9",
        }}
      >
        {output || (
          <span style={{ color: "#aaa" }}>Output will appear here...</span>
        )}
        {isStreaming && <span className="cursor">▋</span>}
      </div>

      {/* Controls */}
      <div style={{ display: "flex", gap: "1rem" }}>
        <button
          onClick={() => setSessionId((prev) => prev + 1)}
          disabled={isStreaming}
        >
          {isStreaming ? "Streaming..." : "Start Stream"}
        </button>

        {isStreaming && (
          <button onClick={() => setSessionId((prev) => prev + 1)}>Stop</button>
        )}
      </div>
    </div>
  );
}

export default App;
