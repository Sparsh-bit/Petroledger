# PetroLedger — Deployment guide

## Option 1: Vercel (frontend) + Render (backend)

Default, lowest-friction path. Already wired via `vercel.json` and
`render.yaml`.

### Backend — Render

1. **Connect repo** → "Blueprint" → Render reads `render.yaml`.
2. Set these secrets in the service dashboard:
   - `DATABASE_URL` (Postgres asyncpg URL; Supabase works)
   - `REDIS_URL` (Upstash or Render-managed Redis)
   - `SUPERADMIN_EMAIL`, `SUPERADMIN_PASSWORD`
   - `CORS_ORIGINS` — your Vercel production domain
   - Optional: `SMTP_*`, `SENTRY_DSN`
3. Deploy. Health is polled at `/health`; detailed probe at
   `/api/v1/health/`.

### Frontend — Vercel

1. **Import repo** → set root directory to **`/` (repo root)**, not `frontend/`.
   `vercel.json` at the repo root controls the full build:
   - Build command: `cd frontend && npm install && npm run build`
   - Output directory: `frontend/dist`
   - SPA rewrites and security headers are already configured.
2. **Framework preset** → Other (auto-detected from `vercel.json`).
3. **Environment variable** (Vercel dashboard → Settings → Environment Variables):

   | Key | Value |
   |-----|-------|
   | `VITE_API_BASE_URL` | `https://<your-service>.onrender.com` |

4. **Deploy**. Every push to `main` triggers a production deployment automatically.
5. Copy your Vercel URL (e.g. `https://petroledger.vercel.app`) and add it to
   `CORS_ORIGINS` in your Render service environment, then redeploy Render.

## Option 2: AWS (Terraform)

1. `cd infrastructure/terraform`
2. `terraform init` (configure S3 remote state first — see `main.tf`).
3. Request ACM certs in both the ALB region (`ap-south-1`) and
   `us-east-1` (for CloudFront), validate via DNS.
4. `terraform plan` + `terraform apply` with:
   - `acm_certificate_arn`
   - `acm_certificate_arn_us_east_1`
   - `backend_image` (push to ECR first, or use `:latest`)
5. Push backend image:
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin <ecr-url>
   docker build -f backend/Dockerfile -t <ecr-url>:<tag> backend/
   docker push <ecr-url>:<tag>
   aws ecs update-service --cluster <cluster> --service <svc> --force-new-deployment
   ```
6. Push frontend bundle:
   ```bash
   (cd frontend && npm ci && npm run build)
   aws s3 sync frontend/dist/ s3://<bucket>/ --delete
   aws cloudfront create-invalidation --distribution-id <id> --paths '/*'
   ```

The `.github/workflows/deploy.yml` automates steps 5–6 once secrets are
configured and the `if: false` guards are removed.

## Option 3: Docker Compose (self-host)

```yaml
# docker-compose.yml (example)
services:
  api:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://...
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      SUPERADMIN_EMAIL: ${SUPERADMIN_EMAIL}
      SUPERADMIN_PASSWORD: ${SUPERADMIN_PASSWORD}
      CORS_ORIGINS: http://localhost:8080
    ports: ["8000:8000"]
    depends_on: [db, redis]

  web:
    build: ./frontend
    ports: ["8080:80"]

  db:
    image: postgres:15
    environment: { POSTGRES_PASSWORD: postgres }

  redis:
    image: redis:7-alpine
```

## Migrations

Run `alembic upgrade head` after each backend deploy that ships new
migrations. On Render, add it to the start command if you want automatic
migration; on ECS, run a one-off task.

## Rollback

- Render: redeploy the previous image tag from the dashboard.
- ECS: `aws ecs update-service --task-definition <previous-revision>`
- Vercel/CloudFront: promote a previous deployment / invalidate and
  re-sync the previous build artifacts.
