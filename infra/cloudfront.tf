resource "aws_cloudfront_vpc_origin" "alb" {
  vpc_origin_endpoint_config {
    name                   = "${local.name_prefix}-vpc-origin-alb"
    arn                    = aws_lb.main.arn
    http_port              = var.backend_container_port
    https_port             = 443
    origin_protocol_policy = "http-only"

    origin_ssl_protocols {
      items    = ["TLSv1.2"]
      quantity = 1
    }
  }

  tags = {
    Name = "${local.name_prefix}-vpc-origin-alb"
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-s3-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_cache_policy" "caching_disabled" {
  name        = "${local.name_prefix}-CachingDisabled"
  comment     = "No caching - pass through to origin"
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = false
    enable_accept_encoding_brotli = false

    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_cache_policy" "caching_optimized" {
  name        = "${local.name_prefix}-CachingOptimized"
  comment     = "Caching enabled for static assets"
  min_ttl     = 1
  default_ttl = 86400
  max_ttl     = 31536000

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true

    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_cache_policy" "use_origin_cache_control" {
  name        = "${local.name_prefix}-UseOriginCacheControl"
  comment     = "Respects origin Cache-Control headers"
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 31536000

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true

    cookies_config {
      cookie_behavior = "all"
    }

    headers_config {
      header_behavior = "whitelist"
      headers {
        items = [
          "x-method-override",
          "origin",
          "host",
          "x-http-method",
          "x-http-method-override",
        ]
      }
    }

    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_origin_request_policy" "all_viewer" {
  name    = "${local.name_prefix}-AllViewer"
  comment = "Forward all viewer parameters"

  cookies_config {
    cookie_behavior = "all"
  }

  headers_config {
    header_behavior = "allViewer"
  }

  query_strings_config {
    query_string_behavior = "all"
  }
}

resource "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name    = "${local.name_prefix}-AllViewerExceptHost"
  comment = "Forward all except Host header"

  cookies_config {
    cookie_behavior = "all"
  }

  headers_config {
    header_behavior = "allExcept"
    headers {
      items = ["host"]
    }
  }

  query_strings_config {
    query_string_behavior = "all"
  }
}

resource "aws_cloudfront_function" "url_rewrite" {
  name    = "${local.name_prefix}-url-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Append .html for clean URLs"
  publish = true

  code = <<-EOT
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      if (uri !== '/' && !uri.includes('.') && !uri.endsWith('/')) {
        request.uri = uri + '.html';
      }
      return request;
    }
  EOT
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2"
  price_class         = "PriceClass_All"
  default_root_object = "index.html"
  aliases             = [var.domain_name]
  web_acl_id          = aws_wafv2_web_acl.main.arn

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
    origin_shield {
      enabled              = true
      origin_shield_region = local.region
    }
  }

  origin {
    domain_name = "${aws_api_gateway_rest_api.health.id}.execute-api.${local.region}.amazonaws.com"
    origin_id   = "api-gateway"
    origin_path = "/v1"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  origin {
    domain_name = aws_lb.main.dns_name
    origin_id   = "vpc-origin-alb"

    vpc_origin_config {
      vpc_origin_id            = aws_cloudfront_vpc_origin.alb.id
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  default_cache_behavior {
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = aws_cloudfront_cache_policy.use_origin_cache_control.id
    allowed_methods        = ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"]
    cached_methods         = ["HEAD", "GET"]

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.url_rewrite.arn
    }
  }

  ordered_cache_behavior {
    path_pattern             = "/health"
    target_origin_id         = "api-gateway"
    viewer_protocol_policy   = "redirect-to-https"
    compress                 = true
    cache_policy_id          = aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    allowed_methods          = ["HEAD", "GET"]
    cached_methods           = ["HEAD", "GET"]
  }

  ordered_cache_behavior {
    path_pattern             = "/health-check"
    target_origin_id         = "api-gateway"
    viewer_protocol_policy   = "redirect-to-https"
    compress                 = true
    cache_policy_id          = aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    allowed_methods          = ["HEAD", "GET"]
    cached_methods           = ["HEAD", "GET"]
  }

  ordered_cache_behavior {
    path_pattern             = "/api/*"
    target_origin_id         = "vpc-origin-alb"
    viewer_protocol_policy   = "redirect-to-https"
    compress                 = true
    cache_policy_id          = aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    allowed_methods          = ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"]
    cached_methods           = ["HEAD", "GET"]
  }

  ordered_cache_behavior {
    path_pattern           = "/ws/*"
    target_origin_id       = "vpc-origin-alb"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = aws_cloudfront_cache_policy.use_origin_cache_control.id
    allowed_methods        = ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"]
    cached_methods         = ["HEAD", "GET"]
  }

  ordered_cache_behavior {
    path_pattern           = "/*"
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = aws_cloudfront_cache_policy.caching_optimized.id
    allowed_methods        = ["HEAD", "GET"]
    cached_methods         = ["HEAD", "GET"]

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.url_rewrite.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "${local.name_prefix}-distribution"
  }
}
