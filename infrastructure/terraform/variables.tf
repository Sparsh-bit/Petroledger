variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project" {
  description = "Project name — used to prefix resources"
  type        = string
  default     = "petroledger"
}

variable "acm_certificate_arn" {
  description = "ARN of an ACM certificate in the region for the ALB HTTPS listener"
  type        = string
  default     = ""
}

variable "acm_certificate_arn_us_east_1" {
  description = "ARN of an ACM certificate in us-east-1 for the CloudFront distribution"
  type        = string
  default     = ""
}

variable "backend_image" {
  description = "Full ECR image URI (with tag) of the backend container"
  type        = string
  default     = ""
}

variable "backend_container_port" {
  type    = number
  default = 8000
}

variable "backend_cpu" {
  type    = number
  default = 512
}

variable "backend_memory" {
  type    = number
  default = 1024
}

variable "backend_desired_count" {
  type    = number
  default = 2
}

variable "domain_name" {
  description = "Primary domain (e.g. app.example.com) — optional, used for DNS + CORS wiring"
  type        = string
  default     = ""
}
