from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime, timedelta
import json
import ast
from flask import session, redirect, url_for
import os
import csv
from werkzeug.utils import secure_filename
from flask import Response



app = Flask(__name__)
DB_NAME = "database.db"

# ===== UPLOAD FOLDERS =====
# -------- UPLOAD FOLDERS --------
MENU_UPLOAD_FOLDER = "static/uploads"
REVIEW_UPLOAD_FOLDER = "static/reviews"
REVIEW_UPLOAD_FOLDER = "static/reviews"



os.makedirs(MENU_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REVIEW_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REVIEW_UPLOAD_FOLDER, exist_ok=True)

app.config["MENU_UPLOAD_FOLDER"] = MENU_UPLOAD_FOLDER
app.config["REVIEW_UPLOAD_FOLDER"] = REVIEW_UPLOAD_FOLDER
app.config["REVIEW_UPLOAD_FOLDER"] = REVIEW_UPLOAD_FOLDER

app.secret_key = "kitchen-secret-key"  # session ku mandatory

#++++++++++kitchen and admin pass________+++#
KITCHEN_USER = "kitchen"
KITCHEN_PASS = "1234"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


# ---------------- DB SETUP ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()

    
    # ORDERS
    db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            table_name TEXT,
            items TEXT,
            subtotal INTEGER,
            discount INTEGER,
            gst INTEGER,
            total INTEGER,
            status TEXT,
            created_at TEXT
        )
    """)
    #  review table--#
    db.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        rating INTEGER,
        message TEXT,
        image TEXT,
        created_at TEXT
        visible INTEGER DEFAULT 1
    )
    

    """)


    # MENU ITEMS (NEW)
    db.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price INTEGER,
            image_url TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    db.execute("""
         CREATE TABLE IF NOT EXISTS help_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            table_no TEXT,
            issue_type TEXT,
            message TEXT,
            image TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
    """)

 
    db.commit()

init_db()



# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/menu")
def menu():
    db = get_db()
    veg = db.execute(
        "SELECT * FROM menu_items WHERE category='veg' AND active=1"
    ).fetchall()
    nonveg = db.execute(
        "SELECT * FROM menu_items WHERE category='nonveg' AND active=1"
    ).fetchall()

    return render_template("menu.html", veg=veg, nonveg=nonveg)

# ---------------- PLACE ORDER API ----------------#
@app.route("/api/place-order", methods=["POST"])
def place_order():
    data = request.json   # frontend la irundhu varra data

    # items object → JSON string
    items_json = json.dumps(data["items"])

    db = get_db()
    cursor = db.execute("""
        INSERT INTO orders
        (customer_name, table_name, items, subtotal, discount, gst, total, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        data["name"],
        data["table"],
        items_json,
        data["subtotal"],
        data["discount"],
        data["gst"],
        data["total"],
        "Pending",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    db.commit()

    # 🔥 newly inserted order id
    order_id = cursor.lastrowid

    return jsonify({
        "success": True,
        "order_id": order_id
    })

#============kitchen login==--#

@app.route("/kitchen_login", methods=["GET", "POST"])
def kitchen_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == KITCHEN_USER and password == KITCHEN_PASS:
            session["kitchen_logged_in"] = True
            return redirect("/kitchen")
        else:
            return render_template(
                "kitchen_login.html",
                error="Invalid username or password"
            )

    return render_template("kitchen_login.html")

#------------------admin-login=========#

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if u == ADMIN_USER and p == ADMIN_PASS:
            session["admin_logged_in"] = True
            return redirect("/admin")
        else:
            return render_template("admin_login.html", error="Invalid login")

    return render_template("admin_login.html")

#---------------admin=logout---#
@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin_login")

# -------- ADMIN MENU PAGE --------
@app.route("/admin/menu", methods=["GET", "POST"])
def admin_menu():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        price = request.form["price"]

        image = request.files["image"]   # 🔥 FILE INPUT

        if image.filename == "":
            return "No image selected"

        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["MENU_UPLOAD_FOLDER"], filename))


        db.execute("""
            INSERT INTO menu_items
            (name, category, price, image_url, active, created_at)
            VALUES (?,?,?,?,1,datetime('now'))
        """, (name, category, price, filename))

        db.commit()
        return redirect("/admin/menu")

    items = db.execute("SELECT * FROM menu_items ORDER BY id DESC").fetchall()
    return render_template("admin_menu.html", items=items)

#---------------dish analytics=====#
@app.route("/admin/analytics", methods=["GET", "POST"])
def admin_analytics():
    db = get_db()

    # Fetch all orders
    rows = db.execute("SELECT * FROM orders").fetchall()

    dish_stats = {}
    dish_names = set()

    # Build dish-wise stats
    for r in rows:
        items = json.loads(r["items"])

        for name, data in items.items():
            dish_names.add(name)

            if name not in dish_stats:
                dish_stats[name] = {
                    "qty": 0,
                    "sales": 0
                }

            dish_stats[name]["qty"] += data["qty"]
            dish_stats[name]["sales"] += data["qty"] * data["price"]

    selected_dish = request.form.get("dish")
    result = None

    # ✅ IMPORTANT: correct indentation
    if selected_dish and selected_dish in dish_stats:
        revenue = dish_stats[selected_dish]["sales"]
        discount = round(revenue * 0.10)
        profit = revenue - discount

        result = {
            "dish": selected_dish,
            "qty": dish_stats[selected_dish]["qty"],
            "revenue": revenue,
            "discount": discount,
            "profit": profit
        }

    # ✅ ALWAYS return template
    return render_template(
        "admin_analytics.html",
        dish_names=sorted(dish_names),
        selected_dish=selected_dish,
        result=result
    )

#=============------order status---#
@app.route("/order-status/<int:order_id>")
def order_status(order_id):
    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE id=?",
        (order_id,)
    ).fetchone()

    if not order:
        return "Order not found", 404

    items = json.loads(order["items"])

    return render_template(
        "order_status.html",
        order=order,
        items=items
    )



# -------- UPDATE PRICE / TOGGLE --------
@app.route("/admin/menu/update", methods=["POST"])
def update_menu():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()
    db.execute("""
        UPDATE menu_items
        SET price=?, active=?
        WHERE id=?
    """, (
        request.form["price"],
        request.form["active"],
        request.form["id"]
    ))
    db.commit()
    return redirect("/admin/menu")

# ---------------- KITCHEN VIEW ----------------


@app.route("/kitchen")
def kitchen():
    if not session.get("kitchen_logged_in"):
        return redirect("/kitchen-login")

    cleanup_old_orders()  # 24 hrs cleanup (previous logic)

    db = get_db()
    rows = db.execute("""
        SELECT * FROM orders
        WHERE date(created_at) = date('now')
        ORDER BY id DESC
    """).fetchall()

    orders = []
    for r in rows:
        try:
            items = json.loads(r["items"])
        except:
            import ast
            items = ast.literal_eval(r["items"])

        orders.append({
            "id": r["id"],
            "customer_name": r["customer_name"],
            "table_name": r["table_name"],
            "items_parsed": items,
            "subtotal": r["subtotal"],
            "discount": r["discount"],
            "gst": r["gst"],
            "total": r["total"],
            "status": r["status"],
            "created_at": r["created_at"]
        })

    return render_template("kitchen.html", orders=orders)

@app.route("/kitchen_logout")
def kitchen_logout():
    session.pop("kitchen_logged_in", None)
    return redirect("/kitchen_login")

def cleanup_old_orders():
    db = get_db()
    db.execute("""
        DELETE FROM orders
        WHERE datetime(created_at) < datetime('now', '-1 day')
    """)
    db.commit()

#=================admin-dashboard====#
@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()

    # TODAY STATS
    stats = db.execute("""
        SELECT
          COUNT(*) as orders,
          SUM(total) as revenue,
          SUM(discount) as discount,
          SUM(total - gst) as profit
        FROM orders
        WHERE date(created_at) = date('now')
    """).fetchone()

    # TOP SELLING ITEM
    rows = db.execute("SELECT items FROM orders WHERE date(created_at)=date('now')").fetchall()
    dish_count = {}
    import ast, json

    for r in rows:
        try:
            items = json.loads(r["items"])
        except:
            items = ast.literal_eval(r["items"])

        for k,v in items.items():
            dish_count[k] = dish_count.get(k,0) + v["qty"]

    top_item = max(dish_count, key=dish_count.get) if dish_count else "No Data"

    # ALL ORDERS
    orders = db.execute("""
        SELECT * FROM orders
        WHERE date(created_at)=date('now')
        ORDER BY id DESC
    """).fetchall()

    return render_template("admin.html",
        stats=stats,
        top_item=top_item,
        orders=orders
    )


# ---------------- UPDATE STATUS API ----------------
@app.route("/api/update-status", methods=["POST"])
def update_status():
    data = request.json

    db = get_db()
    db.execute(
        "UPDATE orders SET status=? WHERE id=?",
        (data["status"], data["id"])
    )
    db.commit()

    return jsonify({"success": True})

    #==========admin--download====#
@app.route("/admin/download-sales")
def download_sales():
    period = request.args.get("period", "day")  # day / week / month

    db = get_db()
    now = datetime.now()

    if period == "day":
        start = now.strftime("%Y-%m-%d 00:00:00")
    elif period == "week":
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
    elif period == "month":
        start = now.strftime("%Y-%m-01 00:00:00")
    else:
        start = "1970-01-01 00:00:00"

    rows = db.execute(
        "SELECT * FROM orders WHERE created_at >= ?",
        (start,)
    ).fetchall()

    def generate():
        data = csv.writer(Echo())
        yield data.writerow([
            "Order ID","Customer","Table",
            "Items","Subtotal","Discount",
            "GST","Total","Status","Date"
        ])

        for r in rows:
            yield data.writerow([
                r["id"],
                r["customer_name"],
                r["table_name"],
                r["items"],
                r["subtotal"],
                r["discount"],
                r["gst"],
                r["total"],
                r["status"],
                r["created_at"]
            ])

    filename = f"sales_{period}.csv"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename={filename}"
        }
    )

class Echo:
    def write(self, value):
        return value
@app.route("/admin/reviews")
def admin_reviews():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()
    reviews = db.execute("""
        SELECT * FROM reviews
        ORDER BY id DESC
    """).fetchall()

    return render_template("admin_reviews.html", reviews=reviews)


#---------------=========hide/sh0w-------#
@app.route("/admin/review-toggle/<int:id>")
def toggle_review(id):
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()
    r = db.execute("SELECT visible FROM reviews WHERE id=?", (id,)).fetchone()

    new_status = 0 if r["visible"] == 1 else 1
    db.execute("UPDATE reviews SET visible=? WHERE id=?", (new_status, id))
    db.commit()

    return redirect("/admin/reviews")


#================delete==============#

@app.route("/admin/review-delete/<int:id>")
def delete_review(id):
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()
    db.execute("DELETE FROM reviews WHERE id=?", (id,))
    db.commit()

    return redirect("/admin/reviews")

# ---------- REVIEW PAGE ----------
@app.route("/reviews", methods=["GET", "POST"])
def user_reviews():
    db = get_db()

    if request.method == "POST":
        name = request.form["name"]
        rating = request.form["rating"]
        message = request.form["message"]

        image_file = request.files.get("image")
        filename = ""

        if image_file and image_file.filename != "":
            filename = datetime.now().strftime("%Y%m%d%H%M%S_") + image_file.filename
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        db.execute("""
            INSERT INTO reviews (name, rating, message, image, visible, created_at)
            VALUES (?,?,?,?,1,?)
        """, (
            name, rating, message, filename,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        db.commit()
        return redirect("/reviews")

    reviews = db.execute("""
        SELECT * FROM reviews
        WHERE visible = 1
        ORDER BY id DESC
    """).fetchall()

    return render_template("reviews.html", reviews=reviews)
# -------- HELP PAGE --------
@app.route("/help", methods=["GET", "POST"])
def help_page():
    db = get_db()

    if request.method == "POST":
        name = request.form["name"]
        table_no = request.form["table"]
        issue_type = request.form["issue"]
        message = request.form["message"]

        image_file = request.files.get("image")
        filename = ""

        if image_file and image_file.filename != "":
            filename = datetime.now().strftime("%Y%m%d%H%M%S_") + image_file.filename
            image_file.save(os.path.join("static/help", filename))

        db.execute("""
            INSERT INTO help_requests
            (name, table_no, issue_type, message, image, created_at)
            VALUES (?,?,?,?,?,?)
        """, (
            name,
            table_no,
            issue_type,
            message,
            filename,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        db.commit()

        return jsonify({"success": True})

    return render_template("help.html")

# ================= ADMIN HELP DASHBOARD =================
@app.route("/admin/help")
def admin_help():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()
    requests = db.execute("""
        SELECT * FROM help_requests
        ORDER BY id DESC
    """).fetchall()

    return render_template("admin_help.html", requests=requests)


# -------- MARK HELP AS RESOLVED --------
@app.route("/admin/help-resolve/<int:id>")
def resolve_help(id):
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()
    db.execute(
        "UPDATE help_requests SET status='Resolved' WHERE id=?",
        (id,)
    )
    db.commit()
    return redirect("/admin/help")


# -------- DELETE HELP REQUEST --------
@app.route("/admin/help-delete/<int:id>")
def delete_help(id):
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    db = get_db()
    db.execute("DELETE FROM help_requests WHERE id=?", (id,))
    db.commit()
    return redirect("/admin/help")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()
