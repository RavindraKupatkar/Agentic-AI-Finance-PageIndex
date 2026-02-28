# deploy/

All deployment and infrastructure configuration files for FinSight PageIndex.

## Architecture

```
Browser → Vercel (Next.js frontend) → Cloud Run (FastAPI backend) → Groq LLM
                ↕                              ↕
            Clerk Auth                    Convex DB
```

## Files

| File | Purpose | Platform |
|------|---------|----------|
| `Dockerfile` | Production container image | Cloud Run, any Docker host |
| `cloudbuild.yaml` | CI/CD pipeline: build → push → deploy | Google Cloud Build |
| `docker-compose.yaml` | Local development with all services | Local |
| `.dockerignore` | Excludes files from Docker build context | Docker |
| `render.yaml` | Alternative: Render Blueprint | Render (backup) |
| `Procfile` | Process declaration for PaaS platforms | Heroku/Railway/Render |
| `nixpacks.toml` | Nixpacks builder config | Railway |
| `runtime.txt` | Python version for PaaS platforms | Railway/Render |

## Deployment Target

**Primary:** Google Cloud Run (serverless Docker containers)
- Auto-scales to zero (pay nothing when idle)
- Scales up automatically under load
- $0 for first 2M requests/month

**Frontend:** Vercel (Next.js)

## No Kubernetes

Cloud Run is **serverless**. There are no clusters, nodes, or pods to manage.
Google handles all infrastructure. You just push code.
