#!/usr/bin/env bash
set -euo pipefail

# Build a read-only security group check Lambda zip.
# No pip install is needed because boto3 is bundled in the Lambda runtime.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ZIP_NAME="public_security_group_check.zip"

cd "$SCRIPT_DIR"
rm -f "$ZIP_NAME"
zip "$ZIP_NAME" handler.py

echo ""
echo "Created $ZIP_NAME ($(du -h "$ZIP_NAME" | cut -f1))"
echo ""
