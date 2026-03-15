import { useState, useCallback, useRef } from "react";
import { connectSSE } from "../router/processor";
import type { LLMConfig } from "../types/types";
import {
  parseStreamPayload,
  isResult,
  type EvaluationResult,
  type StreamPayload,
  CATEGORY_LABELS,
} from "../types/stream";
import { ExecutiveRadar } from "./ExecutiveRadar";
import {
  ScoreDistributionChart,
  SycophancyBarChart,
  PromptInjectionFlow,
  RolePlayScatter,
  PIIBubbleChart,
  HallucinationViolin,
  JailbreakBar,
} from "./CategoryCharts";
import { SubparCaseCard } from "./SubparCaseCard";

const SUBPAR_SCORE_THRESHOLD = 6;

const CATEGORIES = [
  "Executive",
  "Sycophancy Check",
  "Prompt Injection Leak",
  "Role-Play Drift",
  "PII/Sensitive Leak",
  "Hallucination Variance",
  "Advanced Jailbreak",
];

const defaultConfig: LLMConfig = {
  personality_statement: "You are a helpful assistant",
  description: "A test chatbot",
  system_prompts: [],
  disallowed_topics: [],
  llm_link: "http://127.0.0.1:5002",
};

const defaultParamsJson = `{
  "behavior": "You are a helpful assistant",
  "description": "A test chatbot",
  "system_prompts": [],
  "disallowed_topics": [],
  "llm_link": "http://127.0.0.1:5002",
  "num_cases": 5
}`;

function SubparSection({
  results,
  category,
}: {
  results: EvaluationResult[];
  category: string;
}) {
  const subpar = results.filter(
    (r) => r.category === category && r.evaluation.score < SUBPAR_SCORE_THRESHOLD
  );
  if (subpar.length === 0) return null;
  return (
    <div className="mt-8">
      <h3 className="mb-3 text-sm font-semibold text-slate-800">
        Subpar cases (score &lt; {SUBPAR_SCORE_THRESHOLD})
      </h3>
      <div className="space-y-2">
        {subpar.map((r, i) => (
          <SubparCaseCard key={`${r.category}-${r.case_index}-${i}`} result={r} />
        ))}
      </div>
    </div>
  );
}

export function AgenticSafetyDashboard() {
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("Executive");
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [paramsJson, setParamsJson] = useState<string>(defaultParamsJson);
  const [paramsOpen, setParamsOpen] = useState(false);
  const [paramsError, setParamsError] = useState<string | null>(null);
  const disconnectRef = useRef<(() => void) | null>(null);

  const onMessage = useCallback((raw: string) => {
    const payload = parseStreamPayload(raw) as StreamPayload | null;
    if (!payload) return;
    if (payload.type === "ready") {
      setStatus("Connected. Evaluating…");
      setResults([]);
    } else if (isResult(payload)) {
      setResults((prev) => [...prev, payload]);
    } else if (payload.type === "done") {
      setStatus("Evaluation complete.");
    } else if (payload.type === "error") {
      setError(payload.error);
    }
  }, []);

  const startEvaluation = useCallback(() => {
    setError(null);
    setParamsError(null);
    setStatus("Connecting…");
    setResults([]);
    let body: Record<string, unknown> | undefined;
    const trimmed = paramsJson.trim();
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed) as Record<string, unknown>;
        body = parsed;
      } catch {
        setParamsError("Invalid JSON. Fix the parameters or clear the box to use defaults.");
        return;
      }
    }
    connectSSE(defaultConfig, {
      onMessage,
      onOpen: () => {
        setIsStreaming(true);
        setStatus("Stream open. Waiting for results…");
      },
      onClose: () => setIsStreaming(false),
      onError: (err: unknown) => {
        setError(
          typeof err === "string" ? err : err instanceof Error ? err.message : "Unknown error"
        );
        setIsStreaming(false);
      },
    }, body).then((disconnect) => {
      disconnectRef.current = disconnect;
    });
  }, [onMessage, paramsJson]);

  const stopEvaluation = useCallback(() => {
    disconnectRef.current?.();
    disconnectRef.current = null;
    setIsStreaming(false);
  }, []);

  return (
    <div
      className="min-h-screen text-slate-800"
      style={{
        background: "linear-gradient(to bottom, #d4edda 0%, #a8d5ba 40%, #5a9f6f 70%, #2d5a3d 100%)",
      }}
    >
      {/* Header - white background, black text */}
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">
              Agentic Safety Dashboard
            </h1>
            <p className="text-sm text-slate-500">
              Safety & reliability across Sycophancy, Prompt Injection, Role-Play, PII, Hallucination & Jailbreak
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setParamsOpen((o) => !o)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            >
              {paramsOpen ? "Hide parameters" : "Edit parameters"}
            </button>
            <span className="text-sm text-slate-500">
              {status || "Idle"}
              {results.length > 0 && ` · ${results.length} result(s)`}
            </span>
            {isStreaming ? (
              <button
                onClick={stopEvaluation}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-red-700"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={startEvaluation}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-indigo-700"
              >
                Run Evaluation
              </button>
            )}
          </div>
        </div>
        {paramsOpen && (
          <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="mb-2 text-sm font-medium text-slate-700">
                Request body for POST /stream (paste JSON the backend accepts)
              </p>
              <p className="mb-2 text-xs text-slate-500">
                Keys: behavior, description, system_prompts, disallowed_topics, llm_link, num_cases — or nested llm_config.
              </p>
              <textarea
                value={paramsJson}
                onChange={(e) => setParamsJson(e.target.value)}
                placeholder={defaultParamsJson}
                rows={8}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-800 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              {paramsError && (
                <p className="mt-2 text-sm text-red-600">{paramsError}</p>
              )}
            </div>
          </div>
        )}
        {error && (
          <div className="mx-auto max-w-7xl px-4 py-2 sm:px-6">
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          </div>
        )}
      </header>

      <div className="mx-auto flex max-w-7xl gap-6 px-4 py-6 sm:px-6">
        {/* Sidebar */}
        <aside className="w-48 shrink-0">
          <nav className="sticky top-6 space-y-0.5 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
                  selectedCategory === cat
                    ? "bg-indigo-100 text-indigo-800"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {cat === "Executive" ? "📊 Executive Summary" : CATEGORY_LABELS[cat] || cat}
              </button>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main className="min-w-0 flex-1">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            {selectedCategory === "Executive" && (
              <div>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">
                  Executive Summary — Radar
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  Pass rate by category. Tight circle = low risk; wide shape = boundaries to fix.
                </p>
                <ExecutiveRadar results={results} />
              </div>
            )}
            {selectedCategory === "Sycophancy Check" && (
              <div>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">
                  Sycophancy — Divergent Bar
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  Evaluation score per case. Low scores indicate alignment with biased prompts.
                </p>
                <h3 className="mb-2 text-sm font-medium text-slate-700">Score distribution</h3>
                <ScoreDistributionChart results={results} category="Sycophancy Check" />
                <div className="mt-4" />
                <SycophancyBarChart results={results} />
                <SubparSection results={results} category="Sycophancy Check" />
              </div>
            )}
            {selectedCategory === "Prompt Injection Leak" && (
              <div>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">
                  Prompt Injection — Information Flow
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  How many prompts led to tool calls vs no tool; how many passed the safety check.
                </p>
                <h3 className="mb-2 text-sm font-medium text-slate-700">Score distribution</h3>
                <ScoreDistributionChart results={results} category="Prompt Injection Leak" />
                <div className="mt-4" />
                <PromptInjectionFlow results={results} />
                <SubparSection results={results} category="Prompt Injection Leak" />
              </div>
            )}
            {selectedCategory === "Role-Play Drift" && (
              <div>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">
                  Role-Play Drift — Consistency Score
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  Score per case. Drift from persona shows as lower scores.
                </p>
                <h3 className="mb-2 text-sm font-medium text-slate-700">Score distribution</h3>
                <ScoreDistributionChart results={results} category="Role-Play Drift" />
                <div className="mt-4" />
                <RolePlayScatter results={results} />
                <SubparSection results={results} category="Role-Play Drift" />
              </div>
            )}
            {selectedCategory === "PII/Sensitive Leak" && (
              <div>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">
                  PII / Sensitive Leak — Tool Frequency
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  Tool-call frequency by type. High-risk tools highlighted.
                </p>
                <h3 className="mb-2 text-sm font-medium text-slate-700">Score distribution</h3>
                <ScoreDistributionChart results={results} category="PII/Sensitive Leak" />
                <div className="mt-4" />
                <PIIBubbleChart results={results} />
                <SubparSection results={results} category="PII/Sensitive Leak" />
              </div>
            )}
            {selectedCategory === "Hallucination Variance" && (
              <div>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">
                  Hallucination — Score Distribution
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  Distribution of evaluation scores. Wide spread indicates instability.
                </p>
                <h3 className="mb-2 text-sm font-medium text-slate-700">Score distribution</h3>
                <HallucinationViolin results={results} />
                <SubparSection results={results} category="Hallucination Variance" />
              </div>
            )}
            {selectedCategory === "Advanced Jailbreak" && (
              <div>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">
                  Advanced Jailbreak — Per-case Score
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  Score per jailbreak attempt. Low scores = successful defense.
                </p>
                <h3 className="mb-2 text-sm font-medium text-slate-700">Score distribution</h3>
                <ScoreDistributionChart results={results} category="Advanced Jailbreak" />
                <div className="mt-4" />
                <JailbreakBar results={results} />
                <SubparSection results={results} category="Advanced Jailbreak" />
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
