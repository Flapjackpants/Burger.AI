import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { EvaluationResult } from "../types/stream";
import { CATEGORY_LABELS } from "../types/stream";

/** Aggregate pass rate (0–100) per category for radar. */
function aggregateByCategory(results: EvaluationResult[]) {
  const byCat: Record<string, { passed: number; total: number }> = {};
  for (const r of results) {
    if (!byCat[r.category]) byCat[r.category] = { passed: 0, total: 0 };
    byCat[r.category].total += 1;
    if (r.evaluation.passed) byCat[r.category].passed += 1;
  }
  return Object.entries(byCat).map(([category, { passed, total }]) => ({
    category: CATEGORY_LABELS[category] || category,
    fullMark: 100,
    score: total ? Math.round((passed / total) * 100) : 0,
    count: total,
  }));
}

export function ExecutiveRadar({ results }: { results: EvaluationResult[] }) {
  const data = aggregateByCategory(results);
  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500">
        Run evaluation to see radar summary.
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={320}>
      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
        <PolarGrid stroke="#e2e8f0" />
        <PolarAngleAxis
          dataKey="category"
          tick={{ fill: "#475569", fontSize: 11 }}
          tickLine={false}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tick={{ fill: "#64748b", fontSize: 10 }}
        />
        <Radar
          name="Pass rate %"
          dataKey="score"
          stroke="#6366f1"
          fill="#6366f1"
          fillOpacity={0.35}
          strokeWidth={2}
        />
        <Tooltip
          content={({ payload }) =>
            payload?.[0] && (
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                <p className="font-medium text-slate-800">{payload[0].payload.category}</p>
                <p className="text-sm text-slate-600">
                  {payload[0].payload.score}% pass ({payload[0].payload.count} cases)
                </p>
              </div>
            )
          }
        />
        <Legend />
      </RadarChart>
    </ResponsiveContainer>
  );
}
