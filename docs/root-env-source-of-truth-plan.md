# Root `.env` As Local Source Of Truth

## Summary

- Use an untracked root `.env` as the local source for backend runtime config, frontend build/public config, CloudFormation parameters, and Terraform variables.
- Keep app-local env files as optional fallbacks, but make root `.env` take precedence.
- Keep GitHub Actions/production CI unchanged for now; this is local-only config unification.

## Key Changes

- Add/update root `.env.example` with the canonical key set:
  - App/backend: `PROJECT_NAME`, `ENVIRONMENT`, `POSTGRES_*`, `REDIS_*`, `SECRET_KEY`, `API_KEY`, `AWS_REGION`, `BEDROCK_*`, `CORS_ORIGINS`, `S3_*`, `EFS_*`
  - Frontend: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, `NEXT_PUBLIC_AUTH_ENABLED`, `NEXT_PUBLIC_RAG_ENABLED`, `NEXT_PUBLIC_MAX_UPLOAD_SIZE_MB`
  - IaC/deploy: `DOMAIN_NAME`, `HOSTED_ZONE_ID`, `ACM_CERTIFICATE_ARN`, `TEMPLATES_BUCKET`, `TEMPLATES_PREFIX`, `CONTAINER_IMAGE`, `LAMBDA_S3_BUCKET`, `LAMBDA_S3_KEY`, `ENABLE_RDS_SSL`, `CREATE_OPENSEARCH`
- Backend:
  - Update `backend/app/core/config.py` so settings load root `.env` first, then fall back to backend-local env files.
  - Update Docker Compose files to reference root `.env` instead of `backend/.env`; keep only unavoidable service wiring overrides if needed.
- Frontend:
  - Update `frontend/next.config.ts` to load root `.env` before Next build config is evaluated.
  - Update frontend Docker/Compose build config so `NEXT_PUBLIC_*` values come from root `.env`.
- CloudFormation:
  - Update `cloudformation/deploy.sh` to source root `.env` and map those values into stack parameters.
  - CLI flags keep highest precedence, then root `.env`, then safe script defaults.
  - Add initial-create safety for the ECS S3 env-file path: create with backend desired count `0`, upload the root-derived backend env file to `${PROJECT_NAME}-backend-env/.env`, then update desired count to the configured value.
- Terraform:
  - Add `infra/tf.ps1` and `infra/tf.sh` wrappers that load root `.env` and export explicit `TF_VAR_*` mappings.
  - Keep readable root env names; do not require `TF_VAR_*` keys in `.env`.
  - Add Terraform support for uploading the backend env file to the backend-env S3 bucket before ECS tasks start.

## Test Plan

- Verify root env loading:
  - Run backend config smoke test from repo root and from `backend/` cwd; both must resolve root `.env` first.
  - Run `frontend` build/type-check with root `NEXT_PUBLIC_*` values.
- Verify IaC config mapping:
  - Run `cloudformation/deploy.sh --dry-run` or equivalent parameter-print mode without printing secret values.
  - Run `infra/tf.ps1 validate` and `infra/tf.ps1 plan -refresh=false` with root `.env`.
- Verify no stale env source remains:
  - Search for hardcoded `backend/.env`, `frontend/.env.local`, and editable CloudFormation config constants.
  - Confirm `.env` remains ignored and no secret values are committed.

## Assumptions

- Root `.env` is local-only and untracked; CI continues to use GitHub secrets.
- Existing backend/frontend env files remain optional fallbacks, not the primary source.
- Root `.env` primarily represents AWS deploy values, not host-process local development values.
- AWS credentials are not stored in `.env`; AWS CLI/Terraform continue using the local AWS credential chain.
