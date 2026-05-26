resource "aws_networkfirewall_rule_group" "block_facebook" {
  capacity = 100
  name     = "${local.name_prefix}-block-facebook"
  type     = "STATEFUL"

  rule_group {
    stateful_rule_options {
      rule_order = "STRICT_ORDER"
    }

    rules_source {
      stateful_rule {
        action = "DROP"

        header {
          protocol         = "IP"
          source           = var.vpc_cidr
          source_port      = "ANY"
          direction        = "FORWARD"
          destination      = "57.144.0.0/14"
          destination_port = "ANY"
        }

        rule_option {
          keyword  = "msg"
          settings = ["\"BLOCK_META_NETWORK\""]
        }

        rule_option {
          keyword  = "sid"
          settings = ["1000005"]
        }

        rule_option {
          keyword  = "rev"
          settings = ["1"]
        }
      }
    }
  }

  tags = {
    Name = "${local.name_prefix}-block-facebook"
  }
}

resource "aws_networkfirewall_firewall_policy" "main" {
  name = "${local.name_prefix}-firewall-policy"

  firewall_policy {
    stateful_engine_options {
      rule_order              = "STRICT_ORDER"
      stream_exception_policy = "REJECT"
    }

    stateful_rule_group_reference {
      priority     = 1
      resource_arn = "arn:${local.partition}:network-firewall:${local.region}:aws-managed:stateful-rulegroup/AttackInfrastructureStrictOrder"
    }

    stateful_rule_group_reference {
      priority     = 2
      resource_arn = aws_networkfirewall_rule_group.block_facebook.arn
    }

    stateless_default_actions          = ["aws:forward_to_sfe"]
    stateless_fragment_default_actions = ["aws:forward_to_sfe"]
    stateful_default_actions = [
      "aws:alert_established_app_layer",
      "aws:alert_strict",
      "aws:drop_established_app_layer",
    ]
  }

  tags = {
    Name = "${local.name_prefix}-firewall-policy"
  }
}

resource "aws_networkfirewall_firewall" "main" {
  name                = "${local.name_prefix}-network-firewall-vpc"
  firewall_policy_arn = aws_networkfirewall_firewall_policy.main.arn
  vpc_id              = aws_vpc.main.id
  delete_protection   = false

  dynamic "subnet_mapping" {
    for_each = aws_subnet.firewall
    content {
      subnet_id       = subnet_mapping.value.id
      ip_address_type = "IPV4"
    }
  }

  tags = {
    Name = "${local.name_prefix}-network-firewall-vpc"
  }
}

locals {
  firewall_endpoint_ids_by_az = {
    for sync_state in aws_networkfirewall_firewall.main.firewall_status[0].sync_states :
    sync_state.availability_zone => sync_state.attachment[0].endpoint_id
  }
}

resource "aws_route" "public_to_firewall" {
  for_each = aws_route_table.public

  route_table_id         = each.value.id
  destination_cidr_block = "0.0.0.0/0"
  vpc_endpoint_id        = local.firewall_endpoint_ids_by_az[local.azs[index(local.az_keys, each.key)]]
}

resource "aws_route" "igw_edge_to_firewall" {
  for_each = aws_subnet.public

  route_table_id         = aws_route_table.igw_edge.id
  destination_cidr_block = each.value.cidr_block
  vpc_endpoint_id        = local.firewall_endpoint_ids_by_az[each.value.availability_zone]
}

resource "aws_route_table_association" "igw_edge" {
  gateway_id     = aws_internet_gateway.main.id
  route_table_id = aws_route_table.igw_edge.id
}
