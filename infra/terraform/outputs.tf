output "aws_region" { value = var.aws_region }
output "ecr_repository_url" { value = aws_ecr_repository.backend.repository_url }
output "ecs_cluster_name" { value = aws_ecs_cluster.main.name }
output "api_service_name" { value = try(aws_ecs_service.services["api"].name, null) }
output "worker_service_name" { value = try(aws_ecs_service.services["worker"].name, null) }
output "api_task_definition_arn" { value = try(aws_ecs_task_definition.tasks["api"].arn, null) }
output "worker_task_definition_arn" { value = try(aws_ecs_task_definition.tasks["worker"].arn, null) }
output "ingest_task_definition_arn" { value = try(aws_ecs_task_definition.tasks["ingest"].arn, null) }
output "migration_task_definition_arn" { value = try(aws_ecs_task_definition.tasks["migrate"].arn, null) }
output "s3_bucket_name" { value = aws_s3_bucket.data.id }
output "sqs_queue_url" { value = aws_sqs_queue.jobs.id }
output "rds_endpoint" { value = aws_db_instance.main.endpoint }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.users.id }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
output "api_https_url" { value = "https://${var.domain_name}" }
output "runtime_secret_arns" { value = {for role, secret in aws_secretsmanager_secret.runtime : role => secret.arn} }
output "private_subnet_ids" { value = aws_subnet.app[*].id }
output "migration_security_group_id" { value = aws_security_group.tasks["migrate"].id }
