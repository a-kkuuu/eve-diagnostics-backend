import argparse
import hmac
import hashlib
import json
import uuid
import httpx
from app.config import settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-ref", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--event-id", required=False)
    parser.add_argument("--url", default="http://localhost:8000/payments/webhook/")
    args = parser.parse_args()

    event_id = args.event_id or f"evt_{uuid.uuid4().hex}"
    
    payload = {
        "event_id": event_id,
        "provider_ref": args.provider_ref,
        "status": args.status
    }
    body = json.dumps(payload).encode()
    
    secret = settings.webhook_secret
    if not secret:
        print("WEBHOOK_SECRET is not set in config!")
        return

    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    
    response = httpx.post(args.url, content=body, headers={"X-Signature": sig})
    
    try:
        print(response.json())
    except Exception:
        print(response.text)

if __name__ == "__main__":
    main()
