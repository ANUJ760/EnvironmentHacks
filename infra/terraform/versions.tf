terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source = "hashicorp/aws", version = "~> 5.100"
    }
  }
  # Supply bucket/key/region via -backend-config. Never put credentials in state configuration.
  backend "s3" {
    encrypt = true
  }
}
