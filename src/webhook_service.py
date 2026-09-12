import os
import json
import threading
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional

CRM_WEBHOOK_URL = os.getenv("CRM_WEBHOOK_URL", "").strip()

def send_crm_webhook(event_type: str, data: Dict[str, Any], webhook_url: Optional[str] = None):
    """
    Asynchronously dispatches a real-time event payload to the CRM webhook.
    Uses non-blocking background thread so user requests are never delayed.
    """
    target_url = webhook_url or CRM_WEBHOOK_URL or os.getenv("CRM_WEBHOOK_URL", "").strip()
    if not target_url:
        return

    def _worker():
        try:
            payload = {
                "event": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "SmartTyping - Tehsil SmartWork",
                "data": data
            }
            headers= {
                "Content-Type": "application/json",
                "User-Agent": "SmartWork-CRM-Tracker/1.0"
            }
            res = requests.post(target_url, json=payload, headers=headers, timeout=8)
            print(f"[CRM Webhook] Event '{event_type}' dispatched to {target_url} -> Status {res.status_code}")
        except Exception as e:
            print(f"[CRM Webhook] Error sending webhook: {e}")

    threading.Thread(target=_worker, daemon=True).start()
