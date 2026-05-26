variable "project_name" {
  type    = string
  default = "webapp-group10"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "rds_master_username" {
  type    = string
  default = "postgres"
}

variable "rds_master_password" {
  type      = string
  sensitive = true
}

variable "enable_rds_ssl" {
  type    = bool
  default = true
}

variable "create_opensearch_collection" {
  type    = bool
  default = false
}

variable "domain_name" {
  type    = string
  default = "aws.hungtran.id.vn"
}

variable "acm_certificate_arn" {
  type        = string
  description = "ACM certificate ARN in us-east-1 for CloudFront HTTPS."
}

variable "hosted_zone_id" {
  type    = string
  default = ""
}

variable "container_image" {
  type        = string
  default     = ""
  description = "Optional backend image URI. Defaults to the stack ECR backend repository."
}

variable "lambda_s3_bucket" {
  type        = string
  description = "S3 bucket containing the Lambda health check deployment package."
}

variable "lambda_s3_key" {
  type        = string
  description = "S3 key for the Lambda health check deployment package."
}

variable "health_check_url" {
  type        = string
  default     = ""
  description = "Optional override for the Lambda main app health URL."
}

variable "backend_cpu" {
  type    = number
  default = 2048
}

variable "backend_memory" {
  type    = number
  default = 4096
}

variable "backend_desired_count" {
  type    = number
  default = 6
}

variable "backend_max_count" {
  type    = number
  default = 9
}

variable "backend_container_port" {
  type    = number
  default = 8000
}

variable "db_name" {
  type    = string
  default = "postgres"
}

variable "waf_rate_limit" {
  type    = number
  default = 500
}

variable "backend_cors_example_origin" {
  type    = string
  default = "https://webapp-group10.example.com"
}
