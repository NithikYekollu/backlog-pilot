"use client";

import { GitHubIssue, TrackedIssue } from "@/lib/types";

interface IssueCardProps {
  issue: GitHubIssue;
  tracked?: TrackedIssue;
  onTriage: () => void;
  onFix: () => void;
  onSync: () => void;
  triageLoading: boolean;
  fixLoading: boolean;
}

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 30) return `${diffDays}d ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}

const severityColors: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-green-100 text-green-800 border-green-200",
};

const categoryColors: Record<string, string> = {
  bug: "bg-red-50 text-red-700",
  feature: "bg-blue-50 text-blue-700",
  refactor: "bg-purple-50 text-purple-700",
  docs: "bg-teal-50 text-teal-700",
  infra: "bg-gray-100 text-gray-700",
};

const statusLabels: Record<string, { label: string; color: string }> = {
  running: { label: "Running", color: "bg-blue-100 text-blue-800" },
  finished: { label: "Completed", color: "bg-green-100 text-green-800" },
  failed: { label: "Failed", color: "bg-red-100 text-red-800" },
  stopped: { label: "Stopped", color: "bg-gray-100 text-gray-700" },
  blocked: { label: "Needs Input", color: "bg-amber-100 text-amber-800" },
};

export default function IssueCard({
  issue,
  tracked,
  onTriage,
  onFix,
  onSync,
  triageLoading,
  fixLoading,
}: IssueCardProps) {
  const hasTriage = tracked?.triage_result;
  const triageRunning = tracked?.triage_status === "running";
  const fixRunning = tracked?.fix_status === "running";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-gray-400">#{issue.number}</span>
            <span className="text-xs text-gray-400">{timeAgo(issue.updated_at)}</span>
            {issue.comments > 0 && (
              <span className="text-xs text-gray-400">{issue.comments} comments</span>
            )}
          </div>
          <a
            href={issue.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-base font-semibold text-gray-900 hover:text-indigo-600 transition-colors"
          >
            {issue.title}
          </a>
          {/* Labels */}
          {issue.labels.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {issue.labels.map((label) => (
                <span
                  key={label.id}
                  className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                  style={{
                    backgroundColor: `#${label.color}20`,
                    color: `#${label.color}`,
                    border: `1px solid #${label.color}40`,
                  }}
                >
                  {label.name}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-2 flex-shrink-0">
          {!hasTriage && !triageRunning && (
            <button
              onClick={onTriage}
              disabled={triageLoading}
              className="rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 transition-colors whitespace-nowrap"
            >
              {triageLoading ? "Starting..." : "Run Triage"}
            </button>
          )}

          {(triageRunning || fixRunning) && (
            <button
              onClick={onSync}
              className="rounded-lg bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 transition-colors whitespace-nowrap"
            >
              Refresh Status
            </button>
          )}

          {hasTriage && tracked?.triage_result?.can_auto_fix && !tracked.fix_session_id && (
            <button
              onClick={onFix}
              disabled={fixLoading}
              className="rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition-colors whitespace-nowrap"
            >
              {fixLoading ? "Starting..." : "Approve Fix"}
            </button>
          )}
        </div>
      </div>

      {/* Triage Status */}
      {tracked?.triage_status && !hasTriage && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-500">Triage:</span>
          <StatusBadge status={tracked.triage_status} />
          {tracked.devin_url && (
            <a
              href={tracked.devin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-indigo-600 hover:underline"
            >
              View in Devin
            </a>
          )}
        </div>
      )}

      {/* Triage Result */}
      {hasTriage && tracked?.triage_result && (
        <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Triage Result
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border ${
                severityColors[tracked.triage_result.severity] || "bg-gray-100 text-gray-700"
              }`}
            >
              {tracked.triage_result.severity}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                categoryColors[tracked.triage_result.category] || "bg-gray-100 text-gray-700"
              }`}
            >
              {tracked.triage_result.category}
            </span>
            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
              {tracked.triage_result.estimated_effort} effort
            </span>
          </div>
          <p className="text-sm text-gray-700 mb-2">
            <strong>Summary:</strong> {tracked.triage_result.summary}
          </p>
          <p className="text-sm text-gray-600">
            <strong>Approach:</strong> {tracked.triage_result.suggested_approach}
          </p>
          {tracked.triage_result.can_auto_fix && (
            <p className="text-xs text-emerald-600 mt-2 font-medium">
              Devin can auto-fix this issue
            </p>
          )}
        </div>
      )}

      {/* Fix Status */}
      {tracked?.fix_status && (
        <div className="mt-3 flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500">Fix:</span>
          <StatusBadge status={tracked.fix_status} />
          {tracked.devin_url && (
            <a
              href={tracked.devin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-indigo-600 hover:underline"
            >
              View in Devin
            </a>
          )}
          {tracked.pr_url && (
            <a
              href={tracked.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
            >
              View PR
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const info = statusLabels[status] || {
    label: status,
    color: "bg-gray-100 text-gray-700",
  };

  return (
    <span className="flex items-center gap-1.5">
      {status === "running" && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
        </span>
      )}
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${info.color}`}
      >
        {info.label}
      </span>
    </span>
  );
}
