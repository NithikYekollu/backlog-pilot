# Triage Schema

## Overview

When Backlog Pilot creates a Devin triage session, it embeds a JSON schema in the prompt and instructs Devin to populate its **structured output** with the result. Devin updates this field progressively as it works, so partial results may be available before the session finishes.

## Schema

```json
{
  "issue_summary": "string — one-sentence summary of the issue",
  "likely_area": "string — area of the codebase most likely affected (e.g. 'authentication', 'API layer')",
  "suspected_files": ["string — file paths Devin thinks are involved"],
  "difficulty": "easy | medium | hard",
  "safe_to_autofix": "boolean — true if Devin can confidently fix this autonomously",
  "needs_human_clarification": "boolean — true if the issue is ambiguous or missing info",
  "acceptance_criteria": ["string — what must be true for this issue to be considered resolved"],
  "recommended_next_step": "string — concrete next action (e.g. 'Patch validation logic in src/auth.ts')"
}
```

## Field Details

| Field | Type | Default | Description |
|---|---|---|---|
| `issue_summary` | string | `""` | One-sentence summary of what the issue is about |
| `likely_area` | string | `""` | Which part of the codebase is most likely affected |
| `suspected_files` | string[] | `[]` | File paths Devin believes are involved |
| `difficulty` | enum | `"medium"` | `easy`, `medium`, or `hard`. Synonyms like `simple`/`low`/`complex`/`high` are auto-mapped |
| `safe_to_autofix` | boolean | `false` | Whether Devin can autonomously fix this without human help |
| `needs_human_clarification` | boolean | `false` | Whether the issue is ambiguous or needs more information |
| `acceptance_criteria` | string[] | `[]` | List of conditions that must hold for the issue to be resolved |
| `recommended_next_step` | string | `""` | Concrete action to take next |

## Defensive Handling

All fields have sensible defaults, so a partial response from Devin still creates a valid `TriageResult` object. The backend:

1. **Filters unknown keys** — Extra fields Devin includes are silently dropped, preventing validation errors.
2. **Coerces difficulty synonyms** — Values like `"simple"`, `"complex"`, `"high"` are mapped to the canonical `easy`/`medium`/`hard` values.
3. **Progressively updates** — The sync endpoint extracts results even while the session is still running. A newer result with more populated fields replaces an older partial one.
4. **Falls back to conversation** — If `structured_output` is empty when the session finishes, the backend parses the last assistant message for JSON.

## Backward Compatibility

The backend model also accepts the old schema fields (`severity`, `category`, `estimated_effort`, `summary`, `suggested_approach`, `can_auto_fix`) so that in-flight sessions created before this schema change still parse. The frontend uses accessor functions (`getTriageSummary`, `getTriageApproach`, etc.) that fall back to old fields when new ones are empty.

## How Structured Output Works

Per the [Devin API docs](https://docs.devin.ai/api-reference/v1/structured-output):

- Include the desired JSON schema directly in the prompt when creating a session.
- Instruct Devin to update structured output immediately and whenever something relevant changes.
- Poll the session to retrieve the `structured_output` field — it updates progressively.
- You cannot force Devin to update, but you can check what it has written so far at any time.

## UI Rendering

The frontend renders each field in the `TriageResultPanel` component:

- **Badges**: difficulty level, likely area, "needs clarification" warning
- **Summary**: one-sentence issue summary
- **Next step**: recommended action
- **Suspected files**: rendered as `<code>` badges
- **Acceptance criteria**: rendered as a bulleted list
- **Auto-fix indicator**: green text if safe to autofix, amber warning if needs clarification
