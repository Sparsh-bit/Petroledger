# ── ElastiCache Redis (optional) ───────────────────────────────────────
# Commented by default — PetroLedger can continue to use Upstash. Uncomment
# to provision an in-VPC Redis cluster for tenant-lock caching + rate limits.

# resource "aws_elasticache_subnet_group" "main" {
#   name       = "${local.name_prefix}-redis-subnets"
#   subnet_ids = aws_subnet.private[*].id
# }
#
# resource "aws_security_group" "redis" {
#   name        = "${local.name_prefix}-redis-sg"
#   description = "Allow Redis from ECS service only"
#   vpc_id      = aws_vpc.main.id
#
#   ingress {
#     from_port       = 6379
#     to_port         = 6379
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
# resource "aws_elasticache_replication_group" "main" {
#   replication_group_id       = "${local.name_prefix}-redis"
#   description                = "PetroLedger Redis"
#   engine                     = "redis"
#   engine_version             = "7.1"
#   node_type                  = "cache.t4g.micro"
#   num_cache_clusters         = 2
#   automatic_failover_enabled = true
#   multi_az_enabled           = true
#   subnet_group_name          = aws_elasticache_subnet_group.main.name
#   security_group_ids         = [aws_security_group.redis.id]
#   transit_encryption_enabled = true
#   at_rest_encryption_enabled = true
# }
