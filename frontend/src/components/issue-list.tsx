"use client";

import { GitHubIssue, TrackedIssue } from "@/lib/types";
import IssueCard from "./issue-card";

interface IssueListProps {
  issues: GitHubIssue[];
  trackedIssues: Map<number, TrackedIssue>;
  onTriage: (issue: GitHubIssue) => void;
  onFix: (issue: GitHubIssue) => void;
  triageLoadingIssue: number | null;
  fixLoadingIssue: number | null;
  loading: boolean;
}

export default function IssueList({
  issues,
  trackedIssues,
  onTriage,
  onFix,
  triageLoadingIssue,
  fixLoadingIssue,
  loading,
}: IssueListProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-xl border border-gray-200 bg-white p-5 animate-pulse"
          >
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-3"></div>
            <div className="h-5 bg-gray-200 rounded w-3/4 mb-2"></div>
            <div className="h-3 bg-gray-100 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  if (issues.length === 0) {
    return (
      <div className="text-center py-12 rounded-xl border border-dashed border-gray-300 bg-gray-50">
        <p className="text-gray-500 text-sm">No issues found.</p>
        <p className="text-gray-400 text-xs mt-1">
          Try a different repository or check your filters.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-700">
          {issues.length} issue{issues.length !== 1 ? "s" : ""}
        </h2>
      </div>
      {issues.map((issue) => {
        const tracked = trackedIssues.get(issue.number);

        return (
          <IssueCard
            key={issue.number}
            issue={issue}
            tracked={tracked}
            onTriage={() => onTriage(issue)}
            onFix={() => onFix(issue)}
            triageLoading={triageLoadingIssue === issue.number}
            fixLoading={fixLoadingIssue === issue.number}
          />
        );
      })}
    </div>
  );
}
