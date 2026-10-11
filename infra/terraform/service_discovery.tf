resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = "${local.name}.internal"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "api" {
  name = "api"
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.internal.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_iam_role" "frontend" {
  name               = "${local.name}-frontend-task"
  assume_role_policy = aws_iam_role.execution.assume_role_policy
  # No scientific-dataset, queue or database permissions on the public frontend.
}

output "api_internal_url" {
  value = "http://api.${aws_service_discovery_private_dns_namespace.internal.name}:8000"
}
