"""
Direct Slack notification via Incoming Webhook.

Posts formatted triage summaries to a Slack channel without relying on
Devin's session-based Slack integration (which cannot post to channels).
"""

import logging
import os

import httpx

logger = logging.getLogger("backlog_pilot.slack")

_TIMEOUT = 10.0


def get_webhook_url() -> str | None:
    """Return the configured Slack webhook URL, or None if not set."""
    return os.environ.get("SLACK_WEBHOOK_URL", "").strip() or None


async def post_triage_summary(
    repo: str,
    issue_number: int,
    title: str,
    summary: str,
    difficulty: str,
    likely_area: str,
    suspected_files: list[str],
    safe_to_autofix: bool,
    recommended_next_step: str,
    dashboard_url: str | None = None,
) -> bool:
    """Post a formatted triage summary to the configured Slack channel.

    Returns True if the message was posted successfully, False otherwise.
    """
    webhook_url = get_webhook_url()
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured — skipping Slack notification")
        return False

    files_str = ", ".join(f"`{f}`" for f in suspected_files) if suspected_files else "none identified"
    autofix_str = "Yes" if safe_to_autofix else "No"
    difficulty_emoji = {"easy": ":large_green_circle:", "medium": ":large_yellow_circle:", "hard": ":red_circle:"}.get(
        difficulty.lower(), ":white_circle:"
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":mag: Triage Complete: {repo}#{issue_number}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Summary:*\n{summary}"},
                {"type": "mrkdwn", "text": f"*Difficulty:* {difficulty_emoji} {difficulty}"},
                {"type": "mrkdwn", "text": f"*Area:* {likely_area}"},
                {"type": "mrkdwn", "text": f"*Safe to autofix:* {autofix_str}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Suspected files:* {files_str}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Next step:* {recommended_next_step}" if recommended_next_step else "*Next step:* —",
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":robot_face: _Triaged by Devin via Backlog Pilot_"
                    + (f"  |  <{dashboard_url}|View Dashboard>" if dashboard_url else ""),
                }
            ],
        },
    ]

    payload = {"blocks": blocks, "text": f"Triage complete for {repo}#{issue_number}: {title}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.is_success:
                logger.info("Slack notification posted for %s#%d", repo, issue_number)
                return True
            else:
                logger.error("Slack webhook returned %d: %s", resp.status_code, resp.text)
                return False
    except httpx.RequestError as exc:
        logger.error("Failed to reach Slack webhook: %s", exc)
        return False
