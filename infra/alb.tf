resource "aws_lb" "main" {
  name               = "${local.name_prefix}-internal-alb"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [for subnet in aws_subnet.private : subnet.id]

  enable_deletion_protection = false

  tags = {
    Name = "${local.name_prefix}-internal-alb"
  }
}

resource "aws_lb_target_group" "backend" {
  name             = "${local.name_prefix}-tg"
  port             = var.backend_container_port
  protocol         = "HTTP"
  vpc_id           = aws_vpc.main.id
  target_type      = "ip"
  protocol_version = "HTTP1"

  health_check {
    enabled             = true
    healthy_threshold   = 5
    interval            = 60
    matcher             = "200"
    path                = "/api/v1/health"
    port                = "traffic-port"
    timeout             = 40
    unhealthy_threshold = 2
  }

  stickiness {
    type            = "app_cookie"
    cookie_name     = "websocket-group10"
    cookie_duration = 86400
    enabled         = true
  }

  deregistration_delay = 300

  tags = {
    Name = "${local.name_prefix}-tg"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = var.backend_container_port
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}
