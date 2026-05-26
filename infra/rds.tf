resource "aws_db_subnet_group" "main" {
  name        = "${local.name_prefix}-rds-subnet-group"
  description = "Subnet group for ${local.name_prefix} RDS instances"
  subnet_ids  = [for subnet in aws_subnet.database : subnet.id]

  tags = {
    Name = "${local.name_prefix}-rds-subnet-group"
  }
}

resource "aws_db_parameter_group" "postgres_ssl_enabled" {
  name        = "${local.name_prefix}-pg18-ssl-enabled"
  family      = "postgres18"
  description = "${local.name_prefix} PostgreSQL 18 parameter group with SSL enabled"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = {
    Name = "${local.name_prefix}-pg18-ssl-enabled"
  }
}

resource "aws_db_parameter_group" "postgres_ssl_disabled" {
  name        = "${local.name_prefix}-pg18-ssl-disabled"
  family      = "postgres18"
  description = "${local.name_prefix} PostgreSQL 18 parameter group with SSL disabled"

  parameter {
    name  = "rds.force_ssl"
    value = "0"
  }

  tags = {
    Name = "${local.name_prefix}-pg18-ssl-disabled"
  }
}

resource "aws_db_instance" "main" {
  identifier                            = "${local.name_prefix}-database"
  engine                                = "postgres"
  engine_version                        = "18.3"
  instance_class                        = "db.m7g.large"
  allocated_storage                     = 100
  max_allocated_storage                 = 1000
  storage_type                          = "io2"
  iops                                  = 3000
  multi_az                              = true
  username                              = var.rds_master_username
  password                              = var.rds_master_password
  db_subnet_group_name                  = aws_db_subnet_group.main.name
  vpc_security_group_ids                = [aws_security_group.rds.id]
  parameter_group_name                  = var.enable_rds_ssl ? aws_db_parameter_group.postgres_ssl_enabled.name : aws_db_parameter_group.postgres_ssl_disabled.name
  storage_encrypted                     = true
  kms_key_id                            = aws_kms_key.rds.arn
  deletion_protection                   = false
  backup_retention_period               = 35
  backup_window                         = "03:17-05:17"
  monitoring_interval                   = 1
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn
  performance_insights_enabled          = true
  performance_insights_retention_period = 465
  performance_insights_kms_key_id       = aws_kms_key.rds.arn
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]
  copy_tags_to_snapshot                 = true
  auto_minor_version_upgrade            = false
  port                                  = 5432
  db_name                               = var.db_name
  network_type                          = "IPV4"
  publicly_accessible                   = false
  skip_final_snapshot                   = true

  tags = {
    Name = "${local.name_prefix}-database"
  }
}
