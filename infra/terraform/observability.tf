resource "aws_cloudwatch_metric_alarm" "queue" {
  for_each = {
    age = {
      name = "ApproximateAgeOfOldestMessage", threshold = 300, queue = aws_sqs_queue.jobs.name
      }, backlog = {
      name = "ApproximateNumberOfMessagesVisible", threshold = 100, queue = aws_sqs_queue.jobs.name
      }, dead = {
      name = "ApproximateNumberOfMessagesVisible", threshold = 0, queue = aws_sqs_queue.dead.name
    }
  }
  alarm_name          = "${local.name}-${each.key}"
  namespace           = "AWS/SQS"
  metric_name         = each.value.name
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = each.value.threshold
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    QueueName = each.value.queue
  }
}
resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${local.name}-api-errors"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
  }
}
resource "aws_cloudwatch_metric_alarm" "unhealthy" {
  alarm_name          = "${local.name}-api-unhealthy"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix, TargetGroup = aws_lb_target_group.api.arn_suffix
  }
}
resource "aws_budgets_budget" "monthly" {
  count        = var.budget_email != "" ? 1 : 0
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
resource "aws_iam_role" "scheduler" {
  name = "${local.name}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Principal = {
        Service = "scheduler.amazonaws.com"
      }, Action = "sts:AssumeRole"
    }]
    }
  )
}
resource "aws_iam_role_policy" "scheduler" {
  count = var.enable_services ? 1 : 0
  role  = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Action = ["ecs:RunTask"], Resource = [aws_ecs_task_definition.tasks["ingest"].arn]
      }, {
      Effect = "Allow", Action = ["iam:PassRole"], Resource = [aws_iam_role.task["ingest"].arn, aws_iam_role.execution.arn]
    }]
    }
  )
}
resource "aws_scheduler_schedule" "weather" {
  count               = var.enable_services && var.ingest_city_slug != "" ? 1 : 0
  name                = "${local.name}-weather"
  schedule_expression = "rate(3 hours)"
  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn
    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.tasks["ingest"].arn
      launch_type         = "FARGATE"
      network_configuration {
        subnets          = aws_subnet.app[*].id
        security_groups  = [aws_security_group.tasks["ingest"].id]
        assign_public_ip = false
      }
    }
    input = jsonencode({
      containerOverrides = [{
        name = "ingest", command = ["ecotwin", "ingest", "weather", "--city", var.ingest_city_slug]
      }]
      }
    )
  }
}

resource "aws_cloudwatch_log_metric_filter" "job_failures" {
  name           = "${local.name}-job-failures"
  log_group_name = aws_cloudwatch_log_group.tasks["worker"].name
  pattern        = "{ $.event = \"simulation_job_completed\" && $.state = \"FAILED\" }"
  metric_transformation {
    name          = "SimulationFailures"
    namespace     = "EcoTwin"
    value         = "1"
    default_value = 0
  }
}
resource "aws_cloudwatch_log_metric_filter" "ingest_failures" {
  name           = "${local.name}-ingest-failures"
  log_group_name = aws_cloudwatch_log_group.tasks["ingest"].name
  pattern        = "{ $.event = \"ingest_failed\" }"
  metric_transformation {
    name          = "IngestionFailures"
    namespace     = "EcoTwin"
    value         = "1"
    default_value = 0
  }
}
resource "aws_cloudwatch_metric_alarm" "application_failures" {
  for_each            = toset(["SimulationFailures", "IngestionFailures"])
  alarm_name          = "${local.name}-${each.key}"
  namespace           = "EcoTwin"
  metric_name         = each.key
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
