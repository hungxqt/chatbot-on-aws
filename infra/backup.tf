resource "aws_backup_vault" "main" {
  name        = "${local.name_prefix}-vault"
  kms_key_arn = aws_kms_key.backup.arn
}

resource "aws_backup_plan" "main" {
  name = "${local.name_prefix}-backup"

  rule {
    rule_name                    = "DailyBackup"
    target_vault_name            = aws_backup_vault.main.name
    schedule                     = "cron(30 0 ? * * *)"
    schedule_expression_timezone = "Asia/Saigon"
    enable_continuous_backup     = true

    lifecycle {
      delete_after = 35
    }
  }

}

resource "aws_backup_selection" "main" {
  name         = "${local.name_prefix}-backup-resources"
  iam_role_arn = aws_iam_role.backup.arn
  plan_id      = aws_backup_plan.main.id

  resources = [
    "arn:${local.partition}:elasticfilesystem:${local.region}:${local.account_id}:file-system/*",
    "arn:${local.partition}:rds:${local.region}:${local.account_id}:db:${local.name_prefix}-database",
    aws_s3_bucket.app.arn,
    aws_s3_bucket.backend_env.arn,
    aws_s3_bucket.frontend.arn,
    aws_s3_bucket.kb_source.arn,
    aws_s3_bucket.multimedia_kb.arn,
  ]
}
