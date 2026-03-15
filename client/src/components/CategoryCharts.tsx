import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
  LabelList,
  ReferenceLine,
} from "recharts";
import type { EvaluationResult } from "../types/stream";

// ─── Shared: Score distribution (0–10 buckets) for any category ───────────────
export function ScoreDistributionChart({
  results,
  category,
}: {
  results: EvaluationResult[];
  category: string;
}) {
  const filtered = results.filter((r) => r.category === category);
  const buckets: Record<number, number> = {};
  for (let i = 0; i <= 10; i++) buckets[i] = 0;
  for (const r of filtered) {
    const s = Math.min(10, Math.max(0, Math.round(r.evaluation.score)));
    buckets[s] = (buckets[s] || 0) + 1;
  }
  const data = Object.entries(buckets).map(([score, count]) => ({
    score: Number(score),
    count,
  }));
  if (filtered.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart
        data={data}
        margin={{ top: 12, right: 12, left: 12, bottom: 24 }}
        layout="vertical"
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis type="number" tick={{ fontSize: 10 }} />
        <YAxis type="category" dataKey="score" width={24} tick={{ fontSize: 10 }} />
        <Tooltip
          content={({ payload }) =>
            payload?.[0] && (
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                <p className="font-medium text-slate-800">Score {payload[0].payload.score}</p>
                <p className="text-sm text-slate-600">{payload[0].payload.count} cases</p>
              </div>
            )
          }
        />
        <Bar dataKey="count" name="Cases" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── 1. Sycophancy: Divergent Bar (Pass vs Fail alignment) ─────────────────────
export function SycophancyBarChart({ results }: { results: EvaluationResult[] }) {
  const filtered = results.filter((r) => r.category === "Sycophancy Check");
  const data = filtered.map((r, i) => ({
    name: `Case ${r.case_index + 1}`,
    score: r.evaluation.score,
    passed: r.evaluation.passed ? 1 : 0,
    failed: r.evaluation.passed ? 0 : 1,
    reason: r.evaluation.reason?.slice(0, 60) + (r.evaluation.reason?.length > 60 ? "…" : ""),
  }));
  if (data.length === 0) return <EmptyChart label="Sycophancy" />;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 10]} tick={{ fontSize: 10 }} />
        <Tooltip
          content={({ payload }) =>
            payload?.[0] && (
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg text-left">
                <p className="font-medium text-slate-800">{payload[0].payload.name}</p>
                <p className="text-sm text-slate-600">Score: {payload[0].payload.score}/10</p>
                {payload[0].payload.reason && (
                  <p className="text-xs text-slate-500 mt-1">{payload[0].payload.reason}</p>
                )}
              </div>
            )
          }
        />
        <Legend />
        <Bar dataKey="score" name="Evaluation score" fill="#6366f1" radius={[4, 4, 0, 0]} />
        <ReferenceLine y={6} stroke="#94a3b8" strokeDasharray="2 2" />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── 2. Prompt Injection: Flow (User → Agent → Tool / No tool) ─────────────────
export function PromptInjectionFlow({ results }: { results: EvaluationResult[] }) {
  const filtered = results.filter((r) => r.category === "Prompt Injection Leak");
  const withTools = filtered.filter((r) => r.tool_calls && r.tool_calls.length > 0).length;
  const noTools = filtered.length - withTools;
  const passed = filtered.filter((r) => r.evaluation.passed).length;
  const data = [
    { name: "User input", value: filtered.length, fill: "#94a3b8" },
    { name: "Agent response", value: filtered.length, fill: "#64748b" },
    { name: "Tool called", value: withTools, fill: withTools > 0 ? "#f59e0b" : "#cbd5e1" },
    { name: "No tool", value: noTools, fill: "#22c55e" },
    { name: "Passed check", value: passed, fill: "#6366f1" },
  ];
  if (filtered.length === 0) return <EmptyChart label="Prompt Injection" />;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4 rounded-xl border border-slate-200 bg-white p-4">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-2">
            <div
              className="h-4 w-4 rounded"
              style={{ backgroundColor: d.fill }}
            />
            <span className="text-sm text-slate-700">{d.name}: {d.value}</span>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-500">
        Information flow: {filtered.length} prompts → {withTools} tool calls, {passed} passed safety check.
      </p>
    </div>
  );
}

// ─── 3. Role-Play Drift: Scatter (case index vs score = distance from persona) ─
export function RolePlayScatter({ results }: { results: EvaluationResult[] }) {
  const filtered = results.filter((r) => r.category === "Role-Play Drift");
  const data = filtered.map((r) => ({
    x: r.case_index,
    y: r.evaluation.score,
    z: 24,
    passed: r.evaluation.passed,
  }));
  if (data.length === 0) return <EmptyChart label="Role-Play Drift" />;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ScatterChart margin={{ top: 12, right: 12, left: 12, bottom: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis type="number" dataKey="x" name="Case" tick={{ fontSize: 10 }} />
        <YAxis type="number" dataKey="y" name="Score" domain={[0, 10]} tick={{ fontSize: 10 }} />
        <ZAxis type="number" dataKey="z" range={[50, 400]} />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={({ payload }) =>
            payload?.[0] && (
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                <p className="font-medium text-slate-800">Case {payload[0].payload.x + 1}</p>
                <p className="text-sm text-slate-600">Persona consistency score: {payload[0].payload.y}/10</p>
              </div>
            )
          }
        />
        <Scatter name="Responses" data={data}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.passed ? "#22c55e" : "#ef4444"} />
          ))}
          <LabelList dataKey="y" position="top" />
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}

// ─── 4. PII Leak: Bubble-style bar (tool/sensitivity frequency) ────────────────
export function PIIBubbleChart({ results }: { results: EvaluationResult[] }) {
  const filtered = results.filter((r) => r.category === "PII/Sensitive Leak");
  const toolCount: Record<string, number> = {};
  for (const r of filtered) {
    if (r.tool_calls?.length) {
      for (const tc of r.tool_calls) {
        const name = tc.tool_name || "tool";
        toolCount[name] = (toolCount[name] || 0) + 1;
      }
    } else {
      toolCount["No tool"] = (toolCount["No tool"] || 0) + 1;
    }
  }
  const data = Object.entries(toolCount).map(([name, count]) => ({
    name,
    count,
    fill: name === "No tool" ? "#22c55e" : count > 2 ? "#ef4444" : "#f59e0b",
  }));
  if (data.length === 0) return <EmptyChart label="PII Leak" />;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip
          content={({ payload }) =>
            payload?.[0] && (
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                <p className="font-medium text-slate-800">{payload[0].payload.name}</p>
                <p className="text-sm text-slate-600">Count: {payload[0].payload.count}</p>
              </div>
            )
          }
        />
        <Bar dataKey="count" name="Frequency" radius={[4, 4, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── 5. Hallucination: Score distribution (uses shared component) ──────────────
export function HallucinationViolin({ results }: { results: EvaluationResult[] }) {
  const filtered = results.filter((r) => r.category === "Hallucination Variance");
  if (filtered.length === 0) return <EmptyChart label="Hallucination" />;
  return <ScoreDistributionChart results={results} category="Hallucination Variance" />;
}

// ─── Advanced Jailbreak: simple bar (pass/fail per case) ──────────────────────
export function JailbreakBar({ results }: { results: EvaluationResult[] }) {
  const filtered = results.filter((r) => r.category === "Advanced Jailbreak");
  const data = filtered.map((r) => ({
    name: `Case ${r.case_index + 1}`,
    passed: r.evaluation.passed ? 10 : 0,
    failed: r.evaluation.passed ? 0 : 10,
    score: r.evaluation.score,
  }));
  if (data.length === 0) return <EmptyChart label="Advanced Jailbreak" />;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 10]} tick={{ fontSize: 10 }} />
        <Tooltip
          content={({ payload }) =>
            payload?.[0] && (
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                <p className="font-medium text-slate-800">{payload[0].payload.name}</p>
                <p className="text-sm text-slate-600">Score: {payload[0].payload.score}/10</p>
              </div>
            )
          }
        />
        <Bar dataKey="score" name="Score" fill="#dc2626" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500">
      No data for {label}. Run evaluation or select another category.
    </div>
  );
}
