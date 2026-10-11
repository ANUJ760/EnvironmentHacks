resource "aws_ecr_repository" "backend" {
  name                 = "ecotwin-backend"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1, description = "retain twenty releases", selection = {
        tagStatus = "any", countType = "imageCountMoreThan", countNumber = 20
        }, action = {
        type = "expire"
      }
    }]
    }
  )
}
resource "aws_s3_bucket" "data" {
  bucket_prefix = "${local.name}-data-"
}
resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  bucket = aws_s3_bucket.data.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"], Condition = {
        Bool = {
          "aws:SecureTransport" = "false"
        }
      }
    }]
    }
  )
}
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "temporary-cache"
    status = "Enabled"
    filter {
      prefix = "ecotwin/cache/"
    }
    expiration {
      days = 7
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}
