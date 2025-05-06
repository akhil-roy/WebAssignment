import os
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS")

# Configure Email (Update credentials before using)
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT"))
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS")
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL")

mail = Mail(app)
db = SQLAlchemy(app)

# Define database model
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.String(50))
    order_id = db.Column(db.String(50))
    restaurant_name = db.Column(db.String(100))
    locality = db.Column(db.String(100))
    order_status = db.Column(db.String(50))
    order_total = db.Column(db.Float)

with app.app_context():
        db.create_all()  # Ensure table exists

# Index page, Upload and Display data
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["csv_file"]
        if file:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(file_path)

            # Process CSV in chunks
            chunk_size = 10000
            new_entries = []
            for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                for _, row in chunk.iterrows():
                    order = Order(
                        order_date=row["Order Date"],
                        order_id=row["ONDC Order ID"],
                        restaurant_name=row["Restaurant Name"],
                        locality=row["Locality"],
                        order_status=row["Order Status"],
                        order_total=row["Order Total"]
                    )
                    db.session.add(order)
                    new_entries.append(order)
                db.session.commit()

            flash("File uploaded and data processed successfully!")
            return redirect(url_for('index'))
        
    return render_template("index.html")

@app.route("/display")
def display():
    page = request.args.get("page", 1, type=int)
    per_page = 20
    orders = Order.query.paginate(page=page, per_page=per_page)
    return render_template("index.html", orders=orders)

def send_email(recipient, subject, body):
    """Send email using smtplib instead of Flask-Mail"""
    sender_email = os.getenv("MAIL_USERNAME")
    sender_password = os.getenv("MAIL_PASSWORD")
    smtp_server = os.getenv("MAIL_SERVER")
    smtp_port = int(os.getenv("MAIL_PORT"))

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient, msg.as_string())
        flash("Email sent successfully!", "success")
    except Exception as e:
        flash(f"Failed to send email: {e}", "danger")

@app.route("/send_summary", methods=["POST"])
def send_summary():
    date_filter = request.form.get("date")
    recipient_email = request.form.get("email")
    summary = db.session.query(Order.restaurant_name, db.func.count(Order.id)).filter_by(order_date=date_filter).group_by(Order.restaurant_name).all()

    if summary:
        # Prepare summary as an email body
        summary_text = f"Date-Wise Order Summary for {date_filter}:\n\n"
        for restaurant, count in summary:
            summary_text += f"- {restaurant}: {count} orders\n"
        
        send_email(recipient_email, "Date-wise Order Summary", summary_text)
        flash("Summary email sent successfully!")
        return redirect(url_for('display'))

    flash("No data available for this date!", "warning")
    return render_template("index.html")

@app.route("/filter", methods=["POST"])
def filter_data():
    date_filter = request.form.get("date")
    restaurant_filter = request.form.get("restaurant_name")
    orders = Order.query.filter_by(order_date=date_filter, restaurant_name=restaurant_filter).limit(20).all()
    return render_template("index.html", orders=orders)

@app.route("/delete", methods=["POST"])
def delete_data():
    date_filter = request.form.get("date")
    restaurant_filter = request.form.get("restaurant_name")
    Order.query.filter_by(order_date=date_filter, restaurant_name=restaurant_filter).delete()
    db.session.commit()
    flash("Data deleted successfully!")
    return redirect(url_for('display'))

if __name__ == "__main__":
    app.run(debug=True)
