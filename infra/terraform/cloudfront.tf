locals {
  listener_arn = var.use_cloudfront ? aws_lb_listener.cloudfront[0].arn : aws_lb_listener.https[0].arn
  public_url   = var.use_cloudfront ? "https://${aws_cloudfront_distribution.app[0].domain_name}" : "https://${var.domain_name}"
  cors_origin  = var.allowed_cors_origin != "" ? var.allowed_cors_origin : local.public_url
}

resource "aws_lb_listener" "cloudfront" {
  count             = var.use_cloudfront ? 1 : 0
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      status_code  = "403"
      message_body = "Access denied"
    }
  }
}

resource "aws_cloudfront_distribution" "app" {
  count       = var.use_cloudfront ? 1 : 0
  enabled     = true
  comment     = "EcoTwin application"
  price_class = "PriceClass_200"
  origin {
    domain_name = aws_lb.api.dns_name
    origin_id   = "ecotwin-alb"
    custom_header {
      name  = "X-EcoTwin-Origin"
      value = var.origin_verify_secret
    }
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
      origin_read_timeout    = 60
    }
  }
  default_cache_behavior {
    target_origin_id         = "ecotwin-alb"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3"
    compress                 = true
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
  lifecycle {
    precondition {
      condition     = length(var.origin_verify_secret) >= 32
      error_message = "CloudFront requires a random origin verification secret of at least 32 characters."
    }
  }
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  count = var.use_cloudfront ? 1 : 0
  name  = "com.amazonaws.global.cloudfront.origin-facing"
}
