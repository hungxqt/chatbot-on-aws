output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "rds_endpoint" {
  value       = aws_db_instance.main.address
  description = "RDS PostgreSQL endpoint"
}

output "redis_endpoint" {
  value       = aws_elasticache_serverless_cache.redis.endpoint[0].address
  description = "ElastiCache Redis endpoint"
}

output "knowledge_base_id" {
  value       = var.create_opensearch_collection ? aws_bedrockagent_knowledge_base.main[0].id : ""
  description = "Bedrock Knowledge Base ID"
}

output "ecs_cluster_arn" {
  value       = aws_ecs_cluster.main.arn
  description = "ECS Cluster ARN"
}

output "ecr_repository_uri" {
  value       = aws_ecr_repository.backend.repository_url
  description = "ECR Repository URI"
}

output "alb_dns_name" {
  value       = aws_lb.main.dns_name
  description = "Internal ALB DNS name"
}

output "api_gateway_invoke_url" {
  value       = aws_api_gateway_stage.v1.invoke_url
  description = "API Gateway invoke URL"
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.main.id
  description = "CloudFront Distribution ID"
}

output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.main.domain_name
  description = "CloudFront domain name"
}

output "application_url" {
  value       = "https://${var.domain_name}"
  description = "Application URL"
}
