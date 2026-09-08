import os
import time
import datetime
from typing import Optional, Dict, Any

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()

supabase_client = None

def get_supabase_client():
    global supabase_client
    if supabase_client is not None:
        return supabase_client
    
    if SUPABASE_URL and (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY):
        try:
            from supabase import create_client, Client
            key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
            supabase_client = create_client(SUPABASE_URL, key)
            print("[Supabase] Successfully connected to Supabase Client.")
            return supabase_client
        except Exception as e:
            print(f"[Supabase] Client initialization notice: {e}")
            return None
    return None

def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetches user profile from Supabase profiles table, with fallback."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        res = client.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data if res else None
    except Exception as e:
        print(f"[Supabase] Error getting profile for {user_id}: {e}")
        return None

def upsert_user_profile(user_id: str, email: str, full_name: str = "", mobile: str = "", location: str = "") -> Dict[str, Any]:
    """Creates or updates a user profile with onboarding info."""
    client = get_supabase_client()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    profile_data = {
        "id": user_id,
        "email": email,
        "updated_at": now_iso
    }
    if full_name:
        profile_data["full_name"] = full_name
    if mobile:
        profile_data["mobile"] = mobile
    if location:
        profile_data["location"] = location

    if client:
        try:
            # Check if profile exists
            existing = get_user_profile(user_id)
            if existing:
                res = client.table("profiles").update(profile_data).eq("id", user_id).execute()
                return res.data[0] if res.data else {**existing, **profile_data}
            else:
                profile_data["plan"] = "free"
                profile_data["created_at"] = now_iso
                res = client.table("profiles").insert(profile_data).execute()
                return res.data[0] if res.data else profile_data
        except Exception as e:
            print(f"[Supabase] Error upserting profile: {e}")
    
    # Fallback in-memory dict
    return profile_data

def verify_user_is_pro(user_id: str, email: str = "") -> bool:
    """Checks whether user has an active, non-expired PRO membership."""
    if not user_id and not email:
        return False
    
    client = get_supabase_client()
    if client:
        try:
            query = client.table("profiles").select("plan, plan_expires_at")
            if user_id:
                res = query.eq("id", user_id).execute()
            else:
                res = query.eq("email", email.strip().lower()).execute()
                
            if res and res.data and len(res.data) > 0:
                user_record = res.data[0]
                plan = user_record.get("plan", "free")
                expires_at = user_record.get("plan_expires_at")
                if plan == "pro":
                    if not expires_at:
                        return True
                    # Check if expiration timestamp is in future
                    try:
                        exp_dt = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        return exp_dt > datetime.datetime.now(datetime.timezone.utc)
                    except Exception:
                        return True
        except Exception as e:
            print(f"[Supabase] Pro status verification notice: {e}")
            
    return False

def upgrade_user_to_pro(user_id: str, plan_type: str, order_id: str = "", payment_id: str = "") -> bool:
    """Activates PRO membership for 7 days (weekly), 30 days (monthly), or 365 days (yearly)."""
    client = get_supabase_client()
    
    days_map = {
        "weekly": 7,
        "monthly": 30,
        "yearly": 365
    }
    days = days_map.get(plan_type.lower(), 30)
    now = datetime.datetime.now(datetime.timezone.utc)
    expiry = now + datetime.timedelta(days=days)
    
    update_data = {
        "plan": "pro",
        "plan_expires_at": expiry.isoformat(),
        "updated_at": now.isoformat()
    }
    
    if client:
        try:
            client.table("profiles").update(update_data).eq("id", user_id).execute()
            
            # Record in subscriptions table
            sub_record = {
                "user_id": user_id,
                "plan_type": plan_type,
                "amount": 49 if plan_type == "weekly" else (99 if plan_type == "monthly" else 999),
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "status": "active",
                "starts_at": now.isoformat(),
                "expires_at": expiry.isoformat()
            }
            client.table("subscriptions").insert(sub_record).execute()
            return True
        except Exception as e:
            print(f"[Supabase] Error upgrading user to pro: {e}")
            return False
            
    return True
