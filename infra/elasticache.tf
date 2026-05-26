resource "aws_elasticache_serverless_cache" "redis" {
  name                     = "${local.name_prefix}-redis"
  engine                   = "redis"
  major_engine_version     = "7"
  security_group_ids       = [aws_security_group.redis.id]
  subnet_ids               = [for subnet in aws_subnet.database : subnet.id]
  snapshot_retention_limit = 7
  daily_snapshot_time      = "04:30"
  description              = "${local.name_prefix} Redis cache"

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}
