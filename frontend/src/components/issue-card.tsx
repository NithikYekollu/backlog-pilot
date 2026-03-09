/**
 * Issue card component — displays a single GitHub issue with triage/fix controls.
 *
 * TODO: The status field names ("running", "finished", etc.) come from the
 *       Devin API. Update statusLabels if the API adds new states.
 */
"use client";

import {
  GitHubIssue,
  TrackedIssue,
  getTriageSummary,
  getTriageApproach,
  getTriageAutofix,
  getTriageDifficulty,
} from "@/lib/types";

interface IssueCardProps {
  issue: GitHubIssue;
  tracked?: TrackedIssue;
  repo: string;
  onTriage: () => void;
  onFix: () => void;
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

/**
 * Given a hex color (without #), return a text color that is readable
 * on a light tinted background. Darkens light colors so they don't look washed out.
 */
function getLabelTextColor(hex: string): string {
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  // Perceived luminance (sRGB)
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  if (luminance > 0.6) {
    // Light color — darken it significantly for readability
    const factor = 0.4;
    return `rgb(${Math.round(r * factor)}, ${Math.round(g * factor)}, ${Math.round(b * factor)})`;
  }
  // Already dark enough — use as-is
  return `#${hex}`;
}

const difficultyColors: Record<string, string> = {
  easy: "bg-green-100 text-green-800 border-green-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  hard: "bg-red-100 text-red-800 border-red-200",
  // Backward-compat with old schema
  small: "bg-green-100 text-green-800 border-green-200",
  large: "bg-red-100 text-red-800 border-red-200",
};

const statusLabels: Record<string, { label: string; color: string }> = {
  queued: { label: "Queued", color: "bg-purple-100 text-purple-800" },
  running: { label: "Running", color: "bg-blue-100 text-blue-800" },
  finished: { label: "Completed", color: "bg-green-100 text-green-800" },
  failed: { label: "Failed", color: "bg-red-100 text-red-800" },
  stopped: { label: "Stopped", color: "bg-gray-100 text-gray-700" },
  blocked: { label: "Needs Input", color: "bg-amber-100 text-amber-800" },
};

export default function IssueCard({
  issue,
  tracked,
  repo,
  onTriage,
  onFix,
  triageLoading,
  fixLoading,
}: IssueCardProps) {
  const hasTriage = tracked?.triage_result;
  const triageRunning = tracked?.triage_status === "running";

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
              {issue.labels.map((label) => {
                const textColor = getLabelTextColor(label.color);
                return (
                  <span
                    key={label.id}
                    className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold"
                    style={{
                      backgroundColor: `#${label.color}22`,
                      color: textColor,
                      border: `1px solid #${label.color}55`,
                    }}
                  >
                    {label.name}
                  </span>
                );
              })}
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

          {hasTriage && !tracked?.fix_session_id && (
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

      {/* Devin session link — always visible when a session exists */}
      {tracked?.devin_url && (
        <div className="mt-3 flex items-center gap-2 flex-wrap">
          {tracked.triage_status && !hasTriage && (
            <>
              <span className="text-xs text-gray-500">Triage:</span>
              <StatusBadge status={tracked.triage_status} />
            </>
          )}
          <a
            href={tracked.devin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-colors"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
            </svg>
            View in Devin
          </a>
        </div>
      )}

      {/* Triage status (no Devin URL yet) */}
      {tracked?.triage_status && !hasTriage && !tracked.devin_url && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-500">Triage:</span>
          <StatusBadge status={tracked.triage_status} />
        </div>
      )}

      {/* Triage Result */}
      {hasTriage && tracked?.triage_result && (
        <>
          <TriageResultPanel result={tracked.triage_result} repo={repo} />
          {/* Devin link row after triage */}
          {tracked.devin_url && (
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <a
                href={tracked.devin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-colors"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
                View in Devin
              </a>
            </div>
          )}
        </>
      )}

      {/* Fix Status */}
      {tracked?.fix_status && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">Fix:</span>
            <StatusBadge status={tracked.fix_status} />
            {tracked.fix_session_id && (
              <span className="text-xs font-mono text-gray-400" title={tracked.fix_session_id}>
                {tracked.fix_session_id.slice(0, 8)}
              </span>
            )}
            </div>
          {tracked.pr_url && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 flex items-center gap-2">
              <span className="text-sm font-medium text-emerald-800">PR Ready:</span>
              <a
                href={tracked.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-semibold text-emerald-700 hover:text-emerald-900 underline underline-offset-2 transition-colors"
              >
                {tracked.pr_url}
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TriageResultPanel({ result, repo }: { result: NonNullable<TrackedIssue["triage_result"]>; repo: string }) {
  const summary = getTriageSummary(result);
  const approach = getTriageApproach(result);
  const autofix = getTriageAutofix(result);
  const difficulty = getTriageDifficulty(result);

  return (
    <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 p-4">
      {/* Header badges */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Triage Result
        </span>
        {difficulty && (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border ${
              difficultyColors[difficulty] || "bg-gray-100 text-gray-700 border-gray-200"
            }`}
          >
            {difficulty}
          </span>
        )}
        {result.likely_area && (
          <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
            {result.likely_area}
          </span>
        )}
        {result.needs_human_clarification && (
          <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200">
            Needs clarification
          </span>
        )}
      </div>

      {/* Summary */}
      {summary && (
        <p className="text-sm text-gray-700 mb-2">
          <strong>Summary:</strong> {summary}
        </p>
      )}

      {/* Recommended next step */}
      {approach && (
        <p className="text-sm text-gray-600 mb-2">
          <strong>Next step:</strong> {approach}
        </p>
      )}

      {/* Suspected files */}
      {result.suspected_files && result.suspected_files.length > 0 && (
        <div className="mb-2">
          <strong className="text-xs text-gray-500">Suspected files:</strong>
          <div className="flex flex-wrap gap-1 mt-1">
            {result.suspected_files.map((file) => (
              <a
                key={file}
                href={`https://github.com/${repo}/blob/main/${file}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 text-xs font-mono text-indigo-700 hover:bg-indigo-50 hover:text-indigo-900 transition-colors"
              >
                <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                {file}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Acceptance criteria */}
      {result.acceptance_criteria && result.acceptance_criteria.length > 0 && (
        <div className="mb-2">
          <strong className="text-xs text-gray-500">Acceptance criteria:</strong>
          <ul className="list-disc list-inside mt-1 space-y-0.5">
            {result.acceptance_criteria.map((criterion, i) => (
              <li key={i} className="text-xs text-gray-600">
                {criterion}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Auto-fix indicator */}
      {autofix && (
        <p className="text-xs text-emerald-600 mt-2 font-medium">
          Devin can auto-fix this issue
        </p>
      )}
      {!autofix && result.needs_human_clarification && (
        <p className="text-xs text-amber-600 mt-2 font-medium">
          This issue needs human clarification before fixing
        </p>
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
