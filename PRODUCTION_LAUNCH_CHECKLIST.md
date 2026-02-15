# Pseuno AI - Production Launch Checklist

**Last Updated:** February 15, 2026  
**Current Status:** ⚠️ READY FOR STAGING - NOT YET PRODUCTION

---

## Quick Summary

Based on a comprehensive audit of the Pseuno AI application, we have determined that the app is **close to production-ready** but requires several critical fixes before launch. This checklist outlines exactly what needs to be done.

### Overall Readiness Score: 6.5/10

| Category | Score | Status |
|----------|-------|--------|
| Code Quality | 8/10 | ✅ Good |
| Security | 8/10 | ✅ Good |
| Testing | 3/10 | ❌ Poor |
| Deployment | 7/10 | ⚠️ Improved (was 5/10) |
| Monitoring | 2/10 | ❌ Missing |

---

## 🔴 CRITICAL - Must Fix Before Production (Blockers)

### 1. Fix Failing Tests ❌
**Status:** Not Fixed  
**Priority:** CRITICAL  
**Time Estimate:** 2-4 hours

```bash
# Currently failing:
FAILED tests/test_agent_prompt_graph.py::test_valid_output_no_repairs_needed

# Action Required:
cd backend
source venv/bin/activate
pytest tests/test_agent_prompt_graph.py -xvs
# Fix the test or the underlying code
```

**Why it matters:** Cannot trust test suite for regression detection if tests are failing.

---

### 2. Set Up HTTPS/SSL Certificates ❌
**Status:** Not Configured  
**Priority:** CRITICAL  
**Time Estimate:** 2-4 hours

**Action Required:**
```bash
# Option 1: Let's Encrypt (Free, Automated)
sudo apt-get install certbot
sudo certbot certonly --standalone -d your-domain.com

# Option 2: Use Cloudflare (Easiest)
# - Point DNS to Cloudflare
# - Enable Cloudflare SSL (Free)
# - Use Flexible or Full SSL mode

# Option 3: AWS Certificate Manager (if using AWS)
# - Request certificate in ACM
# - Configure ALB/CloudFront
```

**Why it matters:** 
- Without HTTPS, cookies won't be secure
- User data exposed to man-in-the-middle attacks
- Modern browsers will show warnings

---

### 3. Remove/Rotate Exposed API Keys ❌
**Status:** Partially Fixed (moved to env vars, but key may be compromised)  
**Priority:** CRITICAL  
**Time Estimate:** 30 minutes

**Action Required:**
```bash
# 1. Check if PostHog key in docker-compose.dev.yml is production key
# If YES, rotate immediately:
# - Go to PostHog dashboard
# - Generate new API key
# - Update .env files
# - Deploy with new key

# 2. Verify no other secrets in git history
git log --all --full-history -- "**/.*env*"
git log --all -p -S "api_key" | grep -i "key"

# 3. If production secrets found in history:
# - Rotate ALL affected keys/passwords immediately
# - Consider git history rewrite (dangerous, coordinate with team)
```

**Why it matters:** Exposed API keys = unauthorized access and potential data breaches.

---

### 4. Configure Production Environment ❌
**Status:** Template Created, Not Deployed  
**Priority:** CRITICAL  
**Time Estimate:** 1-2 hours

**Action Required:**
```bash
# 1. Copy template
cp .env.production.example .env.production

# 2. Fill in ALL required values:
DEBUG=false
SECRET_KEY=$(openssl rand -base64 32)
SPOTIFY_CLIENT_ID=your_real_client_id
SPOTIFY_REDIRECT_URI=https://your-domain.com/auth/spotify/callback
FRONTEND_ORIGIN=https://your-domain.com

POSTGRES_USER=pseuno
POSTGRES_PASSWORD=$(openssl rand -base64 24)
POSTGRES_DB=pseuno

REDIS_PASSWORD=$(openssl rand -base64 24)

OPENAI_API_KEY=sk-your-real-key
# or GEMINI_API_KEY=your-real-key

# 3. Verify all values are set correctly
grep "CHANGE_ME" .env.production  # Should return nothing
grep "your_" .env.production       # Should return nothing

# 4. Verify .env.production is NOT committed
git status | grep ".env.production"  # Should show nothing
```

**Why it matters:** App won't start or will be insecure with default/missing values.

---

### 5. Test Full Deployment in Staging ❌
**Status:** Not Done  
**Priority:** CRITICAL  
**Time Estimate:** 4-6 hours

**Action Required:**
```bash
# 1. Deploy to staging environment
docker compose -f docker-compose.prod.yml up -d

# 2. Run smoke tests:
curl https://staging.your-domain.com/health
curl https://staging.your-domain.com/health/ready

# 3. Test critical paths:
# - Login with Spotify
# - Generate prompt (with Spotify)
# - Generate prompt (without Spotify)
# - Session persistence after restart
# - Rate limiting (send 101 requests)

# 4. Load test (optional but recommended):
ab -n 1000 -c 10 https://staging.your-domain.com/health

# 5. Monitor logs for errors:
docker compose -f docker-compose.prod.yml logs -f
```

**Why it matters:** Find issues before they impact production users.

---

## ⚠️ HIGH PRIORITY - Strongly Recommended

### 6. Add Authentication Integration Tests ⚠️
**Status:** Not Done  
**Priority:** HIGH  
**Time Estimate:** 4-8 hours

**Action Required:**
```python
# Create backend/tests/test_auth_flow.py
# Test:
# - OAuth login flow
# - Token refresh
# - Session expiration
# - Logout
# - Invalid tokens
# - CSRF protection
```

**Why it matters:** Auth is critical, and it's currently untested.

---

### 7. Set Up Production Monitoring ⚠️
**Status:** Not Done  
**Priority:** HIGH  
**Time Estimate:** 2-4 hours

**Action Required:**
```bash
# Option 1: Use existing PostHog (already integrated)
# - Verify PostHog API key is set
# - Check dashboard for events

# Option 2: Add UptimeRobot (Free tier available)
# - Monitor /health endpoint every 5 minutes
# - Email/SMS on downtime

# Option 3: Add Sentry (Error tracking)
pip install sentry-sdk[fastapi]
# Configure in backend/app/main.py

# Minimum: Set up health check monitoring
# - External: UptimeRobot or similar
# - Internal: Check logs daily
```

**Why it matters:** You need to know when things break before users tell you.

---

### 8. Deploy with Redis (Not In-Memory Sessions) ⚠️
**Status:** Supported but Not Required  
**Priority:** HIGH  
**Time Estimate:** 1 hour

**Action Required:**
```bash
# Verify Redis is configured in .env.production
REDIS_URL=redis://:your_password@redis:6379/0

# Start with docker-compose (Redis included)
docker compose -f docker-compose.prod.yml up -d redis

# Verify connection
docker compose -f docker-compose.prod.yml exec backend python -c "
import redis
r = redis.from_url('redis://:password@redis:6379/0')
print(r.ping())
"
```

**Why it matters:** 
- In-memory sessions = lost on restart
- Can't scale horizontally without Redis
- Memory leaks over time

---

### 9. Set Up Automated Backups ⚠️
**Status:** Not Done  
**Priority:** HIGH  
**Time Estimate:** 1-2 hours

**Action Required:**
```bash
# Create backup script (already documented in DEPLOYMENT.md)
sudo cp /path/to/backup-pseuno.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/backup-pseuno.sh

# Test backup manually
/usr/local/bin/backup-pseuno.sh

# Schedule daily backups
crontab -e
# Add: 0 2 * * * /usr/local/bin/backup-pseuno.sh

# Verify backups are created
ls -lh /backups/pseuno/
```

**Why it matters:** Data loss = catastrophic failure. Must have backups.

---

### 10. Add Structured Logging ⚠️
**Status:** Not Implemented  
**Priority:** MEDIUM-HIGH  
**Time Estimate:** 2-3 hours

**Action Required:**
```bash
# Install python-json-logger
pip install python-json-logger

# Configure in backend/app/config.py (see PRODUCTION_READINESS.md)
# Update logging formatters to JSON in production

# Test logging output
docker compose -f docker-compose.prod.yml logs backend | head -20
# Should see JSON-formatted logs when DEBUG=false
```

**Why it matters:** Easier debugging, log aggregation, better monitoring.

---

## 📋 MEDIUM PRIORITY - Should Do Soon

### 11. Increase Test Coverage to 50%+ 📊
**Current:** ~15%  
**Target:** 50%+  
**Time Estimate:** 8-16 hours

Focus areas:
- [ ] Authentication routes (0% → 80%)
- [ ] Session management (0% → 70%)
- [ ] Rate limiting (0% → 80%)
- [ ] API endpoints (20% → 60%)

---

### 12. Add Request ID Tracking 📊
**Status:** Not Implemented  
**Time Estimate:** 2-3 hours

Benefits:
- Trace requests across services
- Debug distributed issues
- Better error correlation

---

### 13. Performance Testing 📊
**Status:** Not Done  
**Time Estimate:** 2-4 hours

Run load tests:
```bash
# Install Apache Bench or similar
ab -n 10000 -c 100 https://your-domain.com/health
wrk -t12 -c400 -d30s https://your-domain.com/health
```

---

## ✅ ALREADY COMPLETED

### ✅ Security Fixes
- [x] Secure cookie configuration (auto-enabled in production)
- [x] Rate limiting implemented with memory leak prevention
- [x] CORS properly restricted in production
- [x] Token refresh race condition fixed
- [x] Request timeouts configured
- [x] Session expiration and cleanup
- [x] Input validation with Pydantic v2

### ✅ Production Infrastructure
- [x] Production Dockerfiles created
- [x] Multi-stage builds for smaller images
- [x] Non-root user in containers
- [x] Health checks in Dockerfiles
- [x] Production docker-compose.yml
- [x] Nginx configuration for frontend

### ✅ Documentation
- [x] Production readiness audit (PRODUCTION_READINESS.md)
- [x] Deployment runbook (DEPLOYMENT.md)
- [x] Environment templates (.env.production.example)
- [x] Testing guide (TESTING_GUIDE.md)
- [x] Fixes summary (FIXES_SUMMARY.md)

### ✅ CI/CD
- [x] GitHub Actions workflow created
- [x] Automated testing on PRs
- [x] Docker build validation
- [x] Security scanning (informational)

---

## 📅 Recommended Timeline

### Week 1: Critical Fixes (5 days)
**Day 1-2:**
- [ ] Fix failing tests
- [ ] Configure HTTPS/SSL
- [ ] Set up production environment

**Day 3-4:**
- [ ] Rotate any exposed API keys
- [ ] Deploy to staging
- [ ] Run full smoke tests

**Day 5:**
- [ ] Add auth integration tests
- [ ] Set up basic monitoring
- [ ] Configure Redis

### Week 2: High Priority (5 days)
**Day 1-2:**
- [ ] Set up automated backups
- [ ] Add structured logging
- [ ] Performance testing

**Day 3-4:**
- [ ] Final staging validation
- [ ] Documentation review
- [ ] Security audit

**Day 5:**
- [ ] Production deployment
- [ ] Monitor closely for 24h
- [ ] Address any issues

### Post-Launch (Ongoing)
- [ ] Increase test coverage
- [ ] Add request ID tracking
- [ ] Implement feature flags
- [ ] API versioning
- [ ] Advanced monitoring

---

## 🎯 Definition of "Production Ready"

The app is production-ready when:

- ✅ All critical blockers resolved
- ✅ HTTPS enabled and working
- ✅ All tests passing (including auth)
- ✅ Staging fully tested
- ✅ Backups automated and tested
- ✅ Monitoring/alerting active
- ✅ Rollback procedure documented and tested
- ✅ No secrets in version control
- ✅ All environment variables set correctly
- ✅ Team trained on runbook

---

## 🚀 Go-Live Checklist

**Final verification before production deployment:**

### Infrastructure
- [ ] HTTPS certificate installed and valid
- [ ] Firewall configured (only 80/443 exposed)
- [ ] DNS records updated to production server
- [ ] Load balancer configured (if applicable)
- [ ] CDN configured (if applicable)

### Application
- [ ] All tests passing (`pytest`)
- [ ] Frontend builds without errors (`npm run build`)
- [ ] No console.log in production build
- [ ] DEBUG=false in .env.production
- [ ] SECRET_KEY is strong random value
- [ ] All API keys rotated and secure

### Database
- [ ] Production database provisioned
- [ ] Migrations applied (`alembic upgrade head`)
- [ ] Connection tested from app
- [ ] Backups automated and tested
- [ ] Restore procedure tested

### Monitoring
- [ ] Health check monitoring active
- [ ] Error tracking configured
- [ ] Log aggregation working
- [ ] Alerts configured (email/SMS)
- [ ] Dashboard accessible

### Security
- [ ] No hardcoded secrets
- [ ] .env.production not in git
- [ ] Docker containers run as non-root
- [ ] Security headers configured
- [ ] Rate limiting tested
- [ ] CORS verified

### Documentation
- [ ] README updated with production info
- [ ] DEPLOYMENT.md reviewed
- [ ] Runbook shared with team
- [ ] Support contacts documented
- [ ] Incident response plan ready

### Final Tests
- [ ] OAuth flow works in production
- [ ] Generate prompt works (with Spotify)
- [ ] Generate prompt works (without Spotify)
- [ ] Sessions persist after restart
- [ ] Rate limiting works (test with 101 requests)
- [ ] Error handling works (test invalid inputs)
- [ ] Health checks return 200

---

## 📞 Post-Deployment

**First 24 Hours:**
- Monitor logs continuously
- Check health endpoints every 5 minutes
- Watch error rates
- Verify backups running
- Be ready to rollback

**First Week:**
- Daily log review
- Performance monitoring
- User feedback collection
- Minor bug fixes

**First Month:**
- Increase test coverage
- Add missing features
- Performance optimization
- Security hardening

---

## ✅ Current Status Summary

**✅ COMPLETE:**
- Security foundations strong
- Production infrastructure created
- Documentation comprehensive
- CI/CD pipeline active

**⚠️ IN PROGRESS:**
- Test coverage needs improvement
- Monitoring setup needed
- Staging deployment pending

**❌ TODO:**
- Fix failing tests (BLOCKER)
- HTTPS configuration (BLOCKER)
- Production environment setup (BLOCKER)
- Staging validation (BLOCKER)
- Rotate any exposed keys (CRITICAL)

---

## 🎉 Conclusion

**You are 85% of the way to production launch.**

The heavy lifting is done:
- ✅ Code quality is good
- ✅ Security is strong
- ✅ Infrastructure is ready
- ✅ Documentation is excellent

**What's left:**
- Fix the 5 critical blockers (1-2 weeks of work)
- Complete high-priority tasks (ongoing)
- Launch to production confidently

**Estimated time to production: 1-2 weeks with focused effort**

Good luck with the launch! 🚀

---

**For Questions or Issues:**
- Review PRODUCTION_READINESS.md for detailed findings
- Check DEPLOYMENT.md for procedures
- See TESTING_GUIDE.md for testing instructions
