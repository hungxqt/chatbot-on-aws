resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Security group for ${local.name_prefix} internal ALB"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-alb-sg"
  }
}

resource "aws_security_group_rule" "alb_ingress_from_ecs" {
  type                     = "ingress"
  description              = "Allow TCP 8000 from ECS tasks"
  from_port                = var.backend_container_port
  to_port                  = var.backend_container_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.alb.id
  source_security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group" "ecs" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "Security group for ${local.name_prefix} ECS tasks"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-ecs-sg"
  }
}

resource "aws_security_group_rule" "ecs_ingress_from_alb" {
  type                     = "ingress"
  description              = "Allow TCP 8000 from ALB"
  from_port                = var.backend_container_port
  to_port                  = var.backend_container_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs.id
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "Security group for ${local.name_prefix} RDS database"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow TCP 5432 from ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  ingress {
    description     = "Allow TCP 5432 from Lambda functions"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-rds-sg"
  }
}

resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Security group for ${local.name_prefix} Redis cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow TCP 6379 from ECS tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-redis-sg"
  }
}

resource "aws_security_group" "efs" {
  name        = "${local.name_prefix}-efs-sg"
  description = "Security group for ${local.name_prefix} EFS filesystem"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow NFS from ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  ingress {
    description     = "Allow NFS from Lambda functions"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-efs-sg"
  }
}

resource "aws_security_group" "lambda" {
  name        = "${local.name_prefix}-lambda-sg"
  description = "Security group for ${local.name_prefix} Lambda functions"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-lambda-sg"
  }
}
