resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "${local.name_prefix}-vpc-flow-logs"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-vpc-flow-logs"
  }
}

resource "aws_cloudwatch_log_group" "database_subnet_flow_logs" {
  name              = "${local.name_prefix}-database-subnets-vpc-flow-log"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-database-subnets-vpc-flow-log"
  }
}

resource "aws_flow_log" "vpc" {
  iam_role_arn             = aws_iam_role.vpc_flow_logs.arn
  log_destination          = aws_cloudwatch_log_group.vpc_flow_logs.arn
  log_destination_type     = "cloud-watch-logs"
  max_aggregation_interval = 60
  vpc_id                   = aws_vpc.main.id
  traffic_type             = "ALL"

  log_format = "$${version} $${account-id} $${interface-id} $${srcaddr} $${dstaddr} $${srcport} $${dstport} $${protocol} $${packets} $${bytes} $${start} $${end} $${action} $${log-status} $${ecs-cluster-name} $${ecs-cluster-arn} $${ecs-container-instance-id} $${ecs-container-instance-arn} $${ecs-service-name} $${ecs-task-definition-arn} $${ecs-task-id} $${ecs-task-arn} $${ecs-container-id} $${ecs-second-container-id}"

  tags = {
    Name = "${local.name_prefix}-vpc-flow-log"
  }
}

resource "aws_flow_log" "database_subnet" {
  for_each = aws_subnet.database

  iam_role_arn             = aws_iam_role.vpc_flow_logs.arn
  log_destination          = aws_cloudwatch_log_group.database_subnet_flow_logs.arn
  log_destination_type     = "cloud-watch-logs"
  max_aggregation_interval = 60
  subnet_id                = each.value.id
  traffic_type             = "ALL"

  log_format = "$${version} $${account-id} $${interface-id} $${srcaddr} $${dstaddr} $${srcport} $${dstport} $${protocol} $${packets} $${bytes} $${start} $${end} $${action} $${log-status} $${ecs-cluster-name} $${ecs-cluster-arn} $${ecs-container-instance-id} $${ecs-container-instance-arn} $${ecs-service-name} $${ecs-task-definition-arn} $${ecs-task-id} $${ecs-task-arn} $${ecs-container-id} $${ecs-second-container-id}"

  tags = {
    Name = "${local.name_prefix}-database-subnet${index(local.az_keys, each.key) + 1}-flow-log"
  }
}
