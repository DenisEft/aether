# Production Deployment Specification for Aether SaaS Platform

This document outlines the production deployment architecture, configuration, and operational procedures for the Aether SaaS platform. It serves as a comprehensive guide for DevOps and SRE teams managing the production environment.

## 1. Production Architecture

The production architecture of the Aether platform is designed for high availability, scalability, and security. Here's a detailed overview of its components and interactions:

### Components

1. **Nginx Reverse Proxy**
   - Acts as the entry point for all external traffic
   - Terminates SSL connections
   - Load balances requests to backend services
   - Handles WebSocket upgrades
   - Implements rate limiting and security headers

2. **Backend Services**
   - Main application logic
   - REST API endpoints
   - WebSocket handlers for real-time communication
   - Celery workers for background tasks

3. **PostgreSQL Database**
   - Primary data store
   - Supports read replicas for scaling read-heavy operations
   - Implements point-in-time recovery for backups

4. **Redis**
   - Caching layer
   - Session storage
   - Message broker for Celery
   - Pub/Sub for real-time notifications

5. **Celery Workers**
   - Background task processing
   - Three dedicated queues:
     - `default`: General background tasks
     - `ai`: AI/ML related computations
     - `long_running`: Long-running operations with timeout handling

6. **Frontend Static Assets**
   - Hosted via CDN or directly through Nginx
   - Served with appropriate caching headers

### Communication Flow

```
[External Client] --> [Nginx Reverse Proxy] --> [Backend Service]
                                   |
                                   v
                      [PostgreSQL/Redis/Celery Workers]
                                   |
                                   v
                    [Frontend Static Assets - CDN/Nginx]
```

## 2. Docker Compose Production

The production environment uses a comprehensive Docker Compose configuration to manage all services with appropriate resource limits, health checks, and restart policies.

### Production Docker Compose File (`docker-compose.prod.yml`)

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: aether-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    depends_on:
      - backend
    networks:
      - aether-net

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: aether-backend
    restart: always
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/aether_db
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - aether-net
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  postgres:
    image: postgres:15-alpine
    container_name: aether-postgres
    restart: always
    environment:
      - POSTGRES_DB=aether_db
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - aether-net
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d aether_db"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: aether-redis
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - aether-net
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-default:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: aether-celery-default
    restart: always
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/aether_db
      - REDIS_URL=redis://redis:6379/0
    command: celery -A aether.celery_app worker --loglevel=INFO -Q default
    depends_on:
      - redis
      - postgres
    networks:
      - aether-net
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  celery-ai:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: aether-celery-ai
    restart: always
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5342/aether_db
      - REDIS_URL=redis://redis:6379/0
    command: celery -A aether.celery_app worker --loglevel=INFO -Q ai
    depends_on:
      - redis
      - postgres
    networks:
      - aether-net
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  celery-long-running:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: aether-celery-long-running
    restart: always
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/aether_db
      - REDIS_URL=redis://redis:6379/0
    command: celery -A aether.celery_app worker --loglevel=INFO -Q long_running
    depends_on:
      - redis
      - postgres
    networks:
      - aether-net
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

volumes:
  postgres_data:
  redis_data:

networks:
  aether-net:
    driver: bridge
```

## 3. Nginx Configuration

The Nginx configuration handles SSL termination, routing, rate limiting, and CORS headers.

### Nginx Configuration File (`nginx/nginx.conf`)

```nginx
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
        ssl_trusted_certificate /etc/letsencrypt/live/yourdomain.com/chain.pem;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header X-Content-Type-Options "nosniff" always;

        # Rate limiting
        limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
        limit_req zone=api burst=20 nodelay;

        # CORS headers
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization, X-Requested-With" always;
        add_header Access-Control-Max-Age 86400 always;

        # WebSocket upgrade
        location /ws {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        # API routes
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Static assets
        location /static/ {
            alias /path/to/static/files/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Root path for frontend
        location / {
            root /path/to/frontend/dist;
            try_files $uri $uri/ /index.html;
        }
    }
}
```

## 4. Environment Variables

All environment variables are defined in `.env.template` and should be copied to `.env` in the production environment.

### Full List of Environment Variables

| Variable Name | Description | Default Value |
|----------------|-------------|---------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@postgres:5432/aether_db` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `REDIS_PASSWORD` | Redis password | `password` |
| `JWT_SECRET` | Secret for JWT token signing | `secret_key` |
| `ENCRYPTION_KEY` | Key for data encryption | `encryption_key` |
| `API_KEY` | Internal API key | `internal_api_key` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://redis:6379/0` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DEBUG` | Debug mode flag | `False` |
| `ALLOWED_HOSTS` | Allowed hosts for Django | `*` |
| `SECRET_KEY` | Django secret key | `django_secret_key` |

## 5. Secret Management

Secrets are managed using a combination of encrypted files, secure storage services, and environment variable injection.

### Secret Storage Strategy

1. **Database Credentials**
   - Stored in `secrets/postgres.yaml` (encrypted with Ansible Vault)
   - Rotated monthly or on personnel changes

2. **API Keys**
   - Managed via HashiCorp Vault
   - Automated rotation via scripts

3. **Encryption Keys**
   - Generated upon deployment
   - Stored in Kubernetes secrets or encrypted file system

4. **JWT Secrets**
   - Randomly generated upon deployment
   - Rotated annually or on security incidents

### Rotation Procedure

1. Generate new secrets using appropriate tools:
   ```bash
   # For generating new passwords
   openssl rand -base64 32 > secrets/passwords.txt
   ```
2. Update encrypted files and redeploy services
3. Perform rolling updates to ensure no downtime

## 6. Scaling Strategy

### Vertical Scaling vs Horizontal Scaling

- **Vertical Scaling**:
  - Increase CPU/memory of existing instances
  - Used for small-medium deployments
  - Limited by hardware constraints

- **Horizontal Scaling**:
  - Add more instances of services
  - Preferred for large-scale deployments
  - Enables better load distribution

### Worker Scaling

1. **Default Queue Workers**
   - Scale based on task volume
   - Add more workers if tasks queue up for > 2 minutes

2. **AI Queue Workers**
   - Scale based on AI model compute usage
   - Use dedicated GPU-enabled machines

3. **Long Running Tasks**
   - Use separate worker pool
   - Implement timeout handling and retry logic

### Read Replicas

- PostgreSQL supports read replicas
- Used to offload read-heavy queries
- Configured with specific replication settings

## 7. Backup Strategy

### Daily Backups

1. **PostgreSQL**
   ```bash
   pg_dump -h postgres -U user -d aether_db > backups/$(date +%Y-%m-%d_%H-%M-%S)_db.sql
   ```
   - Retention: 30 days
   - Stored in encrypted S3 bucket

2. **Redis**
   ```bash
   redis-cli bgsave
   # RDB file stored locally, then synced to S3
   ```

### Restore Procedure

1. **Database Restoration**
   ```bash
   psql -h postgres -U user -d aether_db < backups/backup.sql
   ```

2. **Redis Restoration**
   ```bash
   # Restart Redis server and let it load RDB file
   systemctl restart redis
   ```

## 8. Monitoring & Alerting

### Prometheus Metrics

Metrics collected include:
- HTTP request duration
- Database query times
- CPU/memory usage
- Celery task completion times
- Redis connection stats

### Grafana Dashboards

Pre-configured dashboards for:
- System resource usage
- Application performance
- Database health
- Celery task queues

### Alerting in Telegram

Alerts are configured using Prometheus Alertmanager and sent via Telegram webhook:
- Database connection errors
- High CPU/memory usage (> 80%)
- Long-running Celery tasks (> 1 hour)
- Service downtime (> 5 minutes)

## 9. Logging

### Structured JSON Logs

All applications log in structured JSON format:
```json
{
  "timestamp": "2026-07-02T14:23:00Z",
  "level": "INFO",
  "message": "User login successful",
  "service": "backend",
  "request_id": "abc123"
}
```

### Log Aggregation

- Using Loki for log aggregation
- Promtail agent deployed on each host
- Grafana dashboard for log viewing

### Log Levels

- `DEBUG`: Development and troubleshooting
- `INFO`: General operational information
- `WARNING`: Potential issues or errors
- `ERROR`: Error conditions requiring action
- `CRITICAL`: Severe errors causing service degradation

## 10. Disaster Recovery

### RPO/RTO Targets

- **Recovery Point Objective (RPO)**: 1 hour
- **Recovery Time Objective (RTO)**: 2 hours

### Restore Procedure

1. **Initial Recovery Steps**
   - Identify impacted services
   - Isolate the failure using monitoring tools
   - Rollback to last known stable version if necessary

2. **Data Recovery**
   - Restore from backups stored in S3
   - Validate data consistency
   - Rebuild any corrupted components

3. **Failover Plan**
   - Failover to standby infrastructure
   - Redirect traffic via DNS or load balancer
   - Confirm service health post-failover

### Testing

Regular disaster recovery drills conducted monthly to verify:
- Backup restoration procedures
- Failover timing
- Data integrity

## 11. Security Hardening

### Firewall Configuration

- SSH: 22/tcp (restricted to specific IPs)
- Nginx: 80/443/tcp
- PostgreSQL: 5432/tcp (restricted to internal network)
- Redis: 6379/tcp (restricted to internal network)

### Container Security

- Run containers as non-root user
- Mount filesystems as read-only where possible
- Enable network isolation using Docker networks
- Use minimal base images (Alpine Linux)

### Network Isolation

- Services communicate via Docker networks
- External access routed through Nginx reverse proxy
- No direct exposure of internal services

## 12. Upgrade Procedure

### Rolling Updates

- Services are updated using rolling updates
- New containers are started before old ones are stopped
- Health checks ensure new instances are healthy before deactivating old ones

### Migration Handling

- Migrations run automatically during deployment
- Downtime < 30 seconds for standard migrations
- Rollback plan implemented for major migrations

### Deployment Steps

```bash
# Pull latest code
git pull origin production

# Check and build new images
docker-compose -f docker-compose.prod.yml build

# Run health checks
docker-compose -f docker-compose.prod.yml up -d

# Validate new deployment
curl -f http://localhost:8000/health
```

## 13. Multi-Environment

### Development Environment

- Single instance deployment
- Shared resources
- Minimal monitoring

### Staging Environment

- Similar to production but with reduced resources
- Full service stack
- Used for user acceptance testing

### Production Environment

- Dedicated resources
- Full monitoring and alerting
- Secure and hardened configuration

Each environment uses its own Docker Compose file with specific configurations:
- `docker-compose.dev.yml` for development
- `docker-compose.staging.yml` for staging
- `docker-compose.prod.yml` for production

### Environment-Specific Variables

Each environment has its own set of variables:
- Database URLs with specific credentials
- API keys for external services
- Service endpoints for integration tests

This specification ensures a robust, scalable, and secure production deployment of the Aether SaaS platform. It provides clear guidelines for configuration, operational procedures, and maintenance practices.
