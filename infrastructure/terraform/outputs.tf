output "alb_dns_name" {
  description = "Public DNS name of the backend ALB"
  value       = aws_lb.api.dns_name
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain serving the SPA"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "frontend_bucket" {
  description = "S3 bucket holding the SPA build"
  value       = aws_s3_bucket.frontend.bucket
}

output "ecr_repository_url" {
  description = "ECR repository for the backend Docker image"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.backend.name
}
