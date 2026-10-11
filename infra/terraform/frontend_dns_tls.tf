# Frontend DNS and TLS integration uses existing ACM certificate and Route53 zone
# when running behind ALB, but can be configured for a distinct frontend sub-domain.
locals {
  frontend_hostname = var.domain_name
}
