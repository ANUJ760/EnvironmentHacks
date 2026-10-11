resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${local.name}-frontend"
  retention_in_days = var.environment == "production" ? 90 : 14
}

resource "aws_cloudwatch_metric_alarm" "frontend_5xx" {
  alarm_name          = "${local.name}-frontend-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Frontend target group 5xx errors exceeded threshold"

  dimensions = {
    TargetGroup  = aws_lb_target_group.frontend.arn_suffix
    LoadBalancer = aws_lb.api.arn_suffix
  }
}
