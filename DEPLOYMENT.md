# Deployment Guide

## Deployment Options

### 1. Local Development Machine

**Best for:** Testing and personal use

**Steps:**
```bash
# Clone repository
git clone https://github.com/groupthinking/MyXstack.git
cd MyXstack

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Build and run
npm run build
npm start
```

**Pros:**
- Simple setup
- Easy debugging
- No hosting costs

**Cons:**
- Must keep computer running
- No remote access
- Not scalable

### 2. Cloud VM (AWS EC2, Google Compute, DigitalOcean)

**Best for:** Production use, 24/7 operation

#### Setup on Ubuntu/Debian

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Clone and setup
git clone https://github.com/groupthinking/MyXstack.git
cd MyXstack
npm install
npm run build

# Create environment file
nano .env
# Paste your credentials and save

# Test run
npm start
```

#### Run as a Service (systemd)

Create `/etc/systemd/system/myxstack.service`:

```ini
[Unit]
Description=MyXstack Autonomous AI Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/MyXstack
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10
StandardOutput=append:/var/log/myxstack/output.log
StandardError=append:/var/log/myxstack/error.log
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
# Create log directory
sudo mkdir -p /var/log/myxstack
sudo chown ubuntu:ubuntu /var/log/myxstack

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable myxstack
sudo systemctl start myxstack

# Check status
sudo systemctl status myxstack

# View logs
sudo journalctl -u myxstack -f
```

### 3. Docker Container

**Best for:** Consistent deployment, easy updates

#### Dockerfile

Create `Dockerfile`:

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source
COPY . .

# Build TypeScript
RUN npm run build

# Run as non-root user
USER node

CMD ["npm", "start"]
```

Create `.dockerignore`:

```
node_modules
dist
.env
.git
*.md
```

#### Build and Run

```bash
# Build image
docker build -t myxstack:latest .

# Run container
docker run -d \
  --name myxstack-agent \
  --restart unless-stopped \
  -e X_API_KEY="your_key" \
  -e X_API_SECRET="your_secret" \
  -e X_ACCESS_TOKEN="your_token" \
  -e X_ACCESS_TOKEN_SECRET="your_token_secret" \
  -e X_BEARER_TOKEN="your_bearer_token" \
  -e X_USERNAME="your_username" \
  -e XAI_API_KEY="your_xai_key" \
  myxstack:latest

# View logs
docker logs -f myxstack-agent

# Stop container
docker stop myxstack-agent
```

#### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  myxstack:
    build: .
    container_name: myxstack-agent
    restart: unless-stopped
    env_file: .env
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Run:

```bash
docker-compose up -d
docker-compose logs -f
```

### 4. Kubernetes

**Best for:** Multi-account deployments, high availability

#### ConfigMap and Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: myxstack-credentials
type: Opaque
stringData:
  X_API_KEY: "your_key"
  X_API_SECRET: "your_secret"
  X_ACCESS_TOKEN: "your_token"
  X_ACCESS_TOKEN_SECRET: "your_token_secret"
  X_BEARER_TOKEN: "your_bearer_token"
  XAI_API_KEY: "your_xai_key"

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: myxstack-config
data:
  X_USERNAME: "your_username"
  POLLING_INTERVAL_MS: "30000"
  MAX_RETRIES: "3"
```

#### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myxstack
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myxstack
  template:
    metadata:
      labels:
        app: myxstack
    spec:
      containers:
      - name: myxstack
        image: myxstack:latest
        envFrom:
        - secretRef:
            name: myxstack-credentials
        - configMapRef:
            name: myxstack-config
        resources:
          limits:
            memory: "256Mi"
            cpu: "500m"
          requests:
            memory: "128Mi"
            cpu: "100m"
```

Deploy:

```bash
kubectl apply -f k8s/
kubectl get pods
kubectl logs -f deployment/myxstack
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `X_USERNAME` | Your X username | `myusername` |

### Optional (for real X API access)

| Variable | Description | How to Get |
|----------|-------------|------------|
| `X_API_KEY` | X API Key | Developer Portal |
| `X_API_SECRET` | X API Secret | Developer Portal |
| `X_ACCESS_TOKEN` | Access Token | Developer Portal |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret | Developer Portal |
| `X_BEARER_TOKEN` | Bearer Token | Developer Portal |

### Optional (for Grok AI)

| Variable | Description | How to Get |
|----------|-------------|------------|
| `XAI_API_KEY` | xAI API Key | xAI Console |

### Optional (configuration)

| Variable | Description | Default |
|----------|-------------|---------|
| `POLLING_INTERVAL_MS` | Check frequency | `30000` |
| `MAX_RETRIES` | Retry attempts | `3` |

## Production Checklist

- [ ] All credentials configured in environment
- [ ] Build completes successfully (`npm run build`)
- [ ] Tested in simulation mode first
- [ ] Logs are being captured
- [ ] Auto-restart configured (systemd/docker)
- [ ] Monitoring/alerting setup
- [ ] Backup credentials stored securely
- [ ] Rate limits understood and configured
- [ ] Error handling tested
- [ ] Graceful shutdown tested

## Monitoring

### Log Files

Monitor application logs for:
- Mention processing activity
- API errors or rate limits
- Grok AI analysis results
- Action execution status

### Health Checks

Implement health check endpoint (future enhancement):
```typescript
// Simple HTTP health check
import http from 'http';

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    const stats = agent.getStats();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      uptime: process.uptime(),
      ...stats
    }));
  }
});

server.listen(3000);
```

### Metrics to Track

1. **Mentions processed** - Total count
2. **Actions taken** - Reply/search/analyze breakdown
3. **API errors** - Rate limits, auth failures
4. **Processing time** - Time per mention
5. **Uptime** - Agent availability

## Security Best Practices

1. **Never commit `.env`** - Use `.gitignore`
2. **Rotate credentials** - Change keys periodically
3. **Use secrets management** - AWS Secrets Manager, HashiCorp Vault
4. **Restrict API permissions** - Minimum required scope
5. **Monitor for abuse** - Unusual activity patterns
6. **Keep dependencies updated** - Security patches
7. **Use HTTPS** - For all API calls
8. **Audit logs** - Review regularly

## Scaling Considerations

### Single Account
- One agent instance per account
- Scale vertically (more CPU/RAM)
- Optimize polling interval

### Multiple Accounts
- One instance per account
- Use orchestration (Kubernetes)
- Shared infrastructure
- Centralized logging

### High Volume
- Reduce polling interval
- Implement webhook support
- Use message queue
- Add caching layer

## Troubleshooting Deployment

### Service won't start
```bash
# Check logs
sudo journalctl -u myxstack -n 50

# Check permissions
ls -la /home/ubuntu/MyXstack

# Verify Node.js
node --version
npm --version
```

### Out of memory
```bash
# Increase Node.js memory limit
NODE_OPTIONS="--max-old-space-size=4096" npm start
```

### Connection issues
```bash
# Test network
curl https://api.twitter.com/2/tweets
curl https://api.x.ai/v1/models

# Check firewall
sudo ufw status
```

## Backup and Recovery

### What to Backup
- Configuration files (`.env`)
- Custom modifications
- Deployment scripts

### Recovery Steps
1. Provision new server/container
2. Restore configuration
3. Install dependencies
4. Start service
5. Verify operation

## Cost Estimates

### Cloud VM
- **AWS t3.micro**: $7-10/month
- **DigitalOcean Droplet**: $5-10/month
- **Google Cloud e2-micro**: $7-10/month

### API Costs
- **X API v2 Basic**: $100/month
- **xAI Grok API**: Pay-per-use, ~$0.01-0.10/mention

### Total Estimated
- **Small scale**: $15-25/month
- **Medium scale**: $50-100/month
- **Large scale**: $200+/month

## Updates and Maintenance

### Updating Code

```bash
# Pull latest changes
cd /home/ubuntu/MyXstack
git pull origin main

# Rebuild
npm install
npm run build

# Restart service
sudo systemctl restart myxstack
```

### Dependency Updates

```bash
# Check for updates
npm outdated

# Update packages
npm update

# Rebuild and test
npm run build
npm start
```

## Support

For deployment issues:
1. Check logs first
2. Verify environment configuration
3. Test in simulation mode
4. Open GitHub issue with details
5. Include log excerpts (remove credentials)
