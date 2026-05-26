# Health Checker Lambda

Standalone AWS Lambda source package for two Lambda functions:

| Lambda | Handler | Purpose |
|--------|---------|---------|
| Health logic | `handler.lambda_handler` | Returns JSON health data |
| Health UI | `dashboard_handler.lambda_handler` | Returns the HTML dashboard |

Both functions can use the same `health_checker.zip` deployment package.

## Checks Performed

| Check | Target | Protocol |
|-------|--------|----------|
| **database** | Aurora PostgreSQL (RDS) | TCP/5432 — `SELECT 1` |
| **redis** | ElastiCache Redis | TCP/6379 — `PING` |
| **bedrock** | AWS Bedrock | boto3 — `list_foundation_models` |
| **bedrock_kb** | Bedrock Knowledge Base | boto3 — `get_knowledge_base` |
| **efs** | EFS mount | Filesystem — write/read/delete test file |
| **main_app** | FastAPI backend (ALB) | HTTP — `GET /api/v1/health` |
| **ecs_services** | ECS cluster services | boto3 — `describe_services` |

## Response Format

```json
{
  "status": "healthy | degraded | unhealthy",
  "timestamp": "2026-05-14T12:00:00+00:00",
  "service": "ai_agent",
  "checks": {
    "database":     { "status": "healthy", "latency_ms": 12, "type": "aurora-postgresql" },
    "redis":        { "status": "healthy", "latency_ms": 3 },
    "bedrock":      { "status": "healthy", "latency_ms": 45, "available_models": 42 },
    "bedrock_kb":   { "status": "healthy", "latency_ms": 30, "kb_status": "ACTIVE" },
    "efs":          { "status": "healthy", "latency_ms": 5 },
    "main_app":     { "status": "healthy", "latency_ms": 120 },
    "ecs_services": { "status": "healthy", "services": { "...": "..." } }
  }
}
```

- `healthy` (200) — all checks pass
- `degraded` (207) — non-critical check failed
- `unhealthy` (503) — critical check (database or redis) failed

## Setup Guide

### Prerequisites

- AWS CLI configured with appropriate credentials
- The existing VPC, subnets, and security groups from `infra/` Terraform
- Secrets in AWS Secrets Manager (already deployed via `infra/secrets.tf`)

### Step 1: Create IAM Role for Lambda

```bash
# Create the execution role
aws iam create-role \
  --role-name ai-agent-health-checker-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic Lambda execution (CloudWatch Logs)
aws iam attach-role-policy \
  --role-name ai-agent-health-checker-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Attach VPC access (ENI management for private subnet)
aws iam attach-role-policy \
  --role-name ai-agent-health-checker-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole

# Create inline policy for Bedrock + ECS + Secrets Manager
aws iam put-role-policy \
  --role-name ai-agent-health-checker-role \
  --policy-name health-checker-services \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "bedrock:ListFoundationModels",
          "bedrock:GetKnowledgeBase"
        ],
        "Resource": "*"
      },
      {
        "Effect": "Allow",
        "Action": ["ecs:ListServices", "ecs:DescribeServices"],
        "Resource": "*"
      },
      {
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue"],
        "Resource": "arn:aws:secretsmanager:*:*:secret:ai-agent-production-secrets*"
      },
      {
        "Effect": "Allow",
        "Action": ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"],
        "Resource": "*"
      }
    ]
  }'
```

### Step 2: Create Security Group for Lambda

The Lambda needs to reach RDS, Redis, and the ALB. Create a security group, then add it as an ingress source to the existing RDS and Redis security groups.

```bash
# Get your VPC ID (from Terraform output or console)
VPC_ID="vpc-xxxxxxxxx"

# Create Lambda security group
LAMBDA_SG=$(aws ec2 create-security-group \
  --group-name ai-agent-health-checker-sg \
  --description "Health checker Lambda" \
  --vpc-id $VPC_ID \
  --query 'GroupId' --output text)

# Allow all outbound (Lambda needs to reach all services)
# (default allows all outbound, so this is already set)

# Allow Lambda to reach RDS (add Lambda SG as ingress to RDS SG)
RDS_SG="sg-xxxxxxxxx"  # your aws_security_group.rds ID
aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG \
  --protocol tcp --port 5432 \
  --source-group $LAMBDA_SG

# Allow Lambda to reach Redis
REDIS_SG="sg-xxxxxxxxx"  # your aws_security_group.redis ID
aws ec2 authorize-security-group-ingress \
  --group-id $REDIS_SG \
  --protocol tcp --port 6379 \
  --source-group $LAMBDA_SG

# Allow Lambda to reach EFS
EFS_SG="sg-xxxxxxxxx"  # your aws_security_group.efs ID
aws ec2 authorize-security-group-ingress \
  --group-id $EFS_SG \
  --protocol tcp --port 2049 \
  --source-group $LAMBDA_SG
```

### Step 3: Build and Deploy the Lambda

```bash
cd lambda/health_checker

# Build the deployment package
chmod +x deploy.sh
./deploy.sh

# Create the Lambda function
aws lambda create-function \
  --function-name ai-agent-health-checker \
  --runtime python3.12 \
  --handler handler.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/ai-agent-health-checker-role \
  --zip-file fileb://health_checker.zip \
  --timeout 30 \
  --memory-size 256 \
  --vpc-config SubnetIds=subnet-PRIVATE1,subnet-PRIVATE2,SecurityGroupIds=$LAMBDA_SG \
  --environment "Variables={
    POSTGRES_HOST=your-aurora-cluster.cluster-xxxx.us-east-1.rds.amazonaws.com,
    POSTGRES_PORT=5432,
    POSTGRES_USER=postgres,
    POSTGRES_PASSWORD=changeme,
    POSTGRES_DB=ai_agent,
    REDIS_HOST=your-redis.xxxx.use1.cache.amazonaws.com,
    REDIS_PORT=6379,
    REDIS_PASSWORD=changeme,
    REDIS_SSL=true,
    AWS_REGION=us-east-1,
    BEDROCK_KNOWLEDGE_BASE_ID=your-kb-id,
    EFS_MOUNT_DIR=/mnt/efs,
    MAIN_APP_HEALTH_URL=http://internal-ai-agent-alb.us-east-1.elb.amazonaws.com:8000/api/v1/health,
    ECS_CLUSTER_NAME=ai-agent-production-cluster
  }"
```

### Step 4: Attach EFS (Optional)

If you want the EFS check to work, configure a Lambda file system:

```bash
# Get the EFS Access Point (or create one)
EFS_ID="fs-xxxxxxxxx"  # your aws_efs_file_system ID

aws efs create-access-point \
  --file-system-id $EFS_ID \
  --posix-user Uid=1000,Gid=1000 \
  --root-directory "Path=/health-check,CreationInfo={OwnerUid=1000,OwnerGid=1000,Permissions=755}"

# Attach to Lambda (use the access point ARN)
aws lambda update-function-configuration \
  --function-name ai-agent-health-checker \
  --file-system-configs "Arn=arn:aws:elasticfilesystem:us-east-1:ACCOUNT_ID:access-point/fsap-xxxxxxxxx,LocalMountPath=/mnt/efs"
```

### Step 5: Create API Gateway

```bash
# Create HTTP API
API_ID=$(aws apigatewayv2 create-api \
  --name ai-agent-health-dashboard \
  --protocol-type HTTP \
  --query 'ApiId' --output text)

# Create Lambda integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:us-east-1:ACCOUNT_ID:function:ai-agent-health-checker \
  --payload-format-version 2.0 \
  --query 'IntegrationId' --output text)

# Create GET /health route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /health" \
  --target "integrations/$INTEGRATION_ID"

# Create default stage with auto-deploy
aws apigatewayv2 create-stage \
  --api-id $API_ID \
  --stage-name '$default' \
  --auto-deploy

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name ai-agent-health-checker \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:ACCOUNT_ID:${API_ID}/*/*"

# Get the invoke URL
aws apigatewayv2 get-api --api-id $API_ID --query 'ApiEndpoint' --output text
```

The health endpoint will be available at: `https://{api-id}.execute-api.us-east-1.amazonaws.com/health`

### Step 6: (Optional) Add CloudWatch Scheduled Check

```bash
# Create a rule that triggers every 5 minutes
aws events put-rule \
  --name ai-agent-health-check-schedule \
  --schedule-expression "rate(5 minutes)"

# Add Lambda as target
aws events put-targets \
  --rule ai-agent-health-check-schedule \
  --targets "Id=health-checker,Arn=arn:aws:lambda:us-east-1:ACCOUNT_ID:function:ai-agent-health-checker"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name ai-agent-health-checker \
  --statement-id eventbridge-invoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/ai-agent-health-check-schedule
```

### Step 7: (Optional) Add CloudWatch Alarm

```bash
# Alarm when health check returns unhealthy (503)
aws cloudwatch put-metric-alarm \
  --alarm-name ai-agent-health-unhealthy \
  --metric-name 5XXError \
  --namespace AWS/ApiGateway \
  --dimensions Name=ApiId,Value=$API_ID \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 3 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:your-alert-topic
```

## Updating the Lambda

```bash
cd lambda/health_checker
./deploy.sh --upload ai-agent-health-checker
```

## Security Notes

- Lambda runs inside the VPC private subnets — no public internet access by default
- Bedrock and ECS API calls require NAT Gateway (already configured in `infra/vpc.tf`)
- Secrets are passed as Lambda environment variables; for production, consider reading from Secrets Manager at runtime
- API Gateway endpoint is public; add IAM auth or API key if this should be internal-only
