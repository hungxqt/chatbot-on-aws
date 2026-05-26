resource "aws_secretsmanager_secret" "backend_secret_key" {
  name                    = "${local.name_prefix}/backend/SECRET_KEY"
  description             = "Backend SECRET_KEY for ${local.name_prefix}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "backend_secret_key" {
  secret_id = aws_secretsmanager_secret.backend_secret_key.id

  secret_string = random_password.backend_secret_key.result
}

resource "random_password" "backend_secret_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "backend_api_key" {
  name                    = "${local.name_prefix}/backend/API_KEY"
  description             = "Backend API_KEY for ${local.name_prefix}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "backend_api_key" {
  secret_id = aws_secretsmanager_secret.backend_api_key.id

  secret_string = random_password.backend_api_key.result
}

resource "random_password" "backend_api_key" {
  length  = 40
  special = false
}

resource "aws_secretsmanager_secret" "backend_database" {
  name                    = "${local.name_prefix}/backend/database"
  description             = "Database credentials placeholder for ${local.name_prefix}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "backend_database" {
  secret_id = aws_secretsmanager_secret.backend_database.id

  secret_string = jsonencode({
    POSTGRES_HOST     = aws_db_instance.main.address
    POSTGRES_PORT     = tostring(aws_db_instance.main.port)
    POSTGRES_USER     = var.rds_master_username
    POSTGRES_PASSWORD = var.rds_master_password
    POSTGRES_DB       = var.db_name
  })
}

resource "aws_secretsmanager_secret" "backend_redis" {
  name                    = "${local.name_prefix}/backend/redis"
  description             = "Redis credentials placeholder for ${local.name_prefix}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "backend_redis" {
  secret_id = aws_secretsmanager_secret.backend_redis.id

  secret_string = jsonencode({
    REDIS_HOST = aws_elasticache_serverless_cache.redis.endpoint[0].address
    REDIS_PORT = tostring(aws_elasticache_serverless_cache.redis.endpoint[0].port)
  })
}

resource "aws_secretsmanager_secret" "backend_bedrock" {
  name                    = "${local.name_prefix}/backend/bedrock"
  description             = "Bedrock configuration placeholder for ${local.name_prefix}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "backend_bedrock" {
  secret_id = aws_secretsmanager_secret.backend_bedrock.id

  secret_string = jsonencode({
    BEDROCK_KNOWLEDGE_BASE_ID = var.create_opensearch_collection ? aws_bedrockagent_knowledge_base.main[0].id : ""
    BEDROCK_KB_DATA_SOURCE_ID = var.create_opensearch_collection ? aws_bedrockagent_data_source.main[0].data_source_id : ""
    BEDROCK_KB_S3_BUCKET      = aws_s3_bucket.multimedia_kb.id
    BEDROCK_KB_S3_PREFIX      = "rag-documents/"
  })
}

resource "aws_secretsmanager_secret" "backend_auth_secret" {
  name                    = "${local.name_prefix}/backend/AUTH_SECRET"
  description             = "Backend AUTH_SECRET for ${local.name_prefix}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "backend_auth_secret" {
  secret_id = aws_secretsmanager_secret.backend_auth_secret.id

  secret_string = random_password.backend_auth_secret.result
}

resource "random_password" "backend_auth_secret" {
  length  = 64
  special = true
}

resource "aws_secretsmanager_secret" "backend_jwks_key" {
  name                    = "${local.name_prefix}/backend/JWKS_KEY"
  description             = "JWKS key placeholder for ${local.name_prefix}"
  recovery_window_in_days = 7
}
