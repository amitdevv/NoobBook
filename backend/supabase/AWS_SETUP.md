# AWS EC2 Deployment

Deploy NoobBook on AWS EC2 with Docker. 5 steps, one command does the heavy lifting.

## 1. Launch EC2 Instance

1. Go to **EC2 > Launch Instance**
2. Configure:
   - **Name:** `noobbook-server`
   - **AMI:** Ubuntu Server 24.04 LTS (amd64)
   - **Instance type:** `m7i-flex.large` (2 vCPU, 8 GB RAM) or `c7i-flex.large` (2 vCPU, 4 GB — minimum)
   - **Key pair:** Create new → `noob-book-key` → RSA → `.pem` → Download it
   - **Storage:** 30 GiB gp3

3. **Security group** — Add these inbound rules:

   | Type | Port | Source | Purpose |
   |------|------|--------|---------|
   | SSH | 22 | My IP | SSH access |
   | HTTP | 80 | Anywhere (0.0.0.0/0) | NoobBook app |

   That's it — nginx handles everything on port 80. No need to expose 5001, 5173, or 8000.

4. Launch and note the **Public IPv4 address**

## 2. SSH Into the Server

```bash
chmod 400 /path/to/noob-book-key.pem
ssh -i /path/to/noob-book-key.pem ubuntu@<PUBLIC_IP>
```

## 3. Install Docker

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
```

Verify:
```bash
docker --version
docker compose version
```

## 4. Clone and Configure

```bash
git clone -b develop https://github.com/TeacherOp/NoobBook.git
cd NoobBook
cp docker/.env.example docker/.env
nano docker/.env
```

Add your API keys (only these 4 are required — everything else is auto-generated):

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

## 5. Run Setup

```bash
bash docker/setup.sh
```

This single command:
- Generates all Supabase secrets (JWT, passwords, tokens)
- Creates the Docker network
- Starts Supabase (13 services)
- Waits for the API gateway to become healthy
- Runs database migrations
- Builds and starts NoobBook (backend + frontend + nginx)

Open in browser: `http://<PUBLIC_IP>`

Done.

## Quick Reference

| Service | URL |
|---------|-----|
| NoobBook | `http://<PUBLIC_IP>` |
| Backend API | `http://<PUBLIC_IP>/api/v1` (proxied via nginx) |
| Supabase API | `http://<PUBLIC_IP>:8000` (internal, not needed externally) |

## Managing the Deployment

```bash
cd ~/NoobBook

# Check status
docker compose ps                              # NoobBook containers
docker compose -f docker/supabase/docker-compose.yml ps   # Supabase containers

# View logs
docker compose logs -f backend                 # Backend logs
docker compose logs -f frontend                # Nginx logs
docker compose logs -f migrate                 # Migration logs

# Stop everything (data preserved)
bash docker/stop.sh

# Restart everything
bash docker/setup.sh                           # Idempotent, skips existing .env

# Update to latest code
git pull origin develop
docker compose up -d --build                   # Rebuild with new code

# Full reset (destroys all data)
bash docker/reset.sh -v
```

## Starting Fresh

If something is broken and you want to start from zero on the same server:

```bash
cd ~/NoobBook
bash docker/stop.sh                            # Stop everything
cd ~
sudo rm -rf NoobBook                           # Remove repo
sudo docker system prune -a --volumes -f       # Remove all Docker data

# Then redo from step 4
git clone -b develop https://github.com/TeacherOp/NoobBook.git
cd NoobBook
cp docker/.env.example docker/.env
nano docker/.env                               # Add API keys
bash docker/setup.sh
```

## Troubleshooting

### Setup script fails at "Waiting for Kong"

Supabase services need time to start. If it times out:
```bash
# Check which service is unhealthy
docker ps -a | grep supabase
docker logs supabase-analytics                 # Logflare often fails first
docker logs supabase-db                        # Database issues
```

Most failures are from low memory. Ensure at least 4 GB RAM.

### Can't access in browser

- Check security group has **port 80** open to `0.0.0.0/0`
- Check containers are running: `docker compose ps`
- Test from server: `curl http://localhost`

### Backend errors

```bash
docker compose logs -f backend
```

Common issues:
- Missing API keys in `docker/.env`
- Supabase not healthy yet (backend depends on migration completing)

### Disk space running low

```bash
df -h /
sudo docker system prune -a                   # Clean unused images
```

### Update security group for new setup

If migrating from the old manual setup, you can **remove** ports 5001, 5173, and 8000 from the security group. Only **port 80** (HTTP) and **port 22** (SSH) are needed now.
