/**
 * API client for the Backlog Pilot backend.
 *
 * TODO: Update NEXT_PUBLIC_API_URL in frontend/.env.local if the backend
 *       is deployed to a different host.
 */

import { GitHubIssue, TrackedIssue, TriageResult } from "./types";

// TODO: For production, set NEXT_PUBLIC_API_URL to the deployed backend URL.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`API error ${res.status}: ${errorBody}`);
  }

  return res.json();
}

// GitHub endpoints
export async function fetchIssues(
  repo: string,
  options?: {
    state?: string;
    sort?: string;
    direction?: string;
    per_page?: number;
    page?: number;
    labels?: string;
  }
): Promise<GitHubIssue[]> {
  const params = new URLSearchParams({ repo });
  if (options?.state) params.set("state", options.state);
  if (options?.sort) params.set("sort", options.sort);
  if (options?.direction) params.set("direction", options.direction);
  if (options?.per_page) params.set("per_page", String(options.per_page));
  if (options?.page) params.set("page", String(options.page));
  if (options?.labels) params.set("labels", options.labels);

  return apiFetch<GitHubIssue[]>(`/api/github/issues?${params}`);
}

// ---------------------------------------------------------------------------
// Devin endpoints
// TODO: These endpoints require DEVIN_API_KEY to be set in backend/.env.
//       Without it, triage and fix calls will return 503.
// ---------------------------------------------------------------------------

export async function createTriageSession(
  repo: string,
  issueNumber: number,
  title: string,
  body: string
): Promise<{ session_id: string; url: string; status: string }> {
  return apiFetch("/api/devin/triage", {
    method: "POST",
    body: JSON.stringify({
      repo,
      issue_number: issueNumber,
      title,
      body,
    }),
  });
}

export async function createFixSession(
  repo: string,
  issueNumber: number,
  title: string,
  body: string,
  triageResult?: TriageResult
): Promise<{ session_id: string; url: string; status: string }> {
  return apiFetch("/api/devin/fix", {
    method: "POST",
    body: JSON.stringify({
      repo,
      issue_number: issueNumber,
      title,
      body,
      triage_result: triageResult,
    }),
  });
}

export async function syncSession(
  sessionId: string
): Promise<{
  status: string;
  tracked_issue?: TrackedIssue;
  session_data?: Record<string, unknown>;
}> {
  return apiFetch(`/api/devin/sessions/${sessionId}/sync`, {
    method: "POST",
  });
}

export async function getSessionStatus(
  sessionId: string
): Promise<Record<string, unknown>> {
  return apiFetch(`/api/devin/sessions/${sessionId}`);
}

export async function sendSessionMessage(
  sessionId: string,
  message: string
): Promise<Record<string, unknown>> {
  return apiFetch(`/api/devin/sessions/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function getTrackedIssues(): Promise<TrackedIssue[]> {
  return apiFetch("/api/devin/tracked");
}
