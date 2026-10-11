output "frontend_ecr_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "frontend_ecs_service_name" {
  value = try(aws_ecs_service.frontend[0].name, null)
}

output "frontend_task_definition_arn" {
  value = try(aws_ecs_task_definition.frontend[0].arn, null)
}

output "frontend_https_url" {
  value = "https://${var.domain_name}"
}

output "frontend_target_group_arn" {
  value = aws_lb_target_group.frontend.arn
}

output "cognito_frontend_client_id" {
  value = aws_cognito_user_pool_client.web.id
}
