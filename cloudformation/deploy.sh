#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# deploy.sh — Deploy webapp-group10 nested CloudFormation stacks
#
# Prerequisites:
#   - AWS CLI v2 configured with appropriate credentials
#   - An S3 bucket to host nested stack templates
#   - An ACM certificate in us-east-1 for your domain
#   - Lambda health check code packaged as a .zip in S3
#
# Usage:
#   ./deploy.sh                          # Deploy with defaults
#   ./deploy.sh --ssl-disabled           # Deploy with RDS SSL disabled
#   ./deploy.sh --with-opensearch        # Deploy with OpenSearch collection
#   ./deploy.sh --no-rollback            # Stop on failure, keep resources for debugging
#   ./deploy.sh --delete                 # Delete the stack
# ============================================================================

# --- Configuration (edit these) ---
STACK_NAME="webapp-group10"
REGION="us-east-1"
TEMPLATES_BUCKET=""           # REQUIRED: S3 bucket for nested templates
TEMPLATES_PREFIX="cloudformation/sections"
ACM_CERTIFICATE_ARN=""        # REQUIRED: ACM cert ARN in us-east-1
LAMBDA_S3_BUCKET=""           # REQUIRED: S3 bucket with Lambda .zip
LAMBDA_S3_KEY=""              # REQUIRED: S3 key for Lambda .zip
DOMAIN_NAME="aws.hungtran.id.vn"
HOSTED_ZONE_ID=""             # Optional: Route 53 hosted zone ID
CONTAINER_IMAGE=""            # Optional: ECR image URI
RDS_MASTER_USERNAME="postgres"  # RDS master username
RDS_MASTER_PASSWORD=""          # REQUIRED: RDS master password (min 8 chars)

# --- Parse flags ---
ENABLE_RDS_SSL="true"
CREATE_OPENSEARCH="false"
DELETE_STACK=false
DISABLE_ROLLBACK=false

for arg in "$@"; do
  case $arg in
    --ssl-disabled)    ENABLE_RDS_SSL="false" ;;
    --with-opensearch) CREATE_OPENSEARCH="true" ;;
    --no-rollback)     DISABLE_ROLLBACK=true ;;
    --delete)          DELETE_STACK=true ;;
    *)                 echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# --- Validate required config ---
if [ "$DELETE_STACK" = false ]; then
  for var in TEMPLATES_BUCKET ACM_CERTIFICATE_ARN LAMBDA_S3_BUCKET LAMBDA_S3_KEY RDS_MASTER_PASSWORD; do
    if [ -z "${!var}" ]; then
      echo "ERROR: $var is not set. Edit deploy.sh and fill in the required values."
      exit 1
    fi
  done
fi

# --- Delete ---
if [ "$DELETE_STACK" = true ]; then
  echo "Deleting stack: $STACK_NAME"
  aws cloudformation delete-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION"
  echo "Waiting for deletion..."
  aws cloudformation wait stack-delete-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"
  echo "Stack deleted."
  exit 0
fi

# --- Upload nested templates to S3 ---
echo "Uploading nested stack templates to s3://${TEMPLATES_BUCKET}/${TEMPLATES_PREFIX}/ ..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for template in network.yaml security.yaml data.yaml bedrock.yaml compute.yaml edge.yaml; do
  aws s3 cp "${SCRIPT_DIR}/sections/${template}" \
    "s3://${TEMPLATES_BUCKET}/${TEMPLATES_PREFIX}/${template}" \
    --region "$REGION"
done
echo "Templates uploaded."

# --- Deploy ---
PARAMS=(
  "ParameterKey=ProjectName,ParameterValue=$STACK_NAME"
  "ParameterKey=RdsMasterUsername,ParameterValue=$RDS_MASTER_USERNAME"
  "ParameterKey=RdsMasterPassword,ParameterValue=$RDS_MASTER_PASSWORD"
  "ParameterKey=EnableRdsSsl,ParameterValue=$ENABLE_RDS_SSL"
  "ParameterKey=CreateOpenSearchCollection,ParameterValue=$CREATE_OPENSEARCH"
  "ParameterKey=DomainName,ParameterValue=$DOMAIN_NAME"
  "ParameterKey=AcmCertificateArn,ParameterValue=$ACM_CERTIFICATE_ARN"
  "ParameterKey=HostedZoneId,ParameterValue=$HOSTED_ZONE_ID"
  "ParameterKey=TemplatesBucketName,ParameterValue=$TEMPLATES_BUCKET"
  "ParameterKey=TemplatesBucketPrefix,ParameterValue=$TEMPLATES_PREFIX"
  "ParameterKey=ContainerImage,ParameterValue=$CONTAINER_IMAGE"
  "ParameterKey=LambdaS3Bucket,ParameterValue=$LAMBDA_S3_BUCKET"
  "ParameterKey=LambdaS3Key,ParameterValue=$LAMBDA_S3_KEY"
)

COMMON_ARGS=(
  --region "$REGION"
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND
  --parameters "${PARAMS[@]}"
  --tags "Key=Project,Value=$STACK_NAME" "Key=ManagedBy,Value=CloudFormation"
)

if [ "$DISABLE_ROLLBACK" = true ]; then
  COMMON_ARGS+=(--disable-rollback)
fi

STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].StackStatus" \
  --output text 2>/dev/null || echo "DOES_NOT_EXIST")

case "$STACK_STATUS" in
  DOES_NOT_EXIST)
    echo "Creating stack: $STACK_NAME"
    aws cloudformation create-stack \
      --stack-name "$STACK_NAME" \
      --template-body "file://${SCRIPT_DIR}/root.yaml" \
      "${COMMON_ARGS[@]}"
    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete \
      --stack-name "$STACK_NAME" \
      --region "$REGION" || true
    ;;
  *ROLLBACK_COMPLETE|*ROLLBACK_FAILED)
    echo "Stack is in $STACK_STATUS state. Deleting before re-creating..."
    aws cloudformation delete-stack \
      --stack-name "$STACK_NAME" \
      --region "$REGION"
    aws cloudformation wait stack-delete-complete \
      --stack-name "$STACK_NAME" \
      --region "$REGION"
    echo "Creating stack: $STACK_NAME"
    aws cloudformation create-stack \
      --stack-name "$STACK_NAME" \
      --template-body "file://${SCRIPT_DIR}/root.yaml" \
      "${COMMON_ARGS[@]}"
    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete \
      --stack-name "$STACK_NAME" \
      --region "$REGION" || true
    ;;
  *CREATE_FAILED|*UPDATE_FAILED)
    echo "Stack is in $STACK_STATUS state. Attempting update..."
    aws cloudformation update-stack \
      --stack-name "$STACK_NAME" \
      --template-body "file://${SCRIPT_DIR}/root.yaml" \
      "${COMMON_ARGS[@]}" || true
    echo "Waiting for stack update..."
    aws cloudformation wait stack-update-complete \
      --stack-name "$STACK_NAME" \
      --region "$REGION" || true
    ;;
  *)
    echo "Updating stack: $STACK_NAME (current status: $STACK_STATUS)"
    aws cloudformation update-stack \
      --stack-name "$STACK_NAME" \
      --template-body "file://${SCRIPT_DIR}/root.yaml" \
      "${COMMON_ARGS[@]}" || true
    echo "Waiting for stack update..."
    aws cloudformation wait stack-update-complete \
      --stack-name "$STACK_NAME" \
      --region "$REGION" || true
    ;;
esac

echo ""
echo "=== Deployment complete ==="
echo ""

# --- Show stack status and outputs ---
FINAL_STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].StackStatus" \
  --output text 2>/dev/null || echo "UNKNOWN")
echo "Stack status: $FINAL_STATUS"

if [[ "$FINAL_STATUS" == *"COMPLETE"* && "$FINAL_STATUS" != *"ROLLBACK"* ]]; then
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
    --output table
fi
