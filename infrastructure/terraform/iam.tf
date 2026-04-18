data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name_prefix}-task-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution_attached" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Optional: allow the task execution role to pull SSM parameters for secrets.
data "aws_iam_policy_document" "ssm_read" {
  statement {
    actions   = ["ssm:GetParameters", "ssm:GetParameter", "secretsmanager:GetSecretValue", "kms:Decrypt"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "ssm_read" {
  name   = "${local.name_prefix}-ssm-read"
  policy = data.aws_iam_policy_document.ssm_read.json
}

resource "aws_iam_role_policy_attachment" "ssm_read_attached" {
  role       = aws_iam_role.task_execution.name
  policy_arn = aws_iam_policy.ssm_read.arn
}

# Task role — application-level AWS permissions (S3, SNS, etc.)
resource "aws_iam_role" "task_app" {
  name               = "${local.name_prefix}-task-app"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "app_permissions" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = ["*"]
  }

  statement {
    actions   = ["sns:Publish"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "app_permissions" {
  name   = "${local.name_prefix}-app"
  policy = data.aws_iam_policy_document.app_permissions.json
}

resource "aws_iam_role_policy_attachment" "app_attached" {
  role       = aws_iam_role.task_app.name
  policy_arn = aws_iam_policy.app_permissions.arn
}
