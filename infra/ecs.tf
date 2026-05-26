locals {
  backend_image = var.container_image != "" ? var.container_image : "${aws_ecr_repository.backend.repository_url}:latest"
}

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-backend"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${local.name_prefix}-backend"
  }
}

resource "aws_cloudwatch_log_group" "ecs_task" {
  name              = "/ecs/${local.name_prefix}-task-definition"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-task-definition"
  }
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-task-definition"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  volume {
    name = "efs-shared"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.main.id
      transit_encryption = "ENABLED"
      root_directory     = "/"

      authorization_config {
        iam             = "ENABLED"
        access_point_id = aws_efs_access_point.shared.id
      }
    }
  }

  container_definitions = jsonencode([{
    name              = "${local.name_prefix}-container"
    essential         = true
    image             = local.backend_image
    cpu               = var.backend_cpu
    memory            = var.backend_memory
    memoryReservation = 3072
    portMappings = [{
      containerPort = var.backend_container_port
      hostPort      = var.backend_container_port
      protocol      = "tcp"
      appProtocol   = "http"
      name          = "${local.name_prefix}-container-port"
    }]
    mountPoints = [{
      sourceVolume  = "efs-shared"
      containerPath = "/mnt/efs/shared"
      readOnly      = false
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs_task.name
        awslogs-region        = local.region
        awslogs-stream-prefix = "ecs"
        awslogs-create-group  = "true"
      }
    }
    environmentFiles = [{
      value = "${aws_s3_bucket.backend_env.arn}/.env"
      type  = "s3"
    }]
    secrets = [
      { name = "API_KEY", valueFrom = aws_secretsmanager_secret.backend_api_key.arn },
      { name = "SECRET_KEY", valueFrom = aws_secretsmanager_secret.backend_secret_key.arn },
      { name = "POSTGRES_HOST", valueFrom = "${aws_secretsmanager_secret.backend_database.arn}:POSTGRES_HOST::" },
      { name = "POSTGRES_PORT", valueFrom = "${aws_secretsmanager_secret.backend_database.arn}:POSTGRES_PORT::" },
      { name = "POSTGRES_USER", valueFrom = "${aws_secretsmanager_secret.backend_database.arn}:POSTGRES_USER::" },
      { name = "POSTGRES_PASSWORD", valueFrom = "${aws_secretsmanager_secret.backend_database.arn}:POSTGRES_PASSWORD::" },
      { name = "POSTGRES_DB", valueFrom = "${aws_secretsmanager_secret.backend_database.arn}:POSTGRES_DB::" },
      { name = "REDIS_HOST", valueFrom = "${aws_secretsmanager_secret.backend_redis.arn}:REDIS_HOST::" },
      { name = "BEDROCK_KNOWLEDGE_BASE_ID", valueFrom = "${aws_secretsmanager_secret.backend_bedrock.arn}:BEDROCK_KNOWLEDGE_BASE_ID::" },
      { name = "BEDROCK_KB_DATA_SOURCE_ID", valueFrom = "${aws_secretsmanager_secret.backend_bedrock.arn}:BEDROCK_KB_DATA_SOURCE_ID::" },
      { name = "BEDROCK_KB_S3_BUCKET", valueFrom = "${aws_secretsmanager_secret.backend_bedrock.arn}:BEDROCK_KB_S3_BUCKET::" },
      { name = "BEDROCK_KB_S3_PREFIX", valueFrom = "${aws_secretsmanager_secret.backend_bedrock.arn}:BEDROCK_KB_S3_PREFIX::" },
    ]
    environment = [
      { name = "ENVIRONMENT", value = "production" },
      { name = "DEBUG", value = "false" },
      { name = "PROJECT_NAME", value = "ChatGPT" },
      { name = "REDIS_SSL", value = "true" },
      { name = "REDIS_ENABLED", value = "true" },
      { name = "AI_MODEL", value = "global.anthropic.claude-sonnet-4-6" },
      { name = "AI_TEMPERATURE", value = "0.7" },
      { name = "AI_AVAILABLE_MODELS", value = jsonencode(["global.anthropic.claude-opus-4-6-v1", "global.anthropic.claude-sonnet-4-5-20250929-v1:0", "global.anthropic.claude-opus-4-5-20251101-v1:0"]) },
      { name = "ACCESS_TOKEN_EXPIRE_MINUTES", value = "10080" },
      { name = "ALGORITHM", value = "HS256" },
      { name = "TIMEZONE", value = "UTC" },
      { name = "AWS_REGION", value = local.region },
      { name = "S3_MEDIA_BUCKET", value = aws_s3_bucket.backend.id },
      { name = "S3_MEDIA_PREFIX", value = "media" },
      { name = "S3_MEDIA_REGION", value = local.region },
    ]
  }])
}

resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-task-definition-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    base              = 0
    weight            = 1
  }

  availability_zone_rebalancing = "ENABLED"
  platform_version              = "LATEST"
  enable_execute_command        = false
  enable_ecs_managed_tags       = true

  network_configuration {
    subnets          = [for subnet in aws_subnet.private : subnet.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "${local.name_prefix}-container"
    container_port   = var.backend_container_port
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_controller {
    type = "ECS"
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  depends_on = [aws_lb_listener.http]
}
