export type Severity = "critical" | "high" | "medium" | "low";
export type Category = "bug" | "feature" | "refactor" | "docs" | "infra";
export type Effort = "small" | "medium" | "large";

export interface TriageResult {
  severity: Severity;
  category: Category;
  estimated_effort: Effort;
  summary: string;
  suggested_approach: string;
  can_auto_fix: boolean;
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
