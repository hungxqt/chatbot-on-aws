#!/usr/bin/env bash
set -euo pipefail

# Zero-dependency health checker — just zip the Python files.
# No pip install, no docker build, no C extensions.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ZIP_NAME="health_checker_lite.zip"

cd "$SCRIPT_DIR"
rm -f "$ZIP_NAME"
zip "$ZIP_NAME" handler.py dashboard_html.py

echo ""
echo "Created $ZIP_NAME ($(du -h "$ZIP_NAME" | cut -f1))"
echo ""

if [[ "${1:-}" == "--upload" ]]; then
    FUNCTION_NAME="${2:-ai-agent-health-checker}"
    echo "Uploading to Lambda function: $FUNCTION_NAME"
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_NAME"
    echo "Done."
fi
