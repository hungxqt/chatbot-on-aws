resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-igw"
  }
}

resource "aws_subnet" "public" {
  for_each = local.subnet_tiers.public

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value
  availability_zone       = local.azs[index(local.az_keys, each.key)]
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.name_prefix}-subnet-public${index(local.az_keys, each.key) + 1}"
  }
}

resource "aws_subnet" "private" {
  for_each = local.subnet_tiers.private

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value
  availability_zone       = local.azs[index(local.az_keys, each.key)]
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.name_prefix}-subnet-private${index(local.az_keys, each.key) + 1}"
  }
}

resource "aws_subnet" "database" {
  for_each = local.subnet_tiers.database

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value
  availability_zone       = local.azs[index(local.az_keys, each.key)]
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.name_prefix}-subnet-database${index(local.az_keys, each.key) + 1}"
  }
}

resource "aws_subnet" "firewall" {
  for_each = local.subnet_tiers.firewall

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value
  availability_zone       = local.azs[index(local.az_keys, each.key)]
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.name_prefix}-subnet-firewall${index(local.az_keys, each.key) + 1}"
  }
}

resource "aws_eip" "nat" {
  for_each = toset(local.az_keys)

  domain = "vpc"

  tags = {
    Name = "${local.name_prefix}-eip-az${index(local.az_keys, each.key) + 1}"
  }
}

resource "aws_nat_gateway" "main" {
  connectivity_type = "public"
  availability_mode = "regional"
  vpc_id            = aws_vpc.main.id

  dynamic "availability_zone_address" {
    for_each = aws_eip.nat
    content {
      allocation_ids    = [availability_zone_address.value.id]
      availability_zone = local.azs[index(local.az_keys, availability_zone_address.key)]
    }
  }

  depends_on = [aws_internet_gateway.main]

  tags = {
    Name = "${local.name_prefix}-regional-nat"
  }
}

resource "aws_route_table" "igw_edge" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rtb-igw-edge"
  }
}

resource "aws_route_table" "firewall" {
  for_each = toset(local.az_keys)

  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rtb-firewall-${each.key}"
  }
}

resource "aws_route_table" "public" {
  for_each = toset(local.az_keys)

  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rtb-public-${each.key}"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rtb-private"
  }
}

resource "aws_route_table" "database" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-rtb-database"
  }
}

resource "aws_route" "firewall_to_igw" {
  for_each = aws_route_table.firewall

  route_table_id         = each.value.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route" "private_to_nat" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main.id
}

resource "aws_route_table_association" "firewall" {
  for_each = aws_subnet.firewall

  subnet_id      = each.value.id
  route_table_id = aws_route_table.firewall[each.key].id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public[each.key].id
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "database" {
  for_each = aws_subnet.database

  subnet_id      = each.value.id
  route_table_id = aws_route_table.database.id
}

resource "aws_network_acl" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-nacl"
  }
}

resource "aws_network_acl_rule" "allow_all_inbound" {
  network_acl_id = aws_network_acl.main.id
  rule_number    = 100
  protocol       = "-1"
  rule_action    = "allow"
  cidr_block     = "0.0.0.0/0"
}

resource "aws_network_acl_rule" "allow_all_outbound" {
  network_acl_id = aws_network_acl.main.id
  rule_number    = 100
  egress         = true
  protocol       = "-1"
  rule_action    = "allow"
  cidr_block     = "0.0.0.0/0"
}

resource "aws_vpc_dhcp_options" "main" {
  domain_name         = "ec2.internal"
  domain_name_servers = ["AmazonProvidedDNS"]

  tags = {
    Name = "${local.name_prefix}-dhcp-options"
  }
}

resource "aws_vpc_dhcp_options_association" "main" {
  vpc_id          = aws_vpc.main.id
  dhcp_options_id = aws_vpc_dhcp_options.main.id
}
