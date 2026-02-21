# Deploy to Production

Deploy the latest main branch to the production server.

## Server

- **SSH**: `ssh root@167.235.133.87`
- **App directory**: `/opt/pseuno`

## Steps

1. SSH into the server
2. Pull the latest code from main
3. Rebuild and restart containers
4. Verify the deploy succeeded

Run these commands over SSH:

```bash
ssh root@167.235.133.87 "cd /opt/pseuno && git pull && docker compose -f docker-compose.prod.yml up -d --build && docker compose -f docker-compose.prod.yml ps && sleep 5 && curl -s localhost:8000/health"
```

If only the backend changed, you can rebuild just that service:
```bash
ssh root@167.235.133.87 "cd /opt/pseuno && git pull && docker compose -f docker-compose.prod.yml up -d --build backend && sleep 5 && curl -s localhost:8000/health"
```

If only the frontend changed, rebuild just frontend:
```bash
ssh root@167.235.133.87 "cd /opt/pseuno && git pull && docker compose -f docker-compose.prod.yml up -d --build frontend"
```
