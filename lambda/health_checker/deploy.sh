#!/bin/bash
# Build and package the Lambda health checker for deployment.
#
# Usage:
#   ./deploy.sh                     # build zip only
#   ./deploy.sh --upload FUNC_NAME  # build + upload to existing Lambda function
#
# Prerequisites: pip, zip, aws cli (for --upload)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/.build"
ZIP_FILE="$SCRIPT_DIR/health_checker.zip"

echo "==> Cleaning build directory..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "==> Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt" -t "$BUILD_DIR" --quiet --no-cache-dir

echo "==> Copying handlers and assets..."
cp "$SCRIPT_DIR/handler.py" "$BUILD_DIR/"
cp "$SCRIPT_DIR/dashboard_handler.py" "$BUILD_DIR/"
cp "$SCRIPT_DIR/dashboard_html.py" "$BUILD_DIR/"

echo "==> Creating deployment package..."
cd "$BUILD_DIR"
zip -r "$ZIP_FILE" . -q
cd "$SCRIPT_DIR"

SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "==> Package ready: $ZIP_FILE ($SIZE)"

rm -rf "$BUILD_DIR"

if [[ "${1:-}" == "--upload" ]] && [[ -n "${2:-}" ]]; then
    FUNC_NAME="$2"
    echo "==> Uploading to Lambda function: $FUNC_NAME"
    aws lambda update-function-code \
        --function-name "$FUNC_NAME" \
        --zip-file "fileb://$ZIP_FILE" \
        --no-cli-pager
    echo "==> Upload complete."
fi
