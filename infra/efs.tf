resource "aws_efs_file_system" "main" {
  encrypted        = true
  kms_key_id       = aws_kms_key.efs.arn
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  lifecycle_policy {
    transition_to_archive = "AFTER_90_DAYS"
  }

  protection {
    replication_overwrite = "ENABLED"
  }

  tags = {
    Name = "${local.name_prefix}-efs"
  }
}

resource "aws_efs_backup_policy" "main" {
  file_system_id = aws_efs_file_system.main.id

  backup_policy {
    status = "ENABLED"
  }
}

resource "aws_efs_mount_target" "main" {
  for_each = aws_subnet.private

  file_system_id  = aws_efs_file_system.main.id
  subnet_id       = each.value.id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "shared" {
  file_system_id = aws_efs_file_system.main.id

  root_directory {
    path = "/shared"

    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }

  posix_user {
    uid = 1000
    gid = 1000
  }

  tags = {
    Name = "${local.name_prefix}-access-point"
  }
}

resource "aws_efs_access_point" "health_check" {
  file_system_id = aws_efs_file_system.main.id

  root_directory {
    path = "/health-check"
  }

  posix_user {
    uid = 1000
    gid = 1000
  }

  tags = {
    Name = "${local.name_prefix}-lambda-health-check"
  }
}
