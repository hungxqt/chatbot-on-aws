"""HTML dashboard Lambda handler for the ai_agent health UI."""

from dashboard_html import DASHBOARD_HTML


def lambda_handler(event, context):
    """Return the static health dashboard HTML."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-cache, no-store",
        },
        "body": DASHBOARD_HTML,
    }
