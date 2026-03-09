export type Difficulty = "easy" | "medium" | "hard";

export interface TriageResult {
  // New structured schema fields
  issue_summary?: string;
  likely_area?: string;
  suspected_files?: string[];
  difficulty?: Difficulty;
  safe_to_autofix?: boolean;
  needs_human_clarification?: boolean;
  acceptance_criteria?: string[];
  recommended_next_step?: string;

  // Backward-compat fields from old schema
  severity?: string;
  category?: string;
  estimated_effort?: string;
  summary?: string;
  suggested_approach?: string;
  can_auto_fix?: boolean;
}

/** Best-effort accessors that handle both old and new schema shapes. */
export function getTriageSummary(tr: TriageResult): string {
  return tr.issue_summary || tr.summary || "";
}

export function getTriageApproach(tr: TriageResult): string {
  return tr.recommended_next_step || tr.suggested_approach || "";
}

export function getTriageAutofix(tr: TriageResult): boolean {
  return tr.safe_to_autofix ?? tr.can_auto_fix ?? false;
}

export function getTriageDifficulty(tr: TriageResult): string {
  return tr.difficulty || tr.estimated_effort || "";
}

export interface TrackedIssue {
  issue_number: number;
  repo: string;
  title: string;
  triage_session_id?: string;
  triage_status?: string;
  triage_result?: TriageResult;
  fix_session_id?: string;
  fix_status?: string;
  pr_url?: string;
  devin_url?: string;
}

export interface GitHubIssue {
  number: number;
  title: string;
  body: string | null;
  state: string;
  labels: Array<{
    id: number;
    name: string;
    color: string;
  }>;
  user: {
    login: string;
    avatar_url: string;
  };
  created_at: string;
  updated_at: string;
  comments: number;
  html_url: string;
}
