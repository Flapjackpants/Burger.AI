import { useState, useCallback } from "react";
import type { EvaluationResult } from "../types/stream";

interface SubparCaseCardProps {
  result: EvaluationResult;
  caseLabel?: string;
}

export function SubparCaseCard({ result, caseLabel }: SubparCaseCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { evaluation, prompt, agent_reply, tool_calls, expected_behavior } = result;
  const summary = `Case ${caseLabel ?? result.case_index + 1} · Score ${evaluation.score}/10 · ${evaluation.passed ? "Passed" : "Failed"}`;

  const copyJson = useCallback(() => {
    const json = JSON.stringify(result, null, 2);
    void navigator.clipboard.writeText(json);
  }, [result]);

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50"
      >
        <span className="text-sm font-medium text-slate-800">{summary}</span>
        <span className="text-slate-400">{expanded ? "▼" : "▶"}</span>
      </button>
      {expanded && (
        <div className="border-t border-slate-200 px-4 py-3 space-y-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prompt</p>
            <p className="mt-1 text-sm text-slate-800 whitespace-pre-wrap">{prompt}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Agent reply</p>
            <p className="mt-1 text-sm text-slate-800 whitespace-pre-wrap">{agent_reply}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tool calls</p>
            <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-100 p-2 text-xs text-slate-800">
              {JSON.stringify(tool_calls, null, 2)}
            </pre>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Evaluation</p>
            <p className="mt-1 text-sm text-slate-800">
              Passed: {evaluation.passed ? "Yes" : "No"} · Score: {evaluation.score}/10
            </p>
            <p className="mt-1 text-sm text-slate-600">{evaluation.reason}</p>
          </div>
          {expected_behavior != null && expected_behavior !== "" && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Expected behavior</p>
              <p className="mt-1 text-sm text-slate-800">{expected_behavior}</p>
            </div>
          )}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Raw JSON</p>
            <div className="relative">
              <pre className="max-h-64 overflow-auto rounded bg-slate-100 p-3 text-xs text-slate-800">
                {JSON.stringify(result, null, 2)}
              </pre>
              <button
                type="button"
                onClick={copyJson}
                className="absolute top-2 right-2 rounded bg-slate-700 px-2 py-1 text-xs font-medium text-white hover:bg-slate-800"
              >
                Copy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
