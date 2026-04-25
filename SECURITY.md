# Security

## Secrets

Do not commit production secrets to this repository.

Runtime values must live only in server-local files or environment variables:

- `backend/.env`
- `DATABASE_URL`
- `JWT_SECRET`
- `SUPERUSER_PASSWORD`
- database dumps and backups

The repository intentionally tracks only `backend/.env.example`, which contains empty or local-development placeholders.

## Before Sharing Or Deploying

Run these checks from the repository root:

```bash
git status --short
git ls-files | grep -E '(^|/)\\.env$|\\.dump$|\\.log$|backups/'
rg -n 'JWT_SECRET|SUPERUSER_PASSWORD|DATABASE_URL|password|secret|token' . -g '!backend/.venv/**' -g '!*.docx'
bash scripts/release_smoke.sh
```

Expected result:

- no tracked real `.env` files;
- no dumps, logs or backups in git;
- no real passwords or tokens in documentation;
- release smoke-check passes.
