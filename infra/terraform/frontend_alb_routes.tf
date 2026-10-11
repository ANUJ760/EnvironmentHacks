resource "aws_lb_target_group" "frontend" {
  name        = "${substr(local.name, 0, 23)}-fe"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/api/health"
    port                = "3000"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30
}

resource "aws_lb_listener_rule" "frontend" {
  listener_arn = local.listener_arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }
  dynamic "condition" {
    for_each = var.use_cloudfront ? [1] : []
    content {
      http_header {
        http_header_name = "X-EcoTwin-Origin"
        values           = [var.origin_verify_secret]
      }
    }
  }
}

resource "aws_lb_listener_rule" "backend_paths" {
  listener_arn = local.listener_arn
  priority     = 5
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    path_pattern {
      values = ["/v1/*", "/readyz", "/livez"]
    }
  }
  dynamic "condition" {
    for_each = var.use_cloudfront ? [1] : []
    content {
      http_header {
        http_header_name = "X-EcoTwin-Origin"
        values           = [var.origin_verify_secret]
      }
    }
  }
}
