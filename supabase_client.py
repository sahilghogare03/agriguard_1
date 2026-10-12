# supabase_client.py

import os
import json
import hashlib
from datetime import datetime

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

supabase = None
supabase_init_error = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Connected to Supabase client successfully!")
    except Exception as e:
        print(f"Supabase connection error: {e}")
        supabase_init_error = str(e)
        supabase = None

LOCAL_HISTORY_FILE = "static/history.json"
LOCAL_USERS_FILE = "static/users.json"
EXCLUSIVE_ADMIN_EMAIL = "admin123@gmail.com"


def _read_local_json(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _write_local_json(filepath, data):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error writing local json ({filepath}): {e}")


def sync_user_profile_to_supabase(user_id, email, name, role="user"):
    """
    Syncs user profile directly to Supabase 'users' database table.
    """
    if supabase is not None:
        try:
            profile = {
                "id": str(user_id),
                "email": email.lower(),
                "name": name or email.split("@")[0],
                "role": role,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            res = supabase.table("users").upsert(profile).execute()
            if res.data:
                print(f"Successfully saved user '{email}' to Supabase 'users' database table!")
        except Exception as e:
            err_str = str(e)
            print(f"Notice (Supabase users table insert/upsert): {err_str}")


# ---------------------------------------------------------
# User Authentication Functions (Exclusive Admin: admin123@gmail.com)
# ---------------------------------------------------------

def register_user(email, password, name=""):
    """
    Registers a new user in Supabase Auth & Supabase 'users' table, with local fallback.
    Only admin123@gmail.com is granted admin role.
    """
    email_clean = email.strip().lower()
    if not email_clean or not password:
        return {"success": False, "error": "Email and password are required."}

    role = "admin" if email_clean == EXCLUSIVE_ADMIN_EMAIL else "user"
    user_id = None
    user_name = name or email_clean.split("@")[0]

    if supabase is not None:
        try:
            res = supabase.auth.sign_up({
                "email": email_clean,
                "password": password,
                "options": {
                    "data": {"name": user_name, "role": role}
                }
            })
            if res.user:
                user_id = str(res.user.id)
                print("Registered new user with Supabase Auth!")
        except Exception as e:
            err_msg = str(e)
            print(f"Supabase Auth register notice: {err_msg}")
            if "already registered" in err_msg.lower() or "user_already_exists" in err_msg.lower():
                return {"success": False, "error": "An account with this email already exists. Please log in."}

    local_users = _read_local_json(LOCAL_USERS_FILE)
    existing = next((u for u in local_users if u.get("email", "").lower() == email_clean), None)
    if existing and not user_id:
        return {"success": False, "error": "An account with this email already exists. Please log in."}

    if not user_id:
        user_id = f"user_{len(local_users) + 1}"

    pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    user_data = {
        "id": user_id,
        "email": email_clean,
        "name": user_name,
        "role": role,
        "password_hash": pwd_hash
    }

    # Sync into Supabase 'users' database table
    sync_user_profile_to_supabase(user_id, email_clean, user_name, role=role)

    if not existing:
        local_users.append(user_data)
        _write_local_json(LOCAL_USERS_FILE, local_users)

    return {
        "success": True,
        "user": {
            "id": user_data["id"],
            "email": user_data["email"],
            "name": user_data["name"],
            "role": user_data["role"]
        },
        "message": "Account created successfully!"
    }


def login_user(email, password):
    """
    Authenticates a user. Only admin123@gmail.com receives admin role.
    """
    email_clean = email.strip().lower()
    if not email_clean or not password:
        return {"success": False, "error": "Please enter both email and password."}

    role = "admin" if email_clean == EXCLUSIVE_ADMIN_EMAIL else "user"

    if supabase is not None:
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email_clean,
                "password": password
            })
            if res.user:
                meta_name = res.user.user_metadata.get("name") if res.user.user_metadata else None
                user_obj = {
                    "id": str(res.user.id),
                    "email": res.user.email,
                    "name": meta_name or email_clean.split("@")[0],
                    "role": role
                }
                sync_user_profile_to_supabase(user_obj["id"], email_clean, user_obj["name"], role=role)
                return {
                    "success": True,
                    "user": user_obj
                }
        except Exception as e:
            err_msg = str(e)
            print(f"Supabase Auth login notice: {err_msg}")

    # Fallback to local users
    local_users = _read_local_json(LOCAL_USERS_FILE)
    pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

    user = next((u for u in local_users if u.get("email", "").lower() == email_clean and (u.get("password_hash") == pwd_hash or not u.get("password_hash"))), None)
    if user:
        user_role = "admin" if email_clean == EXCLUSIVE_ADMIN_EMAIL else "user"
        sync_user_profile_to_supabase(user["id"], email_clean, user.get("name", email_clean.split("@")[0]), role=user_role)
        return {
            "success": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user.get("name", email_clean.split("@")[0]),
                "role": user_role
            }
        }

    return {"success": False, "error": "Invalid email or password. Please check your credentials."}


# ---------------------------------------------------------
# Admin Database Functions
# ---------------------------------------------------------

def get_all_users_supabase():
    """
    Fetches all registered users from Supabase 'users' table or local storage fallback.
    """
    if supabase is not None:
        try:
            res = supabase.table("users").select("*").order("created_at", desc=True).execute()
            if res.data is not None:
                return res.data, True
        except Exception as e:
            print(f"Admin fetch users notice: {e}")

    local_users = _read_local_json(LOCAL_USERS_FILE)
    clean_users = [{"id": u.get("id"), "email": u.get("email"), "name": u.get("name"), "role": "admin" if u.get("email", "").lower() == EXCLUSIVE_ADMIN_EMAIL else "user"} for u in local_users]
    return clean_users, False


def update_user_role_supabase(user_id, new_role):
    """
    Updates a user's role in Supabase 'users' table.
    """
    if supabase is not None:
        try:
            supabase.table("users").update({"role": new_role}).eq("id", str(user_id)).execute()
        except Exception as e:
            print(f"Failed to update role in Supabase: {e}")

    local_users = _read_local_json(LOCAL_USERS_FILE)
    for u in local_users:
        if str(u.get("id")) == str(user_id):
            u["role"] = new_role
    _write_local_json(LOCAL_USERS_FILE, local_users)
    return True


def delete_user_supabase(user_id):
    """
    Deletes a user from Supabase 'users' table.
    """
    if supabase is not None:
        try:
            supabase.table("users").delete().eq("id", str(user_id)).execute()
        except Exception as e:
            print(f"Failed to delete user in Supabase: {e}")

    local_users = _read_local_json(LOCAL_USERS_FILE)
    new_users = [u for u in local_users if str(u.get("id")) != str(user_id)]
    _write_local_json(LOCAL_USERS_FILE, new_users)
    return True


# ---------------------------------------------------------
# History Management Functions (Per-User Isolated & Admin)
# ---------------------------------------------------------

def save_prediction_record(record, user_email=None):
    """
    Saves prediction record to Supabase. Fallbacks to local storage if Supabase is unconfigured or unavailable.
    """
    now_iso = datetime.utcnow().isoformat() + "Z"

    db_record = {
        "user_email": user_email.lower() if user_email else "anonymous",
        "disease": record.get("disease"),
        "confidence": record.get("confidence"),
        "health_status": record.get("health_status"),
        "description": record.get("description"),
        "treatment": record.get("treatment"),
        "prevention": record.get("prevention"),
        "image_path": record.get("image"),
        "created_at": now_iso
    }

    supabase_saved = False
    if supabase is not None:
        try:
            res = supabase.table("prediction_history").insert(db_record).execute()
            if res.data:
                supabase_saved = True
                print(f"Successfully saved prediction record for '{user_email}' to Supabase!")
        except Exception as e:
            err_str = str(e)
            print(f"Failed to insert record to Supabase: {err_str}")

    local_data = _read_local_json(LOCAL_HISTORY_FILE)
    db_record["id"] = local_data[0]["id"] + 1 if local_data and isinstance(local_data[0].get("id"), int) else len(local_data) + 1
    db_record["supabase_synced"] = supabase_saved
    local_data.insert(0, db_record)
    _write_local_json(LOCAL_HISTORY_FILE, local_data)

    return db_record


def get_prediction_history(limit=200, user_email=None, role="user"):
    """
    Retrieves prediction history records from Supabase or local storage fallback.
    Strictly isolated per user unless role == 'admin' or user_email == admin123@gmail.com.
    """
    is_admin = (role == "admin" or (user_email and user_email.lower() == EXCLUSIVE_ADMIN_EMAIL))

    if not user_email and not is_admin:
        return [], False, "No active user session."

    if supabase is not None:
        try:
            query = supabase.table("prediction_history").select("*").order("created_at", desc=True).limit(limit)
            if not is_admin and user_email:
                query = query.eq("user_email", user_email.lower())
            res = query.execute()
            if res.data is not None:
                return res.data, True, None
        except Exception as e:
            err_msg = str(e)
            if "user_email" in err_msg and ("does not exist" in err_msg or "42703" in err_msg):
                try:
                    res = supabase.table("prediction_history").select("*").order("created_at", desc=True).limit(limit).execute()
                    if res.data is not None:
                        return res.data, True, None
                except Exception:
                    pass
            print(f"Failed to fetch history from Supabase: {err_msg}")
            local_data = _read_local_json(LOCAL_HISTORY_FILE)
            if not is_admin and user_email:
                local_data = [r for r in local_data if (r.get("user_email") or "").lower() == user_email.lower()]
            return local_data[:limit], False, err_msg

    local_data = _read_local_json(LOCAL_HISTORY_FILE)
    if not is_admin and user_email:
        local_data = [r for r in local_data if (r.get("user_email") or "").lower() == user_email.lower()]
    elif not user_email:
        local_data = []

    return local_data[:limit], False, supabase_init_error


def delete_prediction_record(record_id, user_email=None, role="user"):
    """
    Deletes a prediction record by ID (user isolated or admin).
    """
    is_admin = (role == "admin" or (user_email and user_email.lower() == EXCLUSIVE_ADMIN_EMAIL))

    if supabase is not None:
        try:
            query = supabase.table("prediction_history").delete().eq("id", record_id)
            if not is_admin and user_email:
                query = query.eq("user_email", user_email.lower())
            query.execute()
        except Exception as e:
            print(f"Failed to delete from Supabase: {e}")

    local_data = _read_local_json(LOCAL_HISTORY_FILE)
    new_data = [item for item in local_data if str(item.get("id")) != str(record_id)]
    _write_local_json(LOCAL_HISTORY_FILE, new_data)
    return True


def clear_all_history(user_email=None, role="user"):
    """
    Clears history records.
    """
    is_admin = (role == "admin" or (user_email and user_email.lower() == EXCLUSIVE_ADMIN_EMAIL))

    if supabase is not None:
        try:
            query = supabase.table("prediction_history").delete()
            if not is_admin and user_email:
                query = query.eq("user_email", user_email.lower())
            else:
                query = query.neq("id", -1)
            query.execute()
        except Exception as e:
            print(f"Failed to clear Supabase table: {e}")

    if not is_admin and user_email:
        local_data = _read_local_json(LOCAL_HISTORY_FILE)
        new_data = [item for item in local_data if (item.get("user_email") or "").lower() != user_email.lower()]
        _write_local_json(LOCAL_HISTORY_FILE, new_data)
    else:
        _write_local_json(LOCAL_HISTORY_FILE, [])

    return True
