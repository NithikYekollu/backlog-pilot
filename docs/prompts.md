# Session Prompt Templates

## Triage Prompt

Used when a user clicks **Run Triage** on a GitHub issue. Creates a Devin session that analyzes the issue against the actual repository and returns structured output for human review.

```
You are triaging GitHub issue #{issue_number} from the repository {repo}.

**Issue title:** {title}

**Issue body:**
{body}

---

### Instructions

1. **Restate the issue** — Write a clear one-sentence summary of what the reporter is describing. Do not copy the title verbatim; distill the core problem.

2. **Inspect relevant code** — Clone the repository if needed. Navigate the codebase to identify the components, modules, and files most likely involved. Read the actual source code rather than guessing from file names alone.

3. **Identify likely area and files** — Name the architectural area (e.g. "authentication middleware", "database migration layer", "React component tree") and list specific file paths you inspected.

4. **Estimate difficulty** — Rate as `easy` (isolated change, clear fix), `medium` (touches multiple files or requires careful reasoning), or `hard` (cross-cutting, risky, or poorly understood area).

5. **Assess autonomous fix safety** — Determine whether this issue can be safely fixed without human intervention. Set `safe_to_autofix` to `true` only if: the fix is well-scoped, unlikely to introduce regressions, and you are confident in the approach. When in doubt, set it to `false`.

6. **Flag ambiguity** — If the issue description is vague, missing reproduction steps, or could be interpreted multiple ways, set `needs_human_clarification` to `true`.

7. **Propose acceptance criteria** — List the concrete conditions that must hold for this issue to be considered resolved (e.g. "Login form no longer throws 500 on empty email", "Unit test added for edge case").

8. **Recommend next step** — State the single most useful next action (e.g. "Patch the validation logic in `src/auth/login.ts:45`", "Add a migration to backfill the missing column").

### Structured output

Update your `structured_output` immediately and keep refining it as you analyze. Return **only** these fields:

{{
  "issue_summary": "<one-sentence distillation of the issue>",
  "likely_area": "<architectural area of the codebase>",
  "suspected_files": ["<file paths you inspected and believe are involved>"],
  "difficulty": "<easy|medium|hard>",
  "safe_to_autofix": <true|false>,
  "needs_human_clarification": <true|false>,
  "acceptance_criteria": ["<condition that must hold when resolved>"],
  "recommended_next_step": "<concrete next action>"
}}

Do not include any fields outside this schema. Be concise but specific.
```

---

## Fix Prompt

Used when a user clicks **Approve Fix** on a triaged issue. Creates a Devin session that attempts a safe implementation and opens a pull request.

```
You are fixing GitHub issue #{issue_number} from the repository {repo}.

**Issue title:** {title}

**Issue body:**
{body}

{triage_context}

---

### Instructions

1. **Understand before changing** — Read the issue carefully. If triage context is provided above, use it as a starting point but verify the analysis yourself. Do not blindly trust triage output.

2. **Inspect the code** — Navigate to the suspected files and surrounding code. Understand the existing patterns, conventions, and test coverage before making changes.

3. **Reproduce or reason** — If the issue describes a bug, try to reproduce it or reason through the code path to confirm the root cause. If you cannot reproduce or confirm, surface this as a blocker instead of guessing.

4. **Make the smallest safe fix** — Change only what is necessary. Prefer targeted edits over refactors. Follow existing code style and conventions. Do not introduce new dependencies unless absolutely required.

5. **Run checks** — Run the project's test suite, linter, and type checker if available. Fix any failures your changes introduce. If the project has no tests, note this in your PR description.

6. **Surface blockers** — If you encounter ambiguity that is too high to resolve confidently, **stop and say so** rather than shipping a guess. Explain what you are unsure about and what information would unblock you.

7. **Open a pull request** — Create a PR with:
   - A clear title referencing the issue (e.g. "Fix #42: Prevent 500 on empty email login")
   - A description summarizing what you changed and why
   - A list of files modified

8. **Update structured output** — Keep your `structured_output` updated as you work so the dashboard can show progress:

{{
  "status": "<in_progress|blocked|completed>",
  "current_task": "<what you are doing right now>",
  "files_changed": ["<files you have modified>"],
  "pr_url": "<URL of the pull request once created>"
}}

### Guardrails

- Do NOT force-push, rebase, or amend commits.
- Do NOT modify unrelated files or "clean up" code outside the scope of the issue.
- Do NOT skip tests to make CI pass.
- If the fix requires a database migration, flag it for human review instead of running it.
- If you are less than 80% confident in your fix, set status to "blocked" and explain why.
```

---

## Template Variables

| Variable | Source | Description |
|---|---|---|
| `{issue_number}` | GitHub issue | The issue number (e.g. `42`) |
| `{repo}` | User input | Repository in `owner/repo` format |
| `{title}` | GitHub issue | Issue title |
| `{body}` | GitHub issue | Issue body (markdown) |
| `{triage_context}` | Triage result (fix only) | Formatted triage output injected into fix prompt |

## Design Principles

1. **Concise over verbose** — Devin works better with clear, structured instructions than walls of text.
2. **Verify over assume** — Both prompts instruct Devin to inspect actual code rather than guess.
3. **Safety over speed** — The fix prompt prioritizes surfacing blockers over shipping uncertain changes.
4. **Progressive output** — Both prompts instruct Devin to update `structured_output` as it works, enabling real-time UI updates.
5. **Schema-strict** — The triage prompt explicitly constrains output to 8 fields to keep parsing reliable.
