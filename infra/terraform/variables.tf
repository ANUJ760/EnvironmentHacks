variable "aws_region" {
  type    = string
  default = "ap-south-1"
}
variable "environment" {
  type    = string
  default = "staging"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Use staging or production."
  }
}
variable "owner" {
  type = string
}
variable "domain_name" {
  type = string
  validation {
    condition     = length(var.domain_name) > 3
    error_message = "An operator-owned TLS hostname is required."
  }
}
variable "zone_id" {
  type = string
}
variable "allowed_cors_origin" {
  type = string
  validation {
    condition     = startswith(var.allowed_cors_origin, "https://")
    error_message = "HTTPS CORS origin required."
  }
}
variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}
variable "budget_email" {
  type    = string
  default = ""
}
variable "monthly_budget_usd" {
  type    = number
  default = 150
}
variable "enable_services" {
  type    = bool
  default = false
}
variable "image_uri" {
  type    = string
  default = ""
  validation {
    condition     = var.image_uri == "" || can(regex("@sha256:[a-f0-9]{64}$", var.image_uri))
    error_message = "Service image must use an immutable ECR digest."
  }
}

variable "frontend_image_uri" {
  type        = string
  default     = ""
  description = "Separate standalone Next.js ECR image, not the backend image."
  validation {
    condition     = var.frontend_image_uri == "" || can(regex("@sha256:[a-f0-9]{64}$", var.frontend_image_uri))
    error_message = "Frontend image must use an immutable ECR digest."
  }
}
variable "database_secret_arns" {
  type = map(string)
  default = {
  }
  description = "Secrets Manager ARNs containing role-specific full DATABASE_URL strings; provision after RDS bootstrap."
}
variable "openaq_secret_arn" {
  type    = string
  default = ""
}
variable "ingest_city_slug" {
  type    = string
  default = ""
}

variable "enable_tasks" {
  type    = bool
  default = false
}

variable "ollama_base_url" {
  type        = string
  default     = "http://localhost:11434"
  description = "Optional operator-managed internal Ollama endpoint; no service is provisioned."
  validation {
    condition     = can(regex("^https?://[A-Za-z0-9.-]+(:[0-9]+)?/?$", var.ollama_base_url))
    error_message = "Use an HTTP(S) origin without credentials, paths or query strings."
  }
}
variable "ollama_allowed_hosts" {
  type        = list(string)
  default     = []
  description = "Explicit additional trusted internal inference hostnames; never browser-controlled."
  validation {
    condition     = alltrue([for host in var.ollama_allowed_hosts : can(regex("^[A-Za-z0-9.-]+$", host))])
    error_message = "Allowlist entries must be hostnames, not URLs."
  }
}
variable "ollama_model" {
  type    = string
  default = "qwen2.5:1.5b"
}
