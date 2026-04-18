# PetroLedger — Terraform (AWS)

**Status: SKELETON.** This module sketches the target AWS footprint. It is
structured so future migration is mechanical but is **not** intended for
immediate `apply` without review of IAM scopes, CIDR ranges, and secrets
wiring.

## What it creates

- VPC (10.40.0.0/16) with 2 public + 2 private subnets across 2 AZs
- Internet Gateway + NAT Gateway for private-subnet egress
- Application Load Balancer with HTTP→HTTPS redirect and HTTPS listener
  (requires `acm_certificate_arn`)
- ECS Fargate cluster + service running the backend container
- ECR repository for the backend image
- CloudWatch log group
- S3 bucket + CloudFront distribution for the SPA (private bucket, OAC)
- IAM task execution + task roles
- Optional (commented): RDS Postgres 15 and ElastiCache Redis

## Deploy

```bash
cd infrastructure/terraform

# one-time: create the S3 + DynamoDB backend, then uncomment the backend
# block in main.tf and run `terraform init -reconfigure`.

terraform init
terraform plan \
    -var="acm_certificate_arn=arn:aws:acm:ap-south-1:123456789012:certificate/..." \
    -var="acm_certificate_arn_us_east_1=arn:aws:acm:us-east-1:123456789012:certificate/..." \
    -var="backend_image=123456789012.dkr.ecr.ap-south-1.amazonaws.com/petroledger-prod-backend:v0.1.0"
terraform apply
```

After apply:

1. Push the backend image to the created ECR repo, then update the service.
2. `npm run build` the frontend and `aws s3 sync frontend/dist/ s3://<bucket>/`
3. Create a CloudFront invalidation: `aws cloudfront create-invalidation --distribution-id <id> --paths '/*'`

## Secrets

Never put DB URLs, SECRET_KEY, or SMTP credentials in this module. Store
them in SSM Parameter Store or Secrets Manager; wire them into the ECS
task definition via `secrets` (stub left for follow-up).
