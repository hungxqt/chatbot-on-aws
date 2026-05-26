# Health Checker Lite (Zero Dependencies)

Drop-in replacement for `health_checker/` with **no external packages**.

## What changed vs `health_checker/`

| Component | `health_checker/` | `health_checker_lite/` |
|---|---|---|
| PostgreSQL | `psycopg2-binary` (~3MB) | Raw PG wire protocol over TCP socket |
| Redis | `redis` (~1MB) | Raw RESP protocol over TCP/TLS socket |
| AWS APIs | `boto3`+`botocore` (~70MB) | SigV4-signed HTTP via `urllib.request` |
| Zip size | ~80MB | ~50KB |
| Cold start | ~5-10s (imports) | ~100ms |

## Deploy

```bash
cd lambda/health_checker_lite
chmod +x deploy.sh
./deploy.sh                                          # build zip
./deploy.sh --upload ai-agent-health-checker         # build + deploy
```

## Caveats

- PostgreSQL check verifies TCP connectivity and protocol handshake, not full SQL execution.
- Redis check sends AUTH + PING using raw RESP, verifies +PONG response.
- AWS SigV4 signing uses Lambda's runtime credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN) — same as boto3 would.
