import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename

from disease_info import disease_info
from predict import predict_disease
from supabase_client import (
    save_prediction_record,
    get_prediction_history,
    delete_prediction_record,
    clear_all_history,
    register_user,
    login_user,
    get_all_users_supabase,
    update_user_role_supabase,
    delete_user_supabase,
    EXCLUSIVE_ADMIN_EMAIL,
    SUPABASE_URL
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "agriguard_secret_key_2026_safe")

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def is_admin_user(user):
    """
    Checks if a user is authorized as Admin. Only admin123@gmail.com is granted access.
    """
    if not user:
        return False
    email = user.get("email", "").strip().lower()
    return email == EXCLUSIVE_ADMIN_EMAIL or user.get("role") == "admin"


# ---------------------------------------------------------
# Web Page Routes
# ---------------------------------------------------------

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html")


@app.route("/login")
def login_page():
    if "user" in session:
        user = session["user"]
        if is_admin_user(user):
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/register")
def register_page():
    if "user" in session:
        return redirect(url_for("home"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@app.route("/history")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login_page", required=1))
    return render_template("history.html")


@app.route("/admin")
@app.route("/admin/dashboard")
def admin_dashboard():
    user = session.get("user")
    if not is_admin_user(user):
        return redirect(url_for("login_page", required=1))
    return render_template("admin.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------------------------------------------------
# Authentication API Endpoints
# ---------------------------------------------------------

@app.route("/api/auth/user", methods=["GET"])
def api_get_user():
    if "user" in session:
        return jsonify({"logged_in": True, "user": session["user"]})
    return jsonify({"logged_in": False, "user": None})


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    email = data.get("email", "")
    password = data.get("password", "")

    res = login_user(email, password)
    if res.get("success"):
        session["user"] = res["user"]
        return jsonify({"success": True, "user": res["user"]})
    return jsonify({"success": False, "error": res.get("error", "Login failed.")}), 400


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    name = data.get("name", "")
    email = data.get("email", "")
    password = data.get("password", "")

    res = register_user(email, password, name=name)
    if res.get("success"):
        session["user"] = res["user"]
        return jsonify({"success": True, "user": res["user"]})
    return jsonify({"success": False, "error": res.get("error", "Registration failed.")}), 400


# ---------------------------------------------------------
# Crop Prediction Endpoint
# ---------------------------------------------------------

@app.route("/predict", methods=["POST"])
def predict():
    if "user" not in session:
        return jsonify({"error": "Login required to scan crops. Please sign in."}), 401

    if "image" not in request.files:
        return jsonify({
            "error": "No image uploaded"
        })

    file = request.files["image"]

    if file.filename == "":
        return jsonify({
            "error": "No file selected"
        })

    if file and allowed_file(file.filename):

        filename = secure_filename(file.filename)

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        file.save(filepath)

        result = predict_disease(filepath)

        if "error" in result:
            return jsonify({
                "error": result["error"]
            })

        disease = result["disease"]
        confidence = result["confidence"]
        health_status = "Healthy" if "healthy" in disease.lower() else "Diseased"

        info = disease_info.get(
            disease,
            {
                "description": "No information available.",
                "treatment": "No treatment available.",
                "prevention": "No prevention available."
            }
        )

        response_payload = {
            "status": "success",
            "disease": disease,
            "confidence": round(confidence, 2),
            "health_status": health_status,
            "description": info["description"],
            "treatment": info["treatment"],
            "prevention": info["prevention"],
            "image": filepath.replace("\\", "/")
        }

        # Save to Supabase History bound to logged in user
        user_email = session["user"].get("email")
        try:
            save_prediction_record(response_payload, user_email=user_email)
        except Exception as e:
            print(f"Error saving to history: {e}")

        return jsonify(response_payload)

    return jsonify({
        "error": "Invalid image format. Supported formats: PNG, JPG, JPEG, WEBP."
    })


# ---------------------------------------------------------
# User History API Endpoints
# ---------------------------------------------------------

@app.route("/api/history", methods=["GET"])
def api_history():
    if "user" not in session:
        return jsonify({
            "status": "error",
            "error": "Login required to access history dashboard.",
            "login_required": True
        }), 401

    user = session["user"]
    user_email = user.get("email")
    role = user.get("role", "user")

    records, is_supabase, supabase_err = get_prediction_history(user_email=user_email, role=role)

    total_scans = len(records)
    healthy_count = sum(1 for r in records if r.get("health_status") == "Healthy")
    diseased_count = sum(1 for r in records if r.get("health_status") == "Diseased")
    avg_confidence = round(sum(r.get("confidence", 0) for r in records) / total_scans, 1) if total_scans > 0 else 0

    return jsonify({
        "status": "success",
        "records": records,
        "is_supabase": is_supabase,
        "supabase_configured": bool(SUPABASE_URL),
        "supabase_error": supabase_err,
        "user": user,
        "stats": {
            "total_scans": total_scans,
            "healthy_count": healthy_count,
            "diseased_count": diseased_count,
            "avg_confidence": avg_confidence
        }
    })


@app.route("/api/history/<record_id>", methods=["DELETE"])
def api_delete_history(record_id):
    if "user" not in session:
        return jsonify({"error": "Login required."}), 401

    user = session["user"]
    delete_prediction_record(record_id, user_email=user.get("email"), role=user.get("role", "user"))
    return jsonify({"status": "success", "message": "Record deleted successfully"})


@app.route("/api/history/clear", methods=["POST"])
def api_clear_history():
    if "user" not in session:
        return jsonify({"error": "Login required."}), 401

    user = session["user"]
    clear_all_history(user_email=user.get("email"), role=user.get("role", "user"))
    return jsonify({"status": "success", "message": "All history cleared successfully"})


# ---------------------------------------------------------
# Admin Control & Supabase Database API Endpoints
# ---------------------------------------------------------

@app.route("/api/admin/dashboard", methods=["GET"])
def api_admin_dashboard():
    user = session.get("user")
    if not is_admin_user(user):
        return jsonify({"error": "Admin privileges required. Access limited to admin123@gmail.com."}), 403

    users, users_sub = get_all_users_supabase()
    scans, scans_sub, err = get_prediction_history(limit=500, role="admin")

    total_scans = len(scans)
    healthy_count = sum(1 for s in scans if s.get("health_status") == "Healthy")
    diseased_count = sum(1 for s in scans if s.get("health_status") == "Diseased")
    diseased_ratio = round((diseased_count / total_scans * 100), 1) if total_scans > 0 else 0
    avg_confidence = round(sum(s.get("confidence", 0) for s in scans) / total_scans, 1) if total_scans > 0 else 0

    return jsonify({
        "status": "success",
        "admin_user": user,
        "users": users,
        "scans": scans,
        "stats": {
            "total_users": len(users),
            "total_scans": total_scans,
            "healthy_count": healthy_count,
            "diseased_count": diseased_count,
            "diseased_ratio": diseased_ratio,
            "avg_confidence": avg_confidence
        }
    })


@app.route("/api/admin/users/<user_id>/role", methods=["POST"])
def api_admin_update_role(user_id):
    user = session.get("user")
    if not is_admin_user(user):
        return jsonify({"error": "Admin privileges required."}), 403

    data = request.get_json() or {}
    new_role = data.get("role", "user")
    update_user_role_supabase(user_id, new_role)
    return jsonify({"status": "success", "message": f"User role updated to {new_role}"})


@app.route("/api/admin/users/<user_id>", methods=["DELETE"])
def api_admin_delete_user(user_id):
    user = session.get("user")
    if not is_admin_user(user):
        return jsonify({"error": "Admin privileges required."}), 403

    delete_user_supabase(user_id)
    return jsonify({"status": "success", "message": "User deleted successfully"})


@app.route("/api/admin/history/<record_id>", methods=["DELETE"])
def api_admin_delete_history(record_id):
    user = session.get("user")
    if not is_admin_user(user):
        return jsonify({"error": "Admin privileges required."}), 403

    delete_prediction_record(record_id, role="admin")
    return jsonify({"status": "success", "message": "Record deleted successfully"})


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )