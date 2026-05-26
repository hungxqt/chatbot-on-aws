locals {
  s3_buckets = {
    backend_env = {
      name = "${local.name_prefix}-backend-env"
    }
    app = {
      name = "${local.name_prefix}-app-bucket"
    }
    frontend = {
      name = "${local.name_prefix}-frontend-bucket"
    }
    backend = {
      name = "${local.name_prefix}-backend-bucket"
    }
    kb_source = {
      name = "${local.name_prefix}-kb-source"
    }
    multimedia_kb = {
      name = "${local.name_prefix}-multimedia-kb"
    }
  }
}

resource "aws_s3_bucket" "backend_env" {
  bucket = local.s3_buckets.backend_env.name
}

resource "aws_s3_bucket" "app" {
  bucket = local.s3_buckets.app.name
}

resource "aws_s3_bucket" "frontend" {
  bucket = local.s3_buckets.frontend.name
}

resource "aws_s3_bucket" "backend" {
  bucket = local.s3_buckets.backend.name
}

resource "aws_s3_bucket" "kb_source" {
  bucket = local.s3_buckets.kb_source.name
}

resource "aws_s3_bucket" "multimedia_kb" {
  bucket = local.s3_buckets.multimedia_kb.name
}

locals {
  managed_buckets = {
    backend_env   = aws_s3_bucket.backend_env
    app           = aws_s3_bucket.app
    frontend      = aws_s3_bucket.frontend
    backend       = aws_s3_bucket.backend
    kb_source     = aws_s3_bucket.kb_source
    multimedia_kb = aws_s3_bucket.multimedia_kb
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = local.managed_buckets

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "all" {
  for_each = local.managed_buckets

  bucket = each.value.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = local.managed_buckets

  bucket = each.value.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "all" {
  for_each = local.managed_buckets

  bucket = each.value.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_cors_configuration" "backend" {
  bucket = aws_s3_bucket.backend.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = [var.backend_cors_example_origin]
    max_age_seconds = 3600
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontServicePrincipal"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
        }
      }
    }]
  })
}
