provider "aws" {
  region = var.aws_region
  default_tags { tags = { project = "ecotwin", env = var.environment, owner = var.owner } }
}
data "aws_availability_zones" "available" { state = "available" }
data "aws_caller_identity" "current" {}
locals {
  name = "ecotwin-${var.environment}"
  services = var.enable_services ? { api = 2, worker = 1 } : {}
  commands = {
    api = ["uvicorn", "ecotwin.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    worker = ["ecotwin", "jobs", "work"]
    ingest = ["ecotwin", "--help"]
    migrate = ["alembic", "upgrade", "head"]
  }
}
