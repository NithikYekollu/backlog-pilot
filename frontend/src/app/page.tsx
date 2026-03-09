/**
 * Main dashboard page for Backlog Pilot.
 *
 * Thin vertical slice: load issues -> run triage -> view results -> approve fix.
 * State is held in React hooks (no external store needed for MVP).
 */
"use client";

import { useState, useCallback, useEffect, useRef } from "react";
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
  const [slackNotifiedIssues, setSlackNotifiedIssues] = useState<Set<number>>(new Set());

  const handleLoadIssues = useCallback(async (repoName: string) => {
    setRepo(repoName);
    setLoading(true);
    setError(null);
    setTrackedIssues(new Map());
    try {
      const data = await fetchIssues(repoName, {
        state: "open",
        sort: "updated",
        direction: "desc",
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
          const existing = next.get(issue.number);
          next.set(issue.number, {
            ...existing,
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

  // -----------------------------------------------------------------------
  // Auto-mark Slack notified when triage completes.
  // Devin's native Slack integration sends DM notifications when session
  // status changes, so we just track which issues have been notified
  // to show the badge in the UI.
  // -----------------------------------------------------------------------
  const prevTrackedRef = useRef<Map<number, TrackedIssue>>(new Map());

  useEffect(() => {
    const prev = prevTrackedRef.current;
    for (const [num, tracked] of Array.from(trackedIssues.entries())) {
      if (slackNotifiedIssues.has(num)) continue;
      const prevTracked = prev.get(num);
      if (tracked.triage_result && (!prevTracked || !prevTracked.triage_result)) {
        // Triage just completed — Devin sends a Slack DM natively.
        // Mark as notified so the badge appears in the UI.
        setSlackNotifiedIssues((prev) => new Set(prev).add(num));
      }
    }
    prevTrackedRef.current = new Map(trackedIssues);
  }, [trackedIssues, slackNotifiedIssues]);

  const handleSync = useCallback(async (sessionId: string) => {
    try {
      const result = await syncSession(sessionId);
      const ti = result.tracked_issue;
      if (ti) {
        setTrackedIssues((prev) => {
          const next = new Map(prev);
          // If the backend returned a recovered session (issue_number=0),
          // find the local issue that owns this session ID and merge.
          if (ti.issue_number === 0) {
            for (const [num, existing] of Array.from(prev.entries())) {
              if (existing.triage_session_id === sessionId || existing.fix_session_id === sessionId) {
                next.set(num, {
                  ...existing,
                  triage_status: ti.triage_status || existing.triage_status,
                  fix_status: ti.fix_status || existing.fix_status,
                  triage_result: ti.triage_result || existing.triage_result,
                  pr_url: ti.pr_url || existing.pr_url,
                });
                return next;
              }
            }
          }
          if (ti.issue_number !== 0) {
            const existing = next.get(ti.issue_number);
            next.set(ti.issue_number, { ...existing, ...ti });
          }
          return next;
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to sync session";
      setError(message);
    }
  }, []);

  // -----------------------------------------------------------------------
  // Auto-polling: refresh every 15s while any session is running
  // -----------------------------------------------------------------------
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Collect session IDs that are in a non-terminal state
    const TERMINAL = new Set(["finished", "failed", "stopped"]);
    const activeSessions: string[] = [];

    for (const t of Array.from(trackedIssues.values())) {
      if (t.triage_session_id && t.triage_status && !TERMINAL.has(t.triage_status) && !t.triage_result) {
        activeSessions.push(t.triage_session_id);
      }
      if (t.fix_session_id && t.fix_status && !TERMINAL.has(t.fix_status) && !t.pr_url) {
        activeSessions.push(t.fix_session_id);
      }
    }

    // Clear any existing timer
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    if (activeSessions.length === 0) return;

    pollTimerRef.current = setInterval(() => {
      activeSessions.forEach((sid) => handleSync(sid));
    }, 15_000);

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [trackedIssues, handleSync]);

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
            repo={repo}
            onTriage={handleTriage}
            onFix={handleFix}
            triageLoadingIssue={triageLoadingIssue}
            fixLoadingIssue={fixLoadingIssue}
            slackNotifiedIssues={slackNotifiedIssues}
            slackLoadingIssue={null}
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
