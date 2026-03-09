"use client";

import { useState, useCallback } from "react";
import Header from "@/components/header";
import ConfigBanner from "@/components/config-banner";
import RepoInput from "@/components/repo-input";
import IssueList from "@/components/issue-list";
import { GitHubIssue, TrackedIssue } from "@/lib/types";
import {
  fetchIssues,
  createTriageSession,
  createFixSession,
  syncSession,
} from "@/lib/api";

export default function Home() {
  const [repo, setRepo] = useState("");
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [trackedIssues, setTrackedIssues] = useState<Map<number, TrackedIssue>>(
    new Map()
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triageLoadingIssue, setTriageLoadingIssue] = useState<number | null>(null);
  const [fixLoadingIssue, setFixLoadingIssue] = useState<number | null>(null);
  const [hasApiKeys, setHasApiKeys] = useState(true);

  const handleLoadIssues = useCallback(async (repoName: string) => {
    setRepo(repoName);
    setLoading(true);
    setError(null);
    try {
      const data = await fetchIssues(repoName, {
        state: "open",
        sort: "updated",
        direction: "asc",
        per_page: 30,
      });
      setIssues(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load issues";
      setError(message);
      setIssues([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleTriage = useCallback(
    async (issue: GitHubIssue) => {
      setTriageLoadingIssue(issue.number);
      setError(null);
      try {
        const result = await createTriageSession(
          repo,
          issue.number,
          issue.title,
          issue.body || ""
        );
        setTrackedIssues((prev) => {
          const next = new Map(prev);
          next.set(issue.number, {
            issue_number: issue.number,
            repo,
            title: issue.title,
            triage_session_id: result.session_id,
            triage_status: "running",
            devin_url: result.url,
          });
          return next;
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to start triage";
        if (message.includes("503") || message.includes("DEVIN_API_KEY")) {
          setHasApiKeys(false);
        }
        setError(message);
      } finally {
        setTriageLoadingIssue(null);
      }
    },
    [repo]
  );

  const handleFix = useCallback(
    async (issue: GitHubIssue) => {
      const tracked = trackedIssues.get(issue.number);
      setFixLoadingIssue(issue.number);
      setError(null);
      try {
        const result = await createFixSession(
          repo,
          issue.number,
          issue.title,
          issue.body || "",
          tracked?.triage_result
        );
        setTrackedIssues((prev) => {
          const next = new Map(prev);
          const existing = next.get(issue.number);
          next.set(issue.number, {
            ...existing,
            issue_number: issue.number,
            repo,
            title: issue.title,
            fix_session_id: result.session_id,
            fix_status: "running",
            devin_url: result.url,
          });
          return next;
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to start fix";
        setError(message);
      } finally {
        setFixLoadingIssue(null);
      }
    },
    [repo, trackedIssues]
  );

  const handleSync = useCallback(async (sessionId: string) => {
    setError(null);
    try {
      const result = await syncSession(sessionId);
      if (result.tracked_issue) {
        setTrackedIssues((prev) => {
          const next = new Map(prev);
          next.set(result.tracked_issue!.issue_number, result.tracked_issue!);
          return next;
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to sync session";
      setError(message);
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <ConfigBanner hasApiKeys={hasApiKeys} />

        <div className="mb-8">
          <RepoInput
            onSubmit={handleLoadIssues}
            loading={loading}
            currentRepo={repo}
          />
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {repo && (
          <IssueList
            issues={issues}
            trackedIssues={trackedIssues}
            onTriage={handleTriage}
            onFix={handleFix}
            onSync={handleSync}
            triageLoadingIssue={triageLoadingIssue}
            fixLoadingIssue={fixLoadingIssue}
            loading={loading}
          />
        )}

        {!repo && !loading && (
          <div className="text-center py-16">
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-indigo-50 mb-4">
              <span className="text-2xl">&#128269;</span>
            </div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              Get started
            </h2>
            <p className="text-sm text-gray-500 max-w-md mx-auto">
              Enter a GitHub repository above to load its open issues. Then use
              Devin to triage and fix them automatically.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
