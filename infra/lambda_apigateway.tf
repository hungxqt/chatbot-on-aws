resource "aws_cloudwatch_log_group" "lambda_health_check" {
  name              = "/aws/lambda/${local.name_prefix}-lambda-healthCheck"
  retention_in_days = 30
}

resource "aws_lambda_function" "health_check" {
  function_name = "${local.name_prefix}-lambda-healthCheck"
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  memory_size   = 512
  timeout       = 90
  architectures = ["x86_64"]
  role          = aws_iam_role.lambda_execution.arn
  publish       = true

  s3_bucket = var.lambda_s3_bucket
  s3_key    = var.lambda_s3_key

  vpc_config {
    security_group_ids = [aws_security_group.lambda.id]
    subnet_ids         = [for subnet in aws_subnet.private : subnet.id]
  }

  file_system_config {
    arn              = aws_efs_access_point.health_check.arn
    local_mount_path = "/mnt/efs"
  }

  environment {
    variables = {
      POSTGRES_USER             = var.rds_master_username
      POSTGRES_HOST             = aws_db_instance.main.address
      POSTGRES_PORT             = tostring(aws_db_instance.main.port)
      POSTGRES_DB               = var.db_name
      POSTGRES_PASSWORD         = ""
      REDIS_HOST                = aws_elasticache_serverless_cache.redis.endpoint[0].address
      REDIS_PORT                = tostring(aws_elasticache_serverless_cache.redis.endpoint[0].port)
      REDIS_SSL                 = "true"
      REDIS_PASSWORD            = ""
      ECS_CLUSTER_NAME          = aws_ecs_cluster.main.name
      EFS_MOUNT_DIR             = "/mnt/efs"
      BEDROCK_KNOWLEDGE_BASE_ID = var.create_opensearch_collection ? aws_bedrockagent_knowledge_base.main[0].id : ""
      MAIN_APP_HEALTH_URL       = var.health_check_url != "" ? var.health_check_url : "http://${aws_lb.main.dns_name}:${var.backend_container_port}/api/v1/health"
    }
  }

  ephemeral_storage {
    size = 1024
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda_health_check.name
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_health_check,
    aws_efs_mount_target.main,
  ]
}

resource "aws_lambda_alias" "health_check" {
  name             = "health-check-production"
  function_name    = aws_lambda_function.health_check.function_name
  function_version = aws_lambda_function.health_check.version
}

resource "aws_lambda_provisioned_concurrency_config" "health_check" {
  function_name                     = aws_lambda_function.health_check.function_name
  provisioned_concurrent_executions = 2
  qualifier                         = aws_lambda_alias.health_check.name
}

resource "aws_api_gateway_rest_api" "health" {
  name = "${local.name_prefix}-api-gateway"

  api_key_source = "HEADER"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.health.id
  parent_id   = aws_api_gateway_rest_api.health.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_resource" "health_check" {
  rest_api_id = aws_api_gateway_rest_api.health.id
  parent_id   = aws_api_gateway_rest_api.health.root_resource_id
  path_part   = "health-check"
}

resource "aws_api_gateway_method" "health_check_get" {
  rest_api_id      = aws_api_gateway_rest_api.health.id
  resource_id      = aws_api_gateway_resource.health_check.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "health_check_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.health.id
  resource_id             = aws_api_gateway_resource.health_check.id
  http_method             = aws_api_gateway_method.health_check_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_alias.health_check.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health_check.function_name
  qualifier     = aws_lambda_alias.health_check.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.health.execution_arn}/*"
}

resource "aws_api_gateway_deployment" "health" {
  rest_api_id = aws_api_gateway_rest_api.health.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.health_check.id,
      aws_api_gateway_method.health_check_get.id,
      aws_api_gateway_integration.health_check_lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "v1" {
  rest_api_id   = aws_api_gateway_rest_api.health.id
  deployment_id = aws_api_gateway_deployment.health.id
  stage_name    = "v1"
}

resource "aws_api_gateway_api_key" "health" {
  name    = "${local.name_prefix}-api-key"
  enabled = true
}

resource "aws_api_gateway_usage_plan" "health" {
  name = "${local.name_prefix}-health-check-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.health.id
    stage  = aws_api_gateway_stage.v1.stage_name
  }

  quota_settings {
    limit  = 5000
    period = "DAY"
  }

  throttle_settings {
    burst_limit = 60
    rate_limit  = 20
  }
}

resource "aws_api_gateway_usage_plan_key" "health" {
  key_id        = aws_api_gateway_api_key.health.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.health.id
}
