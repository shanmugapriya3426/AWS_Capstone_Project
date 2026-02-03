import boto3
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

app = Flask(__name__)
app.secret_key = "lenslease_final_secure_2026"

# ---------- AWS CONFIG ----------
REGION = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
users_table = dynamodb.Table("Users")
bookings_table = dynamodb.Table("Bookings")

# ---------- UTIL ----------
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Unauthorized access!")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ---------- AUTH ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        pwd = request.form.get("password")

        user = users_table.get_item(Key={"email": email}).get("Item")

        if user:
            if user.get("status") == "rejected":
                flash("Your registration request was rejected by the Admin.")
                return render_template("login.html")

            if user.get("status") == "pending":
                flash("Account pending admin approval.")
                return render_template("login.html")

            if user["pwd"] == pwd:
                session.update({
                    "user": email,
                    "role": user["role"],
                    "name": user["name"]
                })

                if user["role"] == "admin":
                    return redirect(url_for("admin_dashboard"))
                if user["role"] == "photographer":
                    return redirect(url_for("photographer_dashboard"))
                return redirect(url_for("client_dashboard"))

        flash("Invalid email or password.")
    return render_template("login.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        pwd = request.form.get("password")

        user = users_table.get_item(Key={"email": email}).get("Item")
        if user and user["pwd"] == pwd and user["role"] == "admin":
            session.update({"user": email, "role": "admin", "name": user["name"]})
            return redirect(url_for("admin_dashboard"))

        flash("Admin credentials only!")
    return render_template("admin_login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        role = request.form["role"]

        if users_table.get_item(Key={"email": email}).get("Item"):
            flash("Account already exists. Please log in.")
            return redirect(url_for("signup"))

        if role == "admin":
            flash("Cannot signup as admin.")
            return redirect(url_for("signup"))

        user_data = {
            "email": email,
            "name": request.form["name"],
            "pwd": request.form["password"],
            "role": role,
            "status": "pending" if role == "photographer" else "active",
            "specialization": request.form.get("specialization", "General"),
            "location": request.form.get("location", "India"),
            "pricing": request.form.get("pricing", "0"),
            "portfolio": [
                "https://images.unsplash.com/photo-1542038784456-1ea8e935640e?w=500"
            ]
        }

        users_table.put_item(Item=user_data)

        if role == "photographer":
            flash("Awaiting Admin Approval.")
        else:
            flash("Account created! Log in.")

        return redirect(url_for("login"))
    return render_template("signup.html")

# ---------- CLIENT ----------
@app.route("/client_dashboard")
@login_required(role="client")
def client_dashboard():
    response = users_table.scan(
        FilterExpression=Attr("role").eq("photographer") & Attr("status").eq("active")
    )
    photographers = {u["email"]: u for u in response.get("Items", [])}
    return render_template("client_dashboard.html", photographers=photographers)

@app.route("/book/<p_email>", methods=["POST"])
@login_required(role="client")
def book_photographer(p_email):
    p = users_table.get_item(Key={"email": p_email}).get("Item")
    p_name = p["name"] if p else "Unknown"

    booking = {
        "id": str(uuid.uuid4())[:8],
        "client": session["user"],
        "p_email": p_email,
        "p_name": p_name,
        "date": request.form["date"],
        "event": request.form["event"],
        "status": "Pending"
    }

    bookings_table.put_item(Item=booking)
    flash(f"Booking request sent to {p_name}!")
    return redirect(url_for("booking_history"))

@app.route("/booking_history")
@login_required(role="client")
def booking_history():
    response = bookings_table.scan(
        FilterExpression=Attr("client").eq(session["user"])
    )
    return render_template("booking_history.html", bookings=response.get("Items", []))

# ---------- ADMIN ----------
@app.route("/admin_dashboard")
@login_required(role="admin")
def admin_dashboard():
    users = users_table.scan().get("Items", [])
    bookings = bookings_table.scan().get("Items", [])

    pending = [u for u in users if u.get("status") == "pending"]
    active = [u for u in users if u.get("status") == "active" or u["role"] == "admin"]

    return render_template(
        "admin_dashboard.html",
        total_users=len(active),
        pending_approvals=len(pending),
        total_bookings=len(bookings),
        users={u["email"]: u for u in active},
        pending={u["email"]: u for u in pending},
        bookings=bookings
    )

@app.route("/admin/approve/<email>")
@login_required(role="admin")
def admin_approve(email):
    users_table.update_item(
        Key={"email": email},
        UpdateExpression="SET #s=:v",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":v": "active"}
    )
    flash("Photographer approved!")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reject/<email>")
@login_required(role="admin")
def admin_reject(email):
    users_table.update_item(
        Key={"email": email},
        UpdateExpression="SET #s=:v",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":v": "rejected"}
    )
    flash("Photographer rejected.")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_user/<email>")
@login_required(role="admin")
def delete_user(email):
    users_table.delete_item(Key={"email": email})
    flash("User removed.")
    return redirect(url_for("admin_dashboard"))

# ---------- PHOTOGRAPHER ----------
@app.route("/photographer_dashboard")
@login_required(role="photographer")
def photographer_dashboard():
    response = bookings_table.scan(
        FilterExpression=Attr("p_email").eq(session["user"])
    )
    users = {u["email"]: u for u in users_table.scan().get("Items", [])}
    return render_template(
        "photographer_dashboard.html",
        bookings=response.get("Items", []),
        users=users
    )

@app.route("/photographer/profile", methods=["GET", "POST"])
@login_required(role="photographer")
def photographer_profile():
    email = session["user"]

    if request.method == "POST":
        users_table.update_item(
            Key={"email": email},
            UpdateExpression="SET #n=:n, specialization=:s, location=:l, pricing=:p",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={
                ":n": request.form["name"],
                ":s": request.form["specialization"],
                ":l": request.form["location"],
                ":p": request.form["pricing"]
            }
        )

        portfolio_url = request.form.get("portfolio_url")
        if portfolio_url:
            users_table.update_item(
                Key={"email": email},
                UpdateExpression="SET portfolio = list_append(if_not_exists(portfolio,:e),:p)",
                ExpressionAttributeValues={
                    ":p": [portfolio_url],
                    ":e": []
                }
            )

        flash("Profile updated successfully!")
        return redirect(url_for("photographer_dashboard"))

    user = users_table.get_item(Key={"email": email}).get("Item")
    return render_template("photographer_profile.html", p=user)

@app.route("/booking/action/<bid>/<action>")
@login_required(role="photographer")
def booking_action(bid, action):
    status_map = {
        "accept": "Confirmed",
        "reject": "Rejected",
        "complete": "Completed"
    }

    if action in status_map:
        bookings_table.update_item(
            Key={"id": bid},
            UpdateExpression="SET #s=:v",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":v": status_map[action]}
        )
        flash(f"Booking marked as {status_map[action]}")

    return redirect(url_for("photographer_dashboard"))

# ---------- MISC ----------
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
