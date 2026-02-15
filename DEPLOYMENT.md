# Pseuno AI - Production Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Deployment Steps](#deployment-steps)
4. [Health Checks](#health-checks)
5. [Monitoring](#monitoring)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)
8. [Security Checklist](#security-checklist)

---

## Prerequisites

### Infrastructure Requirements
- ✅ Server with Docker & Docker Compose installed (v20.10+)
- ✅ Domain name with DNS configured
- ✅ SSL/TLS certificate (Let's Encrypt recommended)
- ✅ PostgreSQL 16+ database provisioned (or use Docker Compose)
- ✅ Redis 7+ instance provisioned (or use Docker Compose)
- ✅ Minimum 2GB RAM, 2 CPU cores, 20GB disk space

### External Services
- ✅ Spotify Developer App configured with production callback URL
- ✅ OpenAI or Google Gemini API key
- ✅ (Optional) PostHog account for analytics

### Access Requirements
- ✅ SSH access to production server
- ✅ Git repository access
- ✅ Docker registry access (if using private registry)

---

## Environment Setup

### 1. Clone Repository on Production Server

```bash
# SSH into production server
ssh user@your-production-server

# Clone repository
git clone https://github.com/ericdjm/pseuno-ai.git
cd pseuno-ai

# Checkout the release version
git checkout tags/v1.0.0  # or specific commit/branch
```

### 2. Create Production Environment File

```bash
# Copy template
cp .env.production.example .env.production

# Edit with production values
nano .env.production
```

### 3. Configure Critical Environment Variables

**REQUIRED Settings:**
```env
# Generate strong secret key
SECRET_KEY=$(openssl rand -base64 32)

# Set production mode
DEBUG=false

# Configure Spotify OAuth
SPOTIFY_CLIENT_ID=your_production_client_id
SPOTIFY_REDIRECT_URI=https://your-domain.com/auth/spotify/callback

# Set frontend origin
FRONTEND_ORIGIN=https://your-domain.com

# Database credentials
POSTGRES_USER=pseuno
POSTGRES_PASSWORD=$(openssl rand -base64 24)
POSTGRES_DB=pseuno

# Redis credentials
REDIS_PASSWORD=$(openssl rand -base64 24)

# LLM API (choose one)
OPENAI_API_KEY=sk-...
# OR
# GEMINI_API_KEY=...
```

**SECURITY NOTE:** Never commit `.env.production` to version control!

---

## Deployment Steps

### Option A: Docker Compose Deployment (Recommended for Small/Medium Scale)

#### Step 1: Build Images

```bash
# Build all services
docker compose -f docker-compose.prod.yml build

# Or build individually
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml build frontend
```

#### Step 2: Run Database Migrations

```bash
# Run migrations before starting services
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Verify migrations
docker compose -f docker-compose.prod.yml run --rm backend alembic current
```

#### Step 3: Start Services

```bash
# Start all services in detached mode
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps
```

#### Step 4: Verify Deployment

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs -f backend

# Wait for "Application startup complete" message
```

### Option B: Manual Docker Deployment

#### Step 1: Create Network

```bash
docker network create pseuno-network
```

#### Step 2: Start PostgreSQL

```bash
docker run -d \
  --name pseuno-postgres \
  --network pseuno-network \
  -e POSTGRES_USER=pseuno \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=pseuno \
  -v pseuno-postgres-data:/var/lib/postgresql/data \
  --restart unless-stopped \
  postgres:16-alpine
```

#### Step 3: Start Redis

```bash
docker run -d \
  --name pseuno-redis \
  --network pseuno-network \
  -v pseuno-redis-data:/data \
  --restart unless-stopped \
  redis:7-alpine redis-server --appendonly yes --requirepass your_redis_password
```

#### Step 4: Run Migrations

```bash
docker run --rm \
  --network pseuno-network \
  -e DATABASE_URL=postgresql+psycopg://pseuno:your_password@pseuno-postgres:5432/pseuno \
  -v $(pwd)/backend:/app \
  pseuno-backend:latest \
  alembic upgrade head
```

#### Step 5: Start Backend

```bash
docker run -d \
  --name pseuno-backend \
  --network pseuno-network \
  --env-file .env.production \
  -e DATABASE_URL=postgresql+psycopg://pseuno:your_password@pseuno-postgres:5432/pseuno \
  -e REDIS_URL=redis://:your_redis_password@pseuno-redis:6379/0 \
  --restart unless-stopped \
  pseuno-backend:latest
```

#### Step 6: Start Frontend

```bash
docker run -d \
  --name pseuno-frontend \
  --network pseuno-network \
  -p 80:80 \
  --restart unless-stopped \
  pseuno-frontend:latest
```

---

## Health Checks

### 1. Application Health

```bash
# Basic health check
curl https://your-domain.com/health

# Expected response:
# {"status":"healthy","service":"pseuno-ai","version":"1.0.0"}
```

### 2. Readiness Check (All Dependencies)

```bash
# Deep health check
curl https://your-domain.com/health/ready

# Expected response:
# {
#   "status": "healthy",
#   "checks": {
#     "database": "healthy",
#     "redis": "healthy",
#     "sessions": "healthy (0 active)"
#   }
# }
```

### 3. API Documentation

```bash
# Access Swagger UI
open https://your-domain.com/docs

# Access ReDoc
open https://your-domain.com/redoc
```

### 4. End-to-End Test

1. Open browser to `https://your-domain.com`
2. Click "Login with Spotify"
3. Authorize the application
4. Verify profile loads correctly
5. Adjust sliders and input theme
6. Click "Generate Prompt + Lyrics"
7. Verify prompt and lyrics are generated
8. Check browser console for errors (should be none)

---

## Monitoring

### 1. View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Backend only
docker compose -f docker-compose.prod.yml logs -f backend

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 backend

# Follow logs with timestamp
docker compose -f docker-compose.prod.yml logs -f --timestamps backend
```

### 2. Check Service Status

```bash
# Docker Compose
docker compose -f docker-compose.prod.yml ps

# Individual containers
docker ps | grep pseuno
```

### 3. Resource Usage

```bash
# Real-time stats
docker stats

# Disk usage
docker system df

# Specific container stats
docker stats pseuno-backend pseuno-frontend
```

### 4. Database Health

```bash
# Connect to database
docker compose -f docker-compose.prod.yml exec postgres psql -U pseuno -d pseuno

# Check connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'pseuno';

# Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 5. Redis Monitoring

```bash
# Connect to Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli -a your_redis_password

# Check info
INFO

# Monitor commands in real-time
MONITOR

# Check memory usage
INFO memory
```

---

## Rollback Procedures

### Scenario 1: Application Error (Code Issue)

```bash
# 1. Stop current deployment
docker compose -f docker-compose.prod.yml down

# 2. Checkout previous version
git log --oneline -10  # Find previous commit
git checkout <previous-commit-hash>

# 3. Rebuild and restart
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 4. Verify health
curl https://your-domain.com/health
```

### Scenario 2: Database Migration Issue

```bash
# 1. Rollback database migration
docker compose -f docker-compose.prod.yml run --rm backend alembic downgrade -1

# 2. Verify current version
docker compose -f docker-compose.prod.yml run --rm backend alembic current

# 3. Restart services
docker compose -f docker-compose.prod.yml restart backend
```

### Scenario 3: Complete System Failure

```bash
# 1. Stop all services
docker compose -f docker-compose.prod.yml down

# 2. Restore from backup
docker run --rm \
  -v pseuno-postgres-data:/var/lib/postgresql/data \
  -v $(pwd)/backups:/backups \
  postgres:16-alpine \
  psql -U pseuno -d pseuno -f /backups/backup_YYYYMMDD.sql

# 3. Revert code to last known good version
git checkout tags/v1.0.0  # or last stable version

# 4. Rebuild and restart
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

---

## Troubleshooting

### Issue: Service Won't Start

```bash
# Check logs for errors
docker compose -f docker-compose.prod.yml logs backend

# Common causes:
# - Missing environment variables
# - Database connection failed
# - Port already in use
# - Invalid configuration

# Verify environment
docker compose -f docker-compose.prod.yml config
```

### Issue: Database Connection Failed

```bash
# Check PostgreSQL is running
docker compose -f docker-compose.prod.yml ps postgres

# Verify credentials
docker compose -f docker-compose.prod.yml exec backend env | grep DATABASE_URL

# Test connection manually
docker compose -f docker-compose.prod.yml exec postgres psql -U pseuno -d pseuno -c "SELECT 1;"

# Check logs
docker compose -f docker-compose.prod.yml logs postgres
```

### Issue: Redis Connection Failed

```bash
# Check Redis is running
docker compose -f docker-compose.prod.yml ps redis

# Test connection
docker compose -f docker-compose.prod.yml exec redis redis-cli -a your_password ping

# Check logs
docker compose -f docker-compose.prod.yml logs redis
```

### Issue: OAuth Flow Fails

```bash
# Common causes:
# 1. SPOTIFY_REDIRECT_URI mismatch
# 2. FRONTEND_ORIGIN incorrect
# 3. Spotify app not configured

# Verify configuration
docker compose -f docker-compose.prod.yml exec backend env | grep SPOTIFY

# Check Spotify Developer Dashboard:
# - Redirect URI must match exactly: https://your-domain.com/auth/spotify/callback
# - App must be set to "Development Mode" or "Production Mode"
```

### Issue: High Memory Usage

```bash
# Check memory usage
docker stats --no-stream

# Check session count (in-memory sessions can grow)
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.services.session_store import session_store
print(f'Active sessions: {len(session_store._sessions)}')
"

# Recommendation: Ensure Redis is configured for production
# Sessions should be stored in Redis, not in-memory
```

### Issue: Rate Limiting Too Aggressive

```bash
# Check rate limit configuration
docker compose -f docker-compose.prod.yml exec backend env | grep RATE_LIMIT

# Adjust in .env.production:
RATE_LIMIT_REQUESTS=200  # Increase from default 100
RATE_LIMIT_WINDOW=60

# Restart backend
docker compose -f docker-compose.prod.yml restart backend
```

---

## Database Backup & Restore

### Automated Backups

```bash
# Create backup script
cat > /usr/local/bin/backup-pseuno.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/pseuno"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
docker compose -f /path/to/pseuno-ai/docker-compose.prod.yml exec -T postgres \
  pg_dump -U pseuno pseuno > $BACKUP_DIR/pseuno_$TIMESTAMP.sql

# Compress
gzip $BACKUP_DIR/pseuno_$TIMESTAMP.sql

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: pseuno_$TIMESTAMP.sql.gz"
EOF

chmod +x /usr/local/bin/backup-pseuno.sh
```

### Schedule Daily Backups (Cron)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /usr/local/bin/backup-pseuno.sh >> /var/log/pseuno-backup.log 2>&1
```

### Manual Backup

```bash
# Backup database
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U pseuno pseuno > backup_$(date +%Y%m%d).sql

# Backup Redis (if not using appendonly)
docker compose -f docker-compose.prod.yml exec redis redis-cli -a your_password SAVE
docker cp pseuno-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### Restore from Backup

```bash
# Restore database
cat backup_20260215.sql | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U pseuno -d pseuno

# Or restore from gzipped backup
zcat backup_20260215.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U pseuno -d pseuno
```

---

## Security Checklist

Before going live, verify:

- [ ] `DEBUG=false` in `.env.production`
- [ ] Strong `SECRET_KEY` generated (min 32 chars)
- [ ] HTTPS enabled on domain (SSL certificate installed)
- [ ] Firewall configured (only ports 80/443 exposed)
- [ ] Database credentials changed from defaults
- [ ] Redis password set
- [ ] Spotify redirect URI updated to production URL
- [ ] PostHog API key moved to environment variable (not hardcoded)
- [ ] Docker containers running as non-root user
- [ ] `.env.production` excluded from version control
- [ ] All secrets stored securely (not in code)
- [ ] CORS configured for production domain only
- [ ] Rate limiting enabled and tested
- [ ] Session cookies set to `Secure` and `HttpOnly`
- [ ] Database backups automated
- [ ] Monitoring and alerting configured

---

## Performance Optimization

### 1. Enable Connection Pooling

Already configured in SQLAlchemy - verify settings:

```python
# In backend/app/database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # Adjust based on load
    max_overflow=20,       # Extra connections if needed
    pool_pre_ping=True,    # Verify connections before use
)
```

### 2. Configure Nginx Caching (if using reverse proxy)

```nginx
# Add to nginx.conf
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g inactive=60m;

location /api/ {
    proxy_cache api_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_key "$scheme$request_method$host$request_uri";
}
```

### 3. Monitor Performance

```bash
# Check response times
time curl https://your-domain.com/health

# Monitor slow queries (PostgreSQL)
docker compose -f docker-compose.prod.yml exec postgres psql -U pseuno -d pseuno -c "
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
"
```

---

## Scaling Considerations

### Horizontal Scaling (Multiple Instances)

1. **Database:** Already centralized (PostgreSQL)
2. **Sessions:** Move to Redis (already supported)
3. **Load Balancer:** Add Nginx/HAProxy in front
4. **File Storage:** Use S3 for any uploaded files (if applicable)

### Vertical Scaling (Larger Instance)

1. **Increase RAM:** For more sessions and cache
2. **More CPU:** For faster LLM processing
3. **Faster Disk:** SSD for database

---

## Support & Maintenance

### Regular Maintenance Tasks

**Daily:**
- Check logs for errors
- Verify health endpoints
- Monitor disk usage

**Weekly:**
- Review performance metrics
- Check for security updates
- Verify backups are running

**Monthly:**
- Update dependencies
- Review and rotate logs
- Security audit

### Getting Help

1. Check logs: `docker compose -f docker-compose.prod.yml logs`
2. Review documentation: `README.md`, `PRODUCTION_READINESS.md`
3. Search issues: https://github.com/ericdjm/pseuno-ai/issues
4. Contact support: [your-support-email]

---

## Appendix: Quick Reference Commands

```bash
# Start production services
docker compose -f docker-compose.prod.yml up -d

# Stop production services
docker compose -f docker-compose.prod.yml down

# View logs
docker compose -f docker-compose.prod.yml logs -f backend

# Restart a service
docker compose -f docker-compose.prod.yml restart backend

# Run migrations
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Backup database
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U pseuno pseuno > backup.sql

# Check status
docker compose -f docker-compose.prod.yml ps

# View resource usage
docker stats
```

---

**Last Updated:** February 15, 2026  
**Version:** 1.0.0
