resource "aws_iam_role" "ecs_execution" {
  name = "${local.name_prefix}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })

  tags = {
    Name = "${local.name_prefix}-ecs-task-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_env" {
  name = "getEnv"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.backend_env.arn}/.env"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = aws_s3_bucket.backend_env.arn
      },
    ]
  })
}

resource "aws_iam_role_policy" "ecs_execution_parameters" {
  name = "getParameters"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "getSecrets"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = "arn:${local.partition}:secretsmanager:${local.region}:${local.account_id}:secret:${local.name_prefix}/backend/*"
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })

  tags = {
    Name = "${local.name_prefix}-ecs-task-role"
  }
}

resource "aws_iam_role_policy" "ecs_task_bedrock" {
  name = "BedrockAccess"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob",
        ]
        Resource = "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:knowledge-base/*"
      },
    ]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3_knowledge_base" {
  name = "S3KnowledgeBase"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.multimedia_kb.arn,
        "${aws_s3_bucket.multimedia_kb.arn}/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3_app_bucket" {
  name = "S3AppBucket"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
      ]
      Resource = "${aws_s3_bucket.backend.arn}/media/*"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_efs" {
  name = "EFS-Access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "elasticfilesystem:ClientMount",
        "elasticfilesystem:ClientWrite",
        "elasticfilesystem:DescribeMountTargets",
      ]
      Resource = "arn:${local.partition}:elasticfilesystem:${local.region}:${local.account_id}:file-system/*"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_exec" {
  name = "enableEcsExec"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role" "lambda_execution" {
  name = "${local.name_prefix}-lambda-healthcheck-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = {
    Name = "${local.name_prefix}-lambda-healthcheck-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_additional" {
  name = "additionalPermissions"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:ListFoundationModels",
          "bedrock:GetKnowledgeBase",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:ListServices",
          "ecs:DescribeServices",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "elasticfilesystem:ClientMount",
          "elasticfilesystem:ClientWrite",
        ]
        Resource = "arn:${local.partition}:elasticfilesystem:${local.region}:${local.account_id}:file-system/*"
      },
    ]
  })
}

resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
    }]
  })

  tags = {
    Name = "${local.name_prefix}-rds-monitoring-role"
  }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_iam_role" "backup" {
  name = "${local.name_prefix}-backup-service-role"
  path = "/service-role/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "backup.amazonaws.com" }
    }]
  })

  tags = {
    Name = "${local.name_prefix}-backup-service-role"
  }
}

resource "aws_iam_role_policy_attachment" "backup" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AWSBackupServiceRolePolicyForS3Backup",
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup",
    "arn:aws:iam::aws:policy/AWSBackupServiceRolePolicyForS3Restore",
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores",
  ])

  role       = aws_iam_role.backup.name
  policy_arn = each.value
}

resource "aws_iam_role" "vpc_flow_logs" {
  name = "${local.name_prefix}-VPCFlowLogs-CloudWatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = local.account_id
        }
        ArnLike = {
          "aws:SourceArn" = "arn:${local.partition}:ec2:${local.region}:${local.account_id}:vpc-flow-log/*"
        }
      }
    }]
  })

  tags = {
    Name = "${local.name_prefix}-VPCFlowLogs-CloudWatch"
  }
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "FlowLogsPolicy"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Resource = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:*"
    }]
  })
}
