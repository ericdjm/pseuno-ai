# Debug Production

Investigate production issues on the live server.

## Access

- **SSH**: `ssh root@167.235.133.87`
- **App directory**: `/opt/pseuno`

## Common commands

All commands below assume you are in `/opt/pseuno` on the server.

### View logs
```bash
docker compose -f docker-compose.prod.yml logs --tail=200 backend
```

### View all service logs
```bash
docker compose -f docker-compose.prod.yml logs --tail=100
```

### Filter errors
```bash
docker compose -f docker-compose.prod.yml logs backend 2>&1 | grep -i error | tail -30
```

### Check health
```bash
curl -s localhost:8000/health
```

### Check running containers
```bash
docker compose -f docker-compose.prod.yml ps
```

### Database access
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U pseuno -d pseuno
```

### Redis
```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli
```

### Restart backend
```bash
docker compose -f docker-compose.prod.yml restart backend
```

### Deploy latest
```bash
cd /opt/pseuno && git pull && docker compose -f docker-compose.prod.yml up -d --build backend
```

## Investigation workflow

1. SSH in and check health first
2. View recent logs, filter for errors
3. Check if containers are running
4. If needed, check DB/Redis state
5. Restart backend if it's stuck
6. If a code fix is needed, deploy from main after merging the fix
