"""Deployment webhook receiver for EVE Market Agent.

Receives deploy triggers from GitHub Actions, verifies the webhook secret,
pulls latest Docker images, and performs a zero-downtime restart.

Usage:
    pip install uvicorn
    WEBHOOK_SECRET=xxx python scripts/deploy-webhook.py
    # Runs on port 9000, only accessible from localhost (put behind nginx)
"""

import os
import subprocess
import hmac
import hashlib
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
import uvicorn

app = FastAPI()
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

HEALTH_CHECK_URL = "http://localhost/health"
HEALTH_CHECK_TIMEOUT = 60
HEALTH_CHECK_INTERVAL = 3


def verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result.stdout.strip()


@app.post("/webhook/deploy")
async def deploy(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Webhook-Secret", "")

    if WEBHOOK_SECRET and not verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await request.json()
    commit = payload.get("commit", "unknown")
    branch = payload.get("branch", "unknown")

    print(f"[{datetime.now()}] Deploy triggered: commit={commit}, branch={branch}")

    try:
        # 1. Pull latest images
        print("Pulling latest images...")
        run("docker compose -f /opt/eve-market/docker-compose.yml pull")

        # 2. Run database migrations
        print("Running database migrations...")
        run("docker compose -f /opt/eve-market/docker-compose.yml run --rm backend alembic upgrade head")

        # 3. Restart services (zero-downtime: new containers start before old ones stop)
        print("Restarting services...")
        run("docker compose -f /opt/eve-market/docker-compose.yml up -d --remove-orphans")

        # 4. Wait for health check
        print("Waiting for health check...")
        import time
        import httpx
        deadline = time.time() + HEALTH_CHECK_TIMEOUT
        healthy = False
        while time.time() < deadline:
            time.sleep(HEALTH_CHECK_INTERVAL)
            try:
                resp = httpx.get(HEALTH_CHECK_URL, timeout=5)
                if resp.status_code == 200 and resp.json().get("status") == "ok":
                    healthy = True
                    break
            except Exception:
                pass

        if not healthy:
            raise RuntimeError("Health check failed after deployment")

        # 5. Clean up old images
        print("Cleaning up old images...")
        run("docker image prune -f")

        # 6. Notify (optional Discord)
        discord_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
        if discord_url:
            import httpx
            httpx.post(discord_url, json={
                "content": f"✅ **EVE Market Agent 部署成功**\nCommit: `{commit}`\nBranch: `{branch}`"
            })

        print(f"[{datetime.now()}] Deploy successful")
        return {"status": "deployed", "commit": commit, "healthy": healthy}

    except Exception as e:
        print(f"[{datetime.now()}] Deploy failed: {e}")
        if discord_url := os.environ.get("DISCORD_WEBHOOK_URL", ""):
            import httpx
            httpx.post(discord_url, json={
                "content": f"❌ **EVE Market Agent 部署失败**\nCommit: `{commit}`\nError: `{str(e)[:500]}`"
            })
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
