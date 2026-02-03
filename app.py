from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = "lenslease_final_secure_2026"

# --- DATABASE ---
db = {
    "users": {
        "admin@test.com": {"pwd": "admin", "role": "admin", "name": "System Admin"},
        # Adding photographers to users so they can log in too
        "arjun@lens.com": {"pwd": "123", "role": "photographer", "name": "Arjun Sharma"},
        "priya@lens.com": {"pwd": "123", "role": "photographer", "name": "Priya Kapoor"},
    },
    "pending_photographers": {},
    "photographers": {
        "arjun@lens.com": {
            "name": "Arjun Sharma",
            "specialization": "Wedding",
            "location": "Mumbai, MH",
            "pricing": "15000",
            "portfolio": ["https://images.unsplash.com/photo-1519741497674-611481863552?w=800"]
        },
        "priya@lens.com": {
            "name": "Priya Kapoor",
            "specialization": "Portrait",
            "location": "Delhi, NCR",
            "pricing": "5000",
            "portfolio": ["https://images.unsplash.com/photo-1554080353-a576cf803bda?w=800"]
        },
        "rahul@lens.com": {
            "name": "Rahul Verma",
            "specialization": "Product Shoot",
            "location": "Bangalore, KA",
            "pricing": "8500",
            "portfolio": ["https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800"]
        }
    },
    "bookings": [],
    "rejected_users": []
}

# --- ACCESS CONTROL DECORATOR ---
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash("Unauthorized access!")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- AUTH ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        pwd = request.form.get('password')
       
        # Check if they were rejected first
        if email in db.get("rejected_users", []):
            flash("Your registration request was rejected by the Admin.")
            return render_template('login.html')

        user = db["users"].get(email)
        if user and user['pwd'] == pwd:
            session['user'] = email
            session['role'] = user['role']
            session['name'] = user['name']
           
            if user['role'] == 'admin': return redirect(url_for('admin_dashboard'))
            if user['role'] == 'photographer': return redirect(url_for('photographer_dashboard'))
            return redirect(url_for('client_dashboard'))
       
        flash("Invalid email/password or account pending approval.")
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        pwd = request.form.get('password')
        # This checks your db dictionary for the credentials you provided
        user = db["users"].get(email)
        if user and user['pwd'] == pwd and user['role'] == 'admin':
            session['user'] = email
            session['role'] = 'admin'
            session['name'] = user['name']
            return redirect(url_for('admin_dashboard'))
        flash("Admin credentials only!")
    return render_template('admin_login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        role = request.form['role']
        if role == 'admin':
            flash("Cannot signup as admin.")
            return redirect(url_for('signup'))

        user_data = {
            "name": request.form['name'],
            "pwd": request.form['password'],
            "role": role,
            "specialization": request.form.get('specialization', 'General'),
            "location": request.form.get('location', 'India'),
            "pricing": request.form.get('pricing', '0'),
            "portfolio": ["https://images.unsplash.com/photo-1542038784456-1ea8e935640e?w=500"]
        }
       
        if role == "photographer":
            db["pending_photographers"][email] = user_data
            flash("Awaiting Admin Approval.")
        else:
            db["users"][email] = user_data
            flash("Account created! Log in.")
        return redirect(url_for('login'))
    return render_template('signup.html')

# --- DASHBOARDS (THE KEY FIX) ---

@app.route('/client_dashboard')
@login_required(role='client')
def client_dashboard():
    # This function name 'client_dashboard' is what url_for looks for
    return render_template('client_dashboard.html', photographers=db["photographers"])

@app.route('/admin_dashboard')
@login_required(role='admin')
def admin_dashboard():
    # 1. Total Users (Clients + Approved Photographers)
    total_users_count = len(db["users"])
   
    # 2. Pending Approvals (New photographer signups)
    pending_count = len(db["pending_photographers"])
   
    # 3. System Bookings (Total number of bookings made)
    bookings_count = len(db["bookings"])


    return render_template(
        'admin_dashboard.html',
        total_users=total_users_count,
        pending_approvals=pending_count,
        total_bookings=bookings_count,
        # Ensure you also pass the lists for your tables
        users=db["users"],
        pending=db["pending_photographers"],
        bookings=db["bookings"]
    )

# --- BOOKING ACTIONS ---

@app.route('/book/<p_email>', methods=['POST'])
@login_required(role='client')
def book_photographer(p_email):
    # Ensure we get the name from the photographers dictionary
    photographer_data = db["photographers"].get(p_email)
    p_name = photographer_data['name'] if photographer_data else "Unknown Photographer"


    new_booking = {
        "id": len(db["bookings"]) + 1,
        "client": session['user'],
        "p_email": p_email,
        "p_name": p_name, # This ensures the name is saved in the booking
        "date": request.form['date'],
        "event": request.form['event'],
        "status": "Pending"
    }
    db["bookings"].append(new_booking)
    flash(f"Booking request sent to {p_name}!")
    return redirect(url_for('booking_history'))

@app.route('/booking_history')
@login_required(role='client')
def booking_history():
    user_bookings = [b for b in db["bookings"] if b['client'] == session['user']]
    return render_template('booking_history.html', bookings=user_bookings)

# --- ADMIN ACTIONS ---

@app.route('/admin/approve/<email>')
@login_required(role='admin')
def admin_approve(email):
    if email in db["pending_photographers"]:
        data = db["pending_photographers"].pop(email)
        db["users"][email] = data
        db["photographers"][email] = data
        flash(f"Photographer {data['name']} Approved!")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/reject/<email>')
@login_required(role='admin')
def admin_reject(email):
    if email in db["pending_photographers"]:
        db["pending_photographers"].pop(email)
        # Add to rejected list so they get the message on login
        if "rejected_users" not in db: db["rejected_users"] = []
        db["rejected_users"].append(email)
        flash(f"Photographer request ({email}) has been rejected.")
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- PHOTOGRAPHER DASHBOARD & ACTIONS ---

@app.route('/photographer_dashboard')
@login_required(role='photographer')
def photographer_dashboard():
    # Fetch only bookings assigned to this photographer
    my_bookings = [b for b in db["bookings"] if b['p_email'] == session['user']]
    return render_template('photographer_dashboard.html', bookings=my_bookings, users=db["users"])

@app.route('/photographer/profile', methods=['GET', 'POST'])
@login_required(role='photographer')
def photographer_profile():
    email = session['user']
    if request.method == 'POST':
        # Update photographer details in the database
        db["photographers"][email].update({
            "name": request.form.get('name'),
            "specialization": request.form.get('specialization'),
            "location": request.form.get('location'),
            "pricing": request.form.get('pricing')
        })
       
        # Portfolio Image Upload logic (Adding a URL to the list)
        new_image = request.form.get('portfolio_url')
        if new_image:
            db["photographers"][email]["portfolio"].append(new_image)
           
        flash("Profile and Portfolio updated successfully!")
        return redirect(url_for('photographer_dashboard'))
       
    return render_template('photographer_profile.html', p=db["photographers"][email])


@app.route('/booking/action/<int:bid>/<action>')
@login_required(role='photographer')
def booking_action(bid, action):
    for b in db["bookings"]:
        if b['id'] == bid and b['p_email'] == session['user']:
            if action == "accept":
                b['status'] = "Confirmed"
            elif action == "reject":
                b['status'] = "Rejected"
            elif action == "complete":
                b['status'] = "Completed" # New Status
               
            flash(f"Booking status updated to {b['status']}!")
            break
    return redirect(url_for('photographer_dashboard'))

@app.route('/admin/delete_user/<email>')
@login_required(role='admin')
def delete_user(email):
    # Check if user exists in the main user database
    if email in db["users"]:
        user_name = db["users"][email].get('name', 'User')
       
        # Remove from all database dictionaries
        db["users"].pop(email, None)
        db["photographers"].pop(email, None)
        db["pending_photographers"].pop(email, None)
       
        # This sends the message you requested back to the admin dashboard
        flash(f"User {user_name} has been removed from the platform.")
    else:
        flash("User not found.")


    return redirect(url_for('admin_dashboard'))

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)





