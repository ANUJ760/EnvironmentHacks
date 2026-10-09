resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
resource "aws_cloudwatch_log_group" "tasks" {
  for_each          = local.commands
  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = 30
}
resource "aws_ecs_task_definition" "tasks" {
  for_each = var.enable_services ? local.commands : {
  }
  family                   = "${local.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 2048
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task[each.key].arn
  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name                   = each.key, image = var.image_uri, essential = true, user = "10001:10001", command = each.value,
    readonlyRootFilesystem = true,
    portMappings = each.key == "api" ? [{
      containerPort = 8000, protocol = "tcp"
    }] : [],
    environment = [
      {
        name = "APP_ENV", value = "production"
        }, {
        name = "AUTH_MODE", value = "cognito"
      },
      {
        name = "CORS_ALLOWED_ORIGINS", value = var.allowed_cors_origin
      },
      {
        name = "ECOTWIN_STORAGE_MODE", value = "s3"
        }, {
        name = "ECOTWIN_QUEUE_BACKEND", value = "sqs"
      },
      {
        name = "ECOTWIN_S3_BUCKET", value = aws_s3_bucket.data.id
        }, {
        name = "AWS_REGION", value = var.aws_region
      },
      {
        name = "ECOTWIN_SQS_QUEUE_URL", value = aws_sqs_queue.jobs.id
      },
      {
        name = "COGNITO_USER_POOL_ID", value = aws_cognito_user_pool.users.id
      },
      {
        name = "COGNITO_CLIENT_ID", value = aws_cognito_user_pool_client.web.id
      },
      {
        name = "COGNITO_AWS_REGION", value = var.aws_region
      },
      {
        name = "OPENAQ_ENABLED", value = each.key == "ingest" && var.openaq_secret_arn != "" ? "true" : "false"
      },
      {
        name = "ECOTWIN_CACHE_DIR", value = "/tmp/ecotwin-cache"
    }],
    secrets = concat([{
      name = "DATABASE_URL", valueFrom = lookup(var.database_secret_arns, each.key, "")
      }], each.key == "ingest" && var.openaq_secret_arn != "" ? [{
      name = "OPENAQ_API_KEY", valueFrom = var.openaq_secret_arn
    }] : []),
    mountPoints = [{
      sourceVolume = "temporary", containerPath = "/tmp", readOnly = false
    }],
    logConfiguration = {
      logDriver = "awslogs", options = {
        awslogs-group = aws_cloudwatch_log_group.tasks[each.key].name, awslogs-region = var.aws_region, awslogs-stream-prefix = "ecs"
      }
    },
    healthCheck = each.key == "api" ? {
      command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz', timeout=3)\""], interval = 30, timeout = 5, retries = 3, startPeriod = 30
    } : null
  }])
  volume {
    name = "temporary"
  }
  lifecycle {
    precondition {
      condition     = var.image_uri != "" && alltrue([for role in keys(local.commands) : contains(keys(var.database_secret_arns), role)])
      error_message = "Enable services only after image push, database bootstrap, migration, and role-specific Secrets Manager provisioning."
    }
  }
}
resource "aws_ecs_service" "services" {
  for_each                           = local.services
  name                               = "${local.name}-${each.key}"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.tasks[each.key].arn
  desired_count                      = each.value
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.tasks[each.key].id]
    assign_public_ip = false
  }
  dynamic "load_balancer" {
    for_each = each.key == "api" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.api.arn
      container_name   = "api"
      container_port   = 8000
    }
  }
  depends_on = [aws_lb_listener.https]
}
resource "aws_appautoscaling_target" "services" {
  for_each           = local.services
  max_capacity       = each.key == "api" ? 6 : 4
  min_capacity       = each.value
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.services[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}
resource "aws_appautoscaling_policy" "cpu" {
  for_each           = local.services
  name               = "${local.name}-${each.key}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.services[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.services[each.key].scalable_dimension
  service_namespace  = "ecs"
  target_tracking_scaling_policy_configuration {
    target_value = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
