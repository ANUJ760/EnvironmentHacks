resource "aws_security_group" "frontend" {
  name        = "${local.name}-frontend-task"
  description = "Frontend ECS container ingress from ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "frontend" {
  count                    = var.enable_tasks || var.enable_services ? 1 : 0
  family                   = "${local.name}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.frontend.arn
  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }
  lifecycle {
    precondition {
      condition     = var.frontend_image_uri != ""
      error_message = "Supply a separate immutable frontend_image_uri before enabling tasks or services."
    }
  }

  container_definitions = jsonencode([
    {
      name      = "frontend"
      image     = var.frontend_image_uri
      essential = true
      user      = "1001:1001"

      portMappings = [
        {
          containerPort = 3000
          hostPort      = 3000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "APP_ENV", value = "production" },
        { name = "APP_BASE_URL", value = "https://${var.domain_name}" },
        { name = "ECOTWIN_API_INTERNAL_URL", value = "http://api.${aws_service_discovery_private_dns_namespace.internal.name}:8000" },
        { name = "MAP_CACHE_DIR", value = "/tmp/ecotwin-map-cache" },
        { name = "OLLAMA_BASE_URL", value = var.ollama_base_url },
        { name = "OLLAMA_ALLOWED_HOSTS", value = join(",", var.ollama_allowed_hosts) },
        { name = "OLLAMA_MODEL", value = var.ollama_model },
        { name = "NEXT_PUBLIC_APP_LABEL", value = "EcoTwin" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "frontend"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "frontend" {
  count           = var.enable_services ? 1 : 0
  name            = "${local.name}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend[0].arn
  desired_count   = var.environment == "production" ? 2 : 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.app[*].id
    security_groups = [aws_security_group.frontend.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 3000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  depends_on = [aws_lb_listener_rule.frontend, aws_ecs_service.services]
}
