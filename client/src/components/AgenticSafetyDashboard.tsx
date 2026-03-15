import { useState, useCallback, useRef } from "react";
import { connectSSE, generateGuardrails } from "../router/processor";
import type { LLMConfig } from "../types/types";
import {
  parseStreamPayload,
  isResult,
  type EvaluationResult,
  type GuardrailRule,
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

const AGENT_BASE = "http://127.0.0.1:5002";
const LLM_LINK_OPENAI = `${AGENT_BASE}/prompt`;
const LLM_LINK_CLAUDE = `${AGENT_BASE}/claude`;

const defaultConfig: LLMConfig = {
  personality_statement: "You are a helpful assistant",
  description: "A test chatbot",
  system_prompts: [],
  disallowed_topics: [],
  llm_link: LLM_LINK_OPENAI,
};

type AgentChoice = "openai" | "claude" | "custom";

function parseLines(s: string): string[] {
  return s
    .split(/\n/)
    .map((x) => x.trim())
    .filter(Boolean);
}

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
  const [behavior, setBehavior] = useState("You are a helpful assistant");
  const [description, setDescription] = useState("A test chatbot");
  const [systemPromptsStr, setSystemPromptsStr] = useState("");
  const [disallowedTopicsStr, setDisallowedTopicsStr] = useState("");
  const [numCases, setNumCases] = useState(5);
  const [agentChoice, setAgentChoice] = useState<AgentChoice>("openai");
  const [customLlmLink, setCustomLlmLink] = useState("");
  const [paramsOpen, setParamsOpen] = useState(false);
  const [paramsError, setParamsError] = useState<string | null>(null);
  const [showAdvancedJson, setShowAdvancedJson] = useState(false);
  const [guardrails, setGuardrails] = useState<GuardrailRule[] | null>(null);
  const [guardrailsLoading, setGuardrailsLoading] = useState(false);
  const [guardrailsError, setGuardrailsError] = useState<string | null>(null);
  const disconnectRef = useRef<(() => void) | null>(null);

  const onMessage = useCallback((raw: string) => {
    const payload = parseStreamPayload(raw) as StreamPayload | null;
    if (!payload) return;
    if (payload.type === "ready") {
      setStatus("Running tests…");
      setResults([]);
    } else if (isResult(payload)) {
      setResults((prev) => [...prev, payload]);
    } else if (payload.type === "done") {
      setStatus("Evaluation complete.");
    } else if (payload.type === "error") {
      setError(payload.error);
    }
  }, []);

  const getLlmLink = useCallback((): string => {
    if (agentChoice === "claude") return LLM_LINK_CLAUDE;
    if (agentChoice === "custom") return customLlmLink.trim() || LLM_LINK_OPENAI;
    return LLM_LINK_OPENAI;
  }, [agentChoice, customLlmLink]);

  const startEvaluation = useCallback(() => {
    setError(null);
    setParamsError(null);
    setResults([]);
    const num = Number(numCases);
    if (Number.isNaN(num) || num < 1 || num > 50) {
      setParamsError("Num cases must be between 1 and 50.");
      return;
    }
    setIsStreaming(true);
    setStatus("Generating red-team prompts…");
    const system_prompts = parseLines(systemPromptsStr);
    const disallowed_topics = parseLines(disallowedTopicsStr);
    const llm_link = getLlmLink();
    let body: Record<string, unknown> = {
      behavior: behavior.trim() || defaultConfig.personality_statement,
      description: description.trim() || defaultConfig.description,
      system_prompts,
      disallowed_topics,
      num_cases: num,
      llm_link,
    };
    if (guardrails != null && guardrails.length > 0) {
      body = { ...body, guardrails };
    }
    connectSSE(defaultConfig, {
      onMessage,
      onOpen: () => {
        setStatus("Generating red-team prompts…");
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
  }, [onMessage, behavior, description, systemPromptsStr, disallowedTopicsStr, numCases, getLlmLink, guardrails]);

  const stopEvaluation = useCallback(() => {
    disconnectRef.current?.();
    disconnectRef.current = null;
    setIsStreaming(false);
  }, []);

  const failedResults = results.filter((r) => !r.evaluation.passed);
  const handleGenerateGuardrails = useCallback(() => {
    const failed = results.filter((r) => !r.evaluation.passed);
    if (failed.length === 0) return;
    setGuardrailsLoading(true);
    setGuardrailsError(null);
    generateGuardrails(failed)
      .then((rules) => {
        setGuardrails(rules);
        setGuardrailsLoading(false);
      })
      .catch((e) => {
        setGuardrailsError(e instanceof Error ? e.message : "Failed to generate guardrails");
        setGuardrailsLoading(false);
      });
  }, [results]);

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
              Burger.AI
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
              {guardrails != null && guardrails.length > 0 && ` · Using ${guardrails.length} guardrail(s)`}
            </span>
            {guardrails != null && guardrails.length > 0 && !isStreaming && (
              <button
                type="button"
                onClick={() => setGuardrails(null)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
              >
                Clear guardrails
              </button>
            )}
            {!isStreaming && results.length > 0 && failedResults.length > 0 && (
              <button
                type="button"
                onClick={handleGenerateGuardrails}
                disabled={guardrailsLoading}
                className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 shadow-sm hover:bg-amber-100 disabled:opacity-50"
              >
                {guardrailsLoading ? "Generating…" : "Generate guardrails from failures"}
              </button>
            )}
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
              <h3 className="mb-3 text-sm font-semibold text-slate-800">Evaluation parameters</h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-xs font-medium text-slate-600">Behavior (personality statement)</label>
                  <input
                    type="text"
                    value={behavior}
                    onChange={(e) => setBehavior(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="You are a helpful assistant"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-xs font-medium text-slate-600">Description</label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="A test chatbot"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">System prompts (one per line)</label>
                  <textarea
                    value={systemPromptsStr}
                    onChange={(e) => setSystemPromptsStr(e.target.value)}
                    rows={3}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="Optional, one per line"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Disallowed topics (one per line)</label>
                  <textarea
                    value={disallowedTopicsStr}
                    onChange={(e) => setDisallowedTopicsStr(e.target.value)}
                    rows={3}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="Optional, one per line"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Num cases</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={numCases}
                    onChange={(e) => setNumCases(Number(e.target.value) || 5)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-xs font-medium text-slate-600">Link to LLM / Agent</label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="agent"
                        checked={agentChoice === "openai"}
                        onChange={() => setAgentChoice("openai")}
                        className="text-indigo-600"
                      />
                      <span className="text-sm text-slate-700">OpenAI payment agent</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="agent"
                        checked={agentChoice === "claude"}
                        onChange={() => setAgentChoice("claude")}
                        className="text-indigo-600"
                      />
                      <span className="text-sm text-slate-700">Claude agent</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="agent"
                        checked={agentChoice === "custom"}
                        onChange={() => setAgentChoice("custom")}
                        className="text-indigo-600"
                      />
                      <span className="text-sm text-slate-700">Custom URL</span>
                    </label>
                    {agentChoice === "custom" && (
                      <input
                        type="url"
                        value={customLlmLink}
                        onChange={(e) => setCustomLlmLink(e.target.value)}
                        placeholder="https://host:port/prompt or /claude"
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      />
                    )}
                  </div>
                </div>
              </div>
              {paramsError && <p className="mt-2 text-sm text-red-600">{paramsError}</p>}
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => setShowAdvancedJson((v) => !v)}
                  className="text-xs font-medium text-slate-500 hover:text-slate-700"
                >
                  {showAdvancedJson ? "Hide" : "Show"} JSON payload
                </button>
                {showAdvancedJson && (
                  <pre className="mt-2 overflow-auto rounded-lg border border-slate-200 bg-white p-2 font-mono text-xs text-slate-700">
                    {JSON.stringify(
                      {
                        behavior: behavior.trim() || defaultConfig.personality_statement,
                        description: description.trim() || defaultConfig.description,
                        system_prompts: parseLines(systemPromptsStr),
                        disallowed_topics: parseLines(disallowedTopicsStr),
                        num_cases: Number(numCases) || 5,
                        llm_link: getLlmLink(),
                      },
                      null,
                      2
                    )}
                  </pre>
                )}
              </div>
            </div>
          </div>
        )}
        {error && (
          <div className="mx-auto max-w-7xl px-4 py-2 sm:px-6">
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          </div>
        )}
        {guardrailsError && (
          <div className="mx-auto max-w-7xl px-4 py-2 sm:px-6">
            <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Guardrails: {guardrailsError}
            </div>
          </div>
        )}
        {guardrails != null && guardrails.length > 0 && (
          <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-800">
                Proposed guardrails ({guardrails.length})
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {guardrails.map((rule, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-xs font-medium text-indigo-800">
                        {rule.type === "pre_hook" ? "Pre-hook" : rule.type === "post_hook" ? "Post-hook" : rule.type}
                      </span>
                      {rule.tool_name && (
                        <span className="truncate text-xs text-slate-500" title={rule.tool_name}>
                          {rule.tool_name === "*" ? "all tools" : rule.tool_name}
                        </span>
                      )}
                    </div>
                    {rule.condition && (
                      <p className="mb-1 break-all font-mono text-xs text-slate-700" title={rule.condition}>
                        {rule.condition}
                      </p>
                    )}
                    {rule.action && (
                      <p className="text-xs text-slate-600">
                        <span className="font-medium">Action:</span> {rule.action}
                      </p>
                    )}
                    {rule.message && (
                      <p className="mt-1 break-words text-xs text-slate-500" title={rule.message}>
                        {rule.message}
                      </p>
                    )}
                    {rule.target_field && (
                      <p className="text-xs text-slate-500">
                        <span className="font-medium">Field:</span> {rule.target_field}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
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
                {(() => {
                  const total = results.length;
                  const passed = results.filter((r) => r.evaluation.passed).length;
                  const pct = total ? Math.round((passed / total) * 100) : 0;
                  return (
                    <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                      <span className="text-sm font-medium text-slate-700">Overall pass rate</span>
                      <span className="text-2xl font-semibold tabular-nums text-slate-900">
                        {total ? `${pct}%` : "—"}
                      </span>
                      {total > 0 && (
                        <span className="text-sm text-slate-500">
                          {passed} passed, {total - passed} failed (of {total} tests)
                        </span>
                      )}
                    </div>
                  );
                })()}
                <p className="mb-4 text-sm text-slate-500">
                  Pass rate by category. Tight shape = low pass rate, wide shape = high pass rate.
                </p>
                <ExecutiveRadar results={results} />
                {isStreaming && (
                  <div className="mt-6">
                    <p className="mb-1.5 text-xs text-slate-500">{status || "Running tests…"}</p>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full w-1/3 rounded-full bg-indigo-500 animate-[evaluator-progress_1.8s_ease-in-out_infinite]"
                        role="progressbar"
                        aria-label="Evaluation in progress"
                      />
                    </div>
                  </div>
                )}
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
