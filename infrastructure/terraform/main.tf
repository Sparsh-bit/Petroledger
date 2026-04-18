terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — uncomment after bootstrapping an S3 bucket + DynamoDB table.
  # backend "s3" {
  #   bucket         = "petroledger-tfstate"
  #   key            = "env/prod/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "petroledger-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name_prefix = "${var.project}-${var.environment}"
}
