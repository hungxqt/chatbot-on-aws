locals {
  kms_root_principal = "arn:${local.partition}:iam::${local.account_id}:root"
}

resource "aws_kms_key" "rds" {
  description         = "Encrypts RDS database volumes"
  enable_key_rotation = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowRootAccess"
        Effect    = "Allow"
        Principal = { AWS = local.kms_root_principal }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowRdsService"
        Effect    = "Allow"
        Principal = { AWS = "*" }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:ListGrants",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = local.account_id
            "kms:ViaService"    = "rds.${local.region}.amazonaws.com"
          }
        }
      },
    ]
  })

  tags = {
    Name = "${local.name_prefix}-kms-rds"
  }
}

resource "aws_kms_key" "efs" {
  description         = "Encrypts EFS filesystems"
  enable_key_rotation = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowRootAccess"
        Effect    = "Allow"
        Principal = { AWS = local.kms_root_principal }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowEfsService"
        Effect    = "Allow"
        Principal = { AWS = "*" }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:ListGrants",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = local.account_id
            "kms:ViaService"    = "elasticfilesystem.${local.region}.amazonaws.com"
          }
        }
      },
    ]
  })

  tags = {
    Name = "${local.name_prefix}-kms-efs"
  }
}

resource "aws_kms_key" "backup" {
  description         = "Encrypts Backup vault"
  enable_key_rotation = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowRootAccess"
        Effect    = "Allow"
        Principal = { AWS = local.kms_root_principal }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowBackupService"
        Effect    = "Allow"
        Principal = { AWS = "*" }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:ListGrants",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = local.account_id
            "kms:ViaService"    = "backup.${local.region}.amazonaws.com"
          }
        }
      },
    ]
  })

  tags = {
    Name = "${local.name_prefix}-kms-backup"
  }
}
