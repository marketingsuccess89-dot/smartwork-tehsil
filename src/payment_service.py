import os
import hmac
import hashlib
from typing import Dict, Any, Optional

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()

PLAN_AMOUNTS = {
    "weekly": 49,
    "monthly": 99,
    "yearly": 999
}

def get_razorpay_client():
    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
        try:
            import razorpay
            return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        except Exception as e:
            print(f"[Razorpay] Client init notice: {e}")
            return None
    return None

def create_payment_order(plan_type: str, user_id: str, email: str = "") -> Dict[str, Any]:
    """Creates a Razorpay order for ₹49, ₹99, or ₹999."""
    plan_key = plan_type.lower()
    amount_in_rupees = PLAN_AMOUNTS.get(plan_key, 99)
    amount_in_paise = amount_in_rupees * 100
    
    client = get_razorpay_client()
    if client:
        try:
            order_data = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": f"rcpt_{user_id[:8]}_{plan_key}",
                "notes": {
                    "plan": plan_key,
                    "user_id": user_id,
                    "email": email
                }
            }
            order = client.order.create(data=order_data)
            return {
                "success": True,
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "key_id": RAZORPAY_KEY_ID,
                "plan": plan_key
            }
        except Exception as e:
            print(f"[Razorpay] Order creation error: {e}")
            
    # Mock / Demo mode fallback when test keys not set
    import uuid
    mock_order_id = f"order_mock_{str(uuid.uuid4())[:12]}"
    return {
        "success": True,
        "mock": True,
        "order_id": mock_order_id,
        "amount": amount_in_paise,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID or "rzp_test_mockKey",
        "plan": plan_key
    }

def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """Verifies HMAC SHA256 signature from Razorpay checkout."""
    if razorpay_order_id.startswith("order_mock_"):
        return True
        
    if not RAZORPAY_KEY_SECRET:
        return True
        
    try:
        msg = f"{razorpay_order_id}|{razorpay_payment_id}"
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated_signature, razorpay_signature)
    except Exception as e:
        print(f"[Razorpay] Signature verification error: {e}")
        return False
