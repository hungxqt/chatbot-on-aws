# SAM Stack

This directory contains a parallel AWS SAM version of the existing infrastructure stack. The original `cloudformation/` templates are intentionally not used as deployment inputs and should remain unchanged.

## Layout

- `template.yaml` is the SAM root template.
- `sections/` contains local nested application templates copied from the CloudFormation sections.
- `functions/health_checker_lite/` contains the local Lambda source packaged by SAM.

## Validate And Build

```bash
cd sam
sam validate --lint --template-file template.yaml
sam build --parallel
```

## Deploy Preview

Choose a new stack name and `ProjectName` for the SAM deployment. Do not reuse the original stack's project name unless you are intentionally targeting the same physical names.

Provide the RDS password at deploy time. Leave the domain parameters empty for the first parallel deployment so CloudFront uses its generated domain instead of the production alias.

```bash
cd sam
sam deploy --guided \
  --stack-name <your-sam-stack-name> \
  --parameter-overrides ProjectName=<your-sam-project-name>
```

For a non-interactive change set preview:

```bash
cd sam
sam deploy --no-execute-changeset \
  --stack-name <your-sam-stack-name> \
  --parameter-overrides \
    ProjectName=<your-sam-project-name> \
    RdsMasterPassword='<set-outside-git>' \
    EnableRdsSsl=true \
    CreateOpenSearchCollection=false \
    DomainName='' \
    AcmCertificateArn='' \
    HostedZoneId='' \
    ContainerImage='' \
    HealthCheckUrl=''
```

To enable a custom domain later, pass `DomainName`, `AcmCertificateArn`, and optionally `HostedZoneId` together. Do not use the original production domain for this parallel stack unless you are intentionally cutting traffic over.
