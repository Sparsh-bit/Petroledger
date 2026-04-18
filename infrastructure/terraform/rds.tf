# ── RDS Postgres (optional) ────────────────────────────────────────────
# Commented by default — PetroLedger can continue to use Supabase. Uncomment
# the block below to provision a managed Postgres 15 instance inside this VPC.

# resource "aws_db_subnet_group" "main" {
#   name       = "${local.name_prefix}-db-subnets"
#   subnet_ids = aws_subnet.private[*].id
# }
#
# resource "aws_security_group" "rds" {
#   name        = "${local.name_prefix}-rds-sg"
#   description = "Allow Postgres from ECS service only"
#   vpc_id      = aws_vpc.main.id
#
#   ingress {
#     from_port       = 5432
#     to_port         = 5432
#     protocol        = "tcp"
#     security_groups = [aws_security_group.service.id]
#   }
#
#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
# }
#
# resource "aws_db_instance" "main" {
#   identifier              = "${local.name_prefix}-db"
#   engine                  = "postgres"
#   engine_version          = "15.6"
#   instance_class          = "db.t4g.small"
#   allocated_storage       = 20
#   storage_encrypted       = true
#   db_name                 = "petroledger"
#   username                = "petroledger"
#   manage_master_user_password = true
#   vpc_security_group_ids  = [aws_security_group.rds.id]
#   db_subnet_group_name    = aws_db_subnet_group.main.name
#   backup_retention_period = 7
#   deletion_protection     = true
#   skip_final_snapshot     = false
#   apply_immediately       = false
# }
