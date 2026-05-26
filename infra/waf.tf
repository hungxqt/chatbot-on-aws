resource "aws_wafv2_web_acl" "main" {
  name  = "${local.name_prefix}-waf"
  scope = "CLOUDFRONT"

  default_action {
    allow {}
  }

  visibility_config {
    sampled_requests_enabled   = true
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-waf"
  }

  rule {
    name     = "RateLimit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        aggregate_key_type    = "IP"
        evaluation_window_sec = 300
        limit                 = var.waf_rate_limit
      }
    }

    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit"
    }
  }

  dynamic "rule" {
    for_each = {
      IPReputation   = { priority = 2, name = "AWSManagedRulesAmazonIpReputationList" }
      CommonRuleSet  = { priority = 3, name = "AWSManagedRulesCommonRuleSet" }
      KnownBadInputs = { priority = 4, name = "AWSManagedRulesKnownBadInputsRuleSet" }
      SQLInjection   = { priority = 5, name = "AWSManagedRulesSQLiRuleSet" }
    }

    content {
      name     = rule.key
      priority = rule.value.priority

      override_action {
        none {}
      }

      statement {
        managed_rule_group_statement {
          vendor_name = "AWS"
          name        = rule.value.name
        }
      }

      visibility_config {
        sampled_requests_enabled   = true
        cloudwatch_metrics_enabled = true
        metric_name                = rule.key
      }
    }
  }
}
