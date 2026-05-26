# Stop Compute Lambda

Stops billable RDS, ECS, and EC2 compute that is not protected by the environment tag policy.

## Behavior

- EC2 instances in `running` state are stopped with `StopInstances`.
- RDS DB instances in `available` state are stopped with `StopDBInstance`.
- RDS DB clusters in `available` state are stopped with `StopDBCluster`.
- ECS services with `desiredCount > 0` are updated to `desiredCount: 0`.
- Any resource tagged `Environment=Production` is skipped.
- Any resource tagged `Environment=Development` and `Keep=True` is skipped.
- All other RDS, ECS, and EC2 targets are eligible.
- Set `TARGET_ENVIRONMENT=Development` to narrow execution to one environment tag value.
- Invoke with `{"dry_run": true}` to inspect the planned actions without stopping anything.

## Handler

```text
handler.lambda_handler
```

This function uses the AWS Lambda Python runtime's bundled `boto3`; no deployment dependency package is required.

## Example Invoke Payloads

Stop every unprotected RDS/ECS/EC2 resource:

```json
{}
```

Preview only:

```json
{"dry_run": true}
```

Stop only unprotected development resources:

```json
{"target_environment": "Development"}
```

## Environment Variables

| Name | Default | Purpose |
|---|---|---|
| `AWS_REGION` | Lambda region / `us-east-1` fallback | AWS region for RDS and ECS clients |
| `DRY_RUN` | `false` | Set `true` to preview by default |
| `TARGET_ENVIRONMENT` | empty | Optional tag value filter, for example `Development` |
| `KEEP_TAG_KEY` | `Keep` | Protection tag key |
| `ENVIRONMENT_TAG_KEY` | `Environment` | Environment tag key |
| `PRODUCTION_ENVIRONMENT_VALUE` | `Production` | Environment value that is always protected |
| `DEVELOPMENT_ENVIRONMENT_VALUE` | `Development` | Environment value where `Keep=True` also protects the resource |

## Principle of Least Privilege

Use the narrowest resource ARNs possible for your account, region, clusters, services, DB instances, and DB clusters.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowEc2Discovery",
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
    },
    {
      "Sid": "AllowStopOnlyApprovedEc2Instances",
      "Effect": "Allow",
      "Action": "ec2:StopInstances",
      "Resource": [
        "arn:aws:ec2:REGION:ACCOUNT_ID:instance/INSTANCE_ID"
      ]
    },
    {
      "Sid": "AllowRdsDiscoveryAndTags",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBClusters",
        "rds:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowStopOnlyApprovedRdsInstances",
      "Effect": "Allow",
      "Action": "rds:StopDBInstance",
      "Resource": [
        "arn:aws:rds:REGION:ACCOUNT_ID:db:DB_INSTANCE_ID"
      ]
    },
    {
      "Sid": "AllowStopOnlyApprovedRdsClusters",
      "Effect": "Allow",
      "Action": "rds:StopDBCluster",
      "Resource": [
        "arn:aws:rds:REGION:ACCOUNT_ID:cluster:DB_CLUSTER_ID"
      ]
    },
    {
      "Sid": "AllowEcsDiscoveryAndTags",
      "Effect": "Allow",
      "Action": [
        "ecs:ListClusters",
        "ecs:ListServices",
        "ecs:DescribeServices",
        "ecs:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowScaleDownOnlyApprovedEcsServices",
      "Effect": "Allow",
      "Action": "ecs:UpdateService",
      "Resource": [
        "arn:aws:ecs:REGION:ACCOUNT_ID:service/CLUSTER_NAME/SERVICE_NAME"
      ]
    },
    {
      "Sid": "AllowLambdaLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:REGION:ACCOUNT_ID:log-group:/aws/lambda/FUNCTION_NAME:*"
    }
  ]
}
```

The Lambda code still checks tags at runtime. IAM should also restrict the `StopInstances`, `StopDBInstance`, `StopDBCluster`, and `UpdateService` resources to only the resources this function is allowed to shut down.
