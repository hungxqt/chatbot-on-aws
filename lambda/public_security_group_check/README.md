# Public Security Group Check Lambda

Lambda that remediates security groups exposing sensitive ports to `0.0.0.0/0`.

## Behavior

- Scans EC2 security group inbound rules in one AWS region.
- Finds TCP port `22` and `5432` when exposed to `0.0.0.0/0`.
- Also finds `IpProtocol=-1` because it exposes all ports.
- Calls `RevokeSecurityGroupIngress` for the matching `0.0.0.0/0` ingress entry.
- Preserves other CIDRs and security-group sources on the same security group.
- If a public rule exposes a port through a wider range, for example `0-65535`, the public range rule is revoked as a whole.

## EventBridge Trigger (Self-Health Security Guard)

To achieve real-time, event-driven remediation, configure an **Amazon EventBridge Rule** triggered by AWS CloudTrail API events for security group modifications.

### Event Pattern

```json
{
  "source": ["aws.ec2"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventSource": ["ec2.amazonaws.com"],
    "eventName": [
      "AuthorizeSecurityGroupIngress",
      "CreateSecurityGroupIngress"
    ]
  }
}
```

When EventBridge detects one of these API calls, it routes the event to this Lambda function, which parses the target security group and immediately removes any rules that expose the protected ports to `0.0.0.0/0`.

## Handler

```text
handler.lambda_handler
```

This function uses the AWS Lambda Python runtime's bundled `boto3`; no deployment dependency package is required.

## Build Zip

Run from `lambda/public_security_group_check`:

```bash
docker run --rm -v ./:/out python:3.12 bash -c "apt-get update -qq && apt-get install -y zip -qq && rm -rf /tmp/build && mkdir -p /tmp/build && cp /out/handler.py /tmp/build/ && cd /tmp/build && zip -r /out/public_security_group_check.zip . -q"
```

## Example Invoke Payloads

Default check:

```json
{}
```

Override checked ports:

```json
{"ports": [22, 5432, 3306]}
```

Dry run without revoking:

```json
{"dry_run": true}
```

## Environment Variables

| Name | Default | Purpose |
|---|---|---|
| `AWS_REGION` | Lambda region / `us-east-1` fallback | AWS region for EC2 client |
| `PORTS` | `22,5432` | Comma-separated TCP ports to check |
| `DRY_RUN` | `false` | Set to `true` to report planned revocations without changing security groups |

## Principle of Least Privilege

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSecurityGroupScan",
      "Effect": "Allow",
      "Action": "ec2:DescribeSecurityGroups",
      "Resource": "*"
    },
    {
      "Sid": "AllowPublicIngressRemediation",
      "Effect": "Allow",
      "Action": "ec2:RevokeSecurityGroupIngress",
      "Resource": "arn:aws:ec2:REGION:ACCOUNT_ID:security-group/*"
    },
    {
      "Sid": "AllowLambdaLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:REGION:ACCOUNT_ID:log-group:/aws/lambda/public_security_group_check:*"
    }
  ]
}
```
