# HireWire Infrastructure & CI/CD

> Kubernetes deployment spec following existing homelab conventions.

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [PostgreSQL Setup](#postgresql-setup)
- [Application Charts](#application-charts)
- [Networking](#networking)
- [Secrets Management](#secrets-management)
- [Deployment](#deployment)
- [Monitoring](#monitoring)

---

## Overview

HireWire deploys as two K8s workloads sharing a PostgreSQL database:

- **Web App** — Deployment serving FastAPI + Vue frontend
- **Scraper** — CronJob running every 2 hours

Both use the existing `workload` library chart and follow app-of-apps patterns.

```mermaid
flowchart TB
    subgraph k3s [K3s Cluster]
        subgraph ns [hirewire namespace]
            WebApp[Web App Deployment]
            Scraper[Scraper CronJob]
            PG[(PostgreSQL)]
        end
        
        subgraph infra [infra namespace]
            SealedSecrets[Sealed Secrets]
        end
        
        subgraph networking [networking]
            Ingress[IngressRoute]
            Cert[TLS Certificate]
        end
    end
    
    Internet([Internet]) --> Ingress
    Ingress --> WebApp
    WebApp --> PG
    Scraper --> PG
    SealedSecrets -.->|decrypts| ns
```

---

## Architecture

### Directory Structure

```
k3s/
├── applications/
│   └── hirewire/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           └── configmap.yaml      # Optional: search config seeds
│
├── infra/
│   ├── postgresql/                 # NEW: Shared PostgreSQL
│   │   ├── Chart.yaml
│   │   └── values.yaml
│   └── secrets/
│       ├── hirewire-db.yaml        # SealedSecret: DB credentials
│       └── hirewire-scraper.yaml   # SealedSecret: API keys (future)
│
└── networking/
    └── values.yaml                 # Add hirewire domain entry
```

### Resource Summary

| Resource | Name | Purpose |
|----------|------|---------|
| Deployment | `hirewire-web` | FastAPI + Vue frontend |
| CronJob | `hirewire-scraper` | Job scraping (every 2h) |
| StatefulSet | `postgresql` | Shared database (infra) |
| Service | `hirewire-web` | ClusterIP for web app |
| Service | `postgresql` | ClusterIP for database |
| PVC | `postgresql-data` | 10Gi database storage |
| SealedSecret | `hirewire-db` | Database credentials |
| IngressRoute | `hirewire` | External HTTPS access |
| Certificate | `hirewire-tls` | Let's Encrypt TLS |

---

## PostgreSQL Setup

Add shared PostgreSQL to infra (can be reused by future apps).

### Chart Definition

```yaml
# k3s/infra/postgresql/Chart.yaml
apiVersion: v2
name: postgresql
description: Shared PostgreSQL database
type: application
version: 0.1.0
appVersion: "16"

dependencies:
  - name: postgresql
    version: "15.5.38"
    repository: "https://charts.bitnami.com/bitnami"
```

### Values

```yaml
# k3s/infra/postgresql/values.yaml
postgresql:
  auth:
    # Credentials from SealedSecret
    existingSecret: postgresql-credentials
    secretKeys:
      adminPasswordKey: postgres-password
      userPasswordKey: password
    username: hirewire
    database: hirewire
  
  primary:
    persistence:
      enabled: true
      size: 10Gi
      storageClass: local-path  # Or your preferred storageClass
    
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 512Mi
    
    # Security context (Restricted PSS)
    podSecurityContext:
      fsGroup: 1001
      runAsUser: 1001
      runAsNonRoot: true
    
    containerSecurityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 1001
      seccompProfile:
        type: RuntimeDefault
  
  # Disable replication for single-node
  architecture: standalone
  
  # Metrics for Prometheus
  metrics:
    enabled: true
    serviceMonitor:
      enabled: true
```

### Register in App-of-Apps

```yaml
# k3s/app-of-apps/values.yaml (add to infra section)
infra:
  # ... existing entries ...
  
  postgresql:
    namespace: postgresql
    syncPolicy:
      automated:
        prune: true
        selfHeal: true
```

---

## Application Charts

### HireWire Web + Scraper

Single chart deploys both workloads using the shared `workload` library.

```yaml
# k3s/applications/hirewire/Chart.yaml
apiVersion: v2
name: hirewire
description: Job search aggregator
type: application
version: 0.1.0
appVersion: "0.1.0"

dependencies:
  - name: workload
    version: "0.3.0"
    repository: "file://../../charts/workload"
    alias: web
  
  - name: workload
    version: "0.3.0"
    repository: "file://../../charts/workload"
    alias: scraper
```

### Values

```yaml
# k3s/applications/hirewire/values.yaml

# ============================================================================
# WEB APP (Deployment)
# ============================================================================
web:
  workload:
    image:
      repository: ghcr.io/pww217/hirewire
      tag: latest
      pullPolicy: Always
    
    # Deployment (default mode)
    replicaCount: 1
    
    service:
      port: 80
      targetPort: 8000
    
    # Environment variables
    env:
      - name: ENVIRONMENT
        value: "production"
      - name: LOG_LEVEL
        value: "INFO"
      - name: LOG_FORMAT
        value: "json"
    
    # Database connection from secret
    envFrom:
      - secretRef:
          name: hirewire-db
    
    # Health checks
    healthCheck:
      enabled: true
      path: /health
      startupProbe:
        failureThreshold: 30
        periodSeconds: 2
      livenessProbe:
        periodSeconds: 30
        failureThreshold: 3
      readinessProbe:
        periodSeconds: 10
        failureThreshold: 3
    
    # Resources
    resources:
      requests:
        cpu: 50m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi
    
    # Security (Restricted PSS defaults from workload chart)
    podSecurityContext:
      runAsUser: 1000
      runAsGroup: 1000
      fsGroup: 1000
      runAsNonRoot: true

# ============================================================================
# SCRAPER (CronJob)
# ============================================================================
scraper:
  workload:
    # CronJob mode
    kind: CronJob
    schedule: "0 */2 * * *"  # Every 2 hours
    
    image:
      repository: ghcr.io/pww217/hirewire
      tag: latest
      pullPolicy: Always
    
    # Job configuration
    job:
      restartPolicy: OnFailure
      backoffLimit: 3
      activeDeadlineSeconds: 600  # 10 minute timeout
      ttlSecondsAfterFinished: 86400  # Keep completed jobs for 1 day
      concurrencyPolicy: Forbid  # Don't overlap runs
    
    # Environment
    env:
      - name: LOG_LEVEL
        value: "INFO"
      - name: LOG_FORMAT
        value: "json"
      - name: ENABLED_SOURCES
        value: "jobspy"
      - name: JOBSPY_SITES
        value: "indeed,glassdoor"
      - name: SCRAPE_TIMEOUT_SECONDS
        value: "300"
    
    # Database connection
    envFrom:
      - secretRef:
          name: hirewire-db
    
    # Resources (higher for scraping)
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 1000m
        memory: 1Gi
    
    # Security
    podSecurityContext:
      runAsUser: 1000
      runAsGroup: 1000
      runAsNonRoot: true
```

### Register in App-of-Apps

```yaml
# k3s/app-of-apps/values.yaml (add to apps section)
apps:
  # ... existing entries ...
  
  hirewire:
    namespace: hirewire
    syncPolicy:
      automated:
        prune: true
        selfHeal: true
```

---

## Networking

### Domain Configuration

```yaml
# k3s/networking/values.yaml (add to domains section)
domains:
  # ... existing domains ...
  
  hirewire:
    host: jobs.subnet75.com  # Or your preferred subdomain
    service: hirewire-web
    namespace: hirewire
    port: 80
    dns:
      target: connect.subnet75.com  # Your DDNS endpoint
      proxied: true
    security:
      tier: web  # 100 req/min rate limit
```

This generates:
- IngressRoute with TLS
- Let's Encrypt certificate
- Cloudflare DNS record
- Security headers middleware
- Rate limiting

### Internal-Only Alternative

If you prefer LAN-only access initially:

```yaml
domains:
  hirewire:
    host: jobs.subnet75.com
    service: hirewire-web
    namespace: hirewire
    port: 80
    tls: {}  # Certificate only, no public DNS
    # No dns: block = internal only
```

---

## Secrets Management

### Database Credentials

Create and seal the database secret:

```bash
# 1. Generate password
DB_PASSWORD=$(openssl rand -base64 32)

# 2. Create secret manifest (dry-run)
kubectl create secret generic hirewire-db \
  --namespace=hirewire \
  --from-literal=DATABASE_URL="postgresql://hirewire:${DB_PASSWORD}@postgresql.postgresql.svc.cluster.local:5432/hirewire" \
  --dry-run=client -o yaml > /tmp/hirewire-db.yaml

# 3. Seal with kubeseal
kubeseal --format yaml < /tmp/hirewire-db.yaml > k3s/infra/secrets/hirewire-db.yaml

# 4. Clean up plaintext
rm /tmp/hirewire-db.yaml

# 5. Commit sealed secret
git add k3s/infra/secrets/hirewire-db.yaml
git commit -m "Add HireWire database credentials"
```

### PostgreSQL Admin Credentials

```bash
# For the PostgreSQL chart itself
POSTGRES_PASSWORD=$(openssl rand -base64 32)
USER_PASSWORD=$(openssl rand -base64 32)

kubectl create secret generic postgresql-credentials \
  --namespace=postgresql \
  --from-literal=postgres-password="${POSTGRES_PASSWORD}" \
  --from-literal=password="${USER_PASSWORD}" \
  --dry-run=client -o yaml | kubeseal --format yaml \
  > k3s/infra/secrets/postgresql-credentials.yaml
```

### Future: Scraper API Keys (Phase 3)

When adding ATS integrations, create additional secrets:

```bash
kubectl create secret generic hirewire-scraper-keys \
  --namespace=hirewire \
  --from-literal=GREENHOUSE_API_KEY="..." \
  --dry-run=client -o yaml | kubeseal --format yaml \
  > k3s/infra/secrets/hirewire-scraper-keys.yaml
```

---

## Deployment

### Initial Setup Order

```mermaid
flowchart LR
    A[1. PostgreSQL Secret] --> B[2. PostgreSQL Chart]
    B --> C[3. HireWire Secret]
    C --> D[4. HireWire Chart]
    D --> E[5. Networking Entry]
```

### Step-by-Step

```bash
# 1. Create and commit secrets
# (Follow secrets management steps above)

# 2. Add PostgreSQL to app-of-apps/values.yaml
# (Add infra.postgresql entry)

# 3. Add HireWire to app-of-apps/values.yaml
# (Add apps.hirewire entry)

# 4. Add networking domain
# (Add domains.hirewire entry)

# 5. Commit and push
git add k3s/
git commit -m "Add HireWire infrastructure"
git push

# 6. ArgoCD syncs automatically (or trigger manually)
argocd app sync app-of-apps
```

### Verify Deployment

```bash
# Check pods
kubectl get pods -n hirewire
kubectl get pods -n postgresql

# Check CronJob
kubectl get cronjobs -n hirewire

# View scraper logs (after first run)
kubectl logs -n hirewire -l app.kubernetes.io/name=hirewire-scraper --tail=100

# Test web app
kubectl port-forward -n hirewire svc/hirewire-web 8000:80
curl http://localhost:8000/health
```

---

## Monitoring

### Logs

Logs flow to Loki via existing Promtail setup:

```bash
# Query in Grafana
{namespace="hirewire"} | json
{namespace="hirewire", container="scraper"} | json | level="error"
```

### Metrics

Add ServiceMonitor for web app metrics (optional):

```yaml
# k3s/applications/hirewire/templates/servicemonitor.yaml
{{- if .Values.web.workload.metrics.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: hirewire-web
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: hirewire-web
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
{{- end }}
```

### Alerts (Optional)

```yaml
# k3s/applications/hirewire/templates/prometheusrule.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: hirewire-alerts
spec:
  groups:
    - name: hirewire
      rules:
        - alert: HireWireScraperFailed
          expr: |
            kube_job_status_failed{namespace="hirewire", job_name=~"hirewire-scraper.*"} > 0
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "HireWire scraper job failed"
            description: "Scraper CronJob has failed. Check logs."
        
        - alert: HireWireWebDown
          expr: |
            up{namespace="hirewire", job="hirewire-web"} == 0
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "HireWire web app is down"
```

---

## CI/CD

### GitOps Flow (Primary)

No traditional CI pipelines needed. ArgoCD handles deployment:

1. Push code changes to Git
2. ArgoCD detects changes and syncs
3. Self-heal reverts manual drift

### Container Image Build (GitHub Actions)

> **Note**: HireWire uses a unified Docker image for both the web API and scraper. The same image is deployed with different entrypoints (see `.github/workflows/hirewire.yaml`).

```yaml
# .github/workflows/hirewire.yaml
name: HireWire CI

on:
  push:
    branches: [main]
    paths:
      - 'apps/hirewire/**'
  pull_request:
    paths:
      - 'apps/hirewire/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: apps/hirewire
          push: ${{ github.event_name != 'pull_request' }}
          tags: |
            ghcr.io/${{ github.repository_owner }}/hirewire:${{ github.sha }}
            ghcr.io/${{ github.repository_owner }}/hirewire:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Renovate Integration

Renovate will automatically:
- Update Helm chart dependencies
- Update container image tags (if configured)
- Create PRs for review

---

## Quick Reference

### Commands

```bash
# Trigger manual scrape
kubectl create job --from=cronjob/hirewire-scraper manual-scrape -n hirewire

# View scraper output
kubectl logs -n hirewire job/manual-scrape -f

# Database shell
kubectl exec -it -n postgresql postgresql-0 -- psql -U hirewire -d hirewire

# Restart web app
kubectl rollout restart deployment/hirewire-web -n hirewire

# Force ArgoCD sync
argocd app sync hirewire --force
```

### URLs

| Service | URL |
|---------|-----|
| Web App | https://jobs.subnet75.com |
| Health Check | https://jobs.subnet75.com/health |
| API Docs | https://jobs.subnet75.com/docs |
| Grafana Logs | `{namespace="hirewire"}` query |

---

## Checklist

**Phase 1 MVP:**
- [ ] Create `k3s/infra/postgresql/` chart
- [ ] Create PostgreSQL SealedSecret
- [ ] Create `k3s/applications/hirewire/` chart
- [ ] Create HireWire DB SealedSecret
- [ ] Add entries to `app-of-apps/values.yaml`
- [ ] Add domain to `networking/values.yaml`
- [ ] Build and push container images
- [ ] Verify deployment and health checks

**Phase 2+:**
- [ ] Add scraper API key secrets (ATS integrations)
- [ ] Add ServiceMonitor for metrics
- [ ] Add PrometheusRule for alerts
- [ ] Configure Renovate for image updates
