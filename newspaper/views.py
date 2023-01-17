import datetime
import requests

from email_validator import EmailNotValidError, validate_email
from flask import (Blueprint, current_app, redirect, render_template, request, session, abort,
                   url_for)
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import SignatureExpired
from urllib.parse import unquote_plus

from . import mail
from .news import save_posts

bp = Blueprint("views", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/register", methods=("GET", "POST"))
def register():
    error = None
    if request.method == "POST":
        # Get and validate the email
        email = request.form["email"]
        try:
            validate_email(email)
        except EmailNotValidError:
            error = "Invalid email"

        db = current_app.mongo.db
        users = db.users
        # Check if the email is already used
        if users.find_one({"email": email, "confirmed": True}):
            error = "Email already used"

        # Get and validate the time
        time = request.form[
            "time-selection"
        ]
        try:
            time = datetime.datetime.strptime(time, "%H")
        except ValueError:
            error = "Invalid time"

        timezone = request.form["timezone-selection"]
        if "." in timezone:
            time = time + datetime.timedelta(hours=int(timezone.split(".")[0]), minutes=int(timezone.split(".")[1]))
        else:
            time = time + datetime.timedelta(hours=int(timezone))
        time = time.time()

        news_ = []
        bbc = request.form.get("bbc", False)
        techcrunch = request.form.get("techcrunch", False)
        verge = request.form.get("verge", False)
        register = request.form.get("register", False)
        gmt = request.form.get("gmt", False)
        guardian = request.form.get("guardian", False)
        for a in [bbc, techcrunch, verge, register, gmt, guardian]:
            if a:
                news_.append(a)

        # Check if the user has selected at least one news source
        if not news_:
            error = "Please select at least one news source"

        extras = {"codingchallenge": False, "repositories": False}

        try:
            if request.form["codingchallenge"]:
                extras["codingchallenge"] = True
        except KeyError:
            pass
        try:
            if request.form["repositories"]:
                extras["repositories"] = True
        except KeyError:
            pass

        if not error:
            frequency = request.form["frequency"]
            if frequency == "everyday":
                frequency = [1, 2, 3, 4, 5, 6, 7]
            elif frequency == "weekdays":
                frequency = [1, 2, 3, 4, 5]
            elif frequency == "weekends":
                frequency = [6, 7]
            else:
                return abort(400)

            # Create the user
            user = {
                "email": email,
                "time": str(time), # NEEDS TO BE IN UTC
                "confirmed": False,
                "frequency": frequency,
                "news": news_,
                "extras": extras,
            }

            # Insert the user
            if not users.find_one({"email": email}):
                users.insert_one(user)
            elif not users.find_one({"email": email, "confirmed": False}):
                users.update_one({"email": email}, {"$set": user})

            session["confirmed"] = {"email": email, "confirmed": False}

            if current_app.config["FORM_WEBHOOK"]:
                requests.post(current_app.config["FORM_WEBHOOK"], json={"content": f"New user registered: `{email[0]}****@{email.split('@')[1][0]}****.{email.split('@')[1].split('.')[1]}`"})
            else:
                print("Form Webhook not set")
            return redirect(url_for("views.confirm", email=email, next="views.register"))

    try:
        if session.get("confirmed")["confirmed"]:
            email = session.get("confirmed")["email"]
            db = current_app.mongo.db
            users = db.users
            users.update_one({"email": email}, {"$set": {"confirmed": True}})
            session["confirmed"] = {"email": email, "confirmed": False}
            return redirect(url_for("views.news"))
    except TypeError:
        pass

    return render_template("signup.html", error=error, captcha_key=current_app.config["GOOGLE_CAPTCHA_KEY"])


@bp.route("/leave", methods=("POST", "GET"))
def leave():
    error = None
    if request.method == "POST":
        # Get and validate the email
        email = request.form["email"]
        try:
            validate_email(email)
        except EmailNotValidError:
            error = "Invalid email"

        # Check if the email is already used

        if not current_app.mongo.db.users.find_one({"email": email}):
            error = "Email not found"
        if not error:
            return redirect(url_for("views.confirm", email=email, next="views.leave"))

    try:
        if session.get("confirmed")["confirmed"]:
            email = session.get("confirmed")["email"]

            # Get the user from the database
            db = current_app.mongo.db
            users = db.users
            user = users.find_one({"email": email})
            # Delete the user
            users.delete_one(user)

            session["confirmed"] = {"email": email, "confirmed": False}

            return "<h1>Successfully unsubscribed!</h1>"
    except TypeError:
        pass

    return render_template("leave.html", error=error)


@bp.route("/confirm/<email>", methods=("POST", "GET"))
def confirm(email: str):
    """Send a confirmation email to the user and confirms the email if the user clicks on the link
    please supply next arg and set it to the function you want to redirect to after confirmation"""
    # next is where the user will be redirected after confirming
    next = request.args.get("next")
    email = unquote_plus(email)

    # the token
    token = request.args.get("token")

    # this is when the user clicks the link in the email and is presented with a confirm Email button
    if token and request.method == "GET":
        return render_template("confirm.html", error=None, email=email, status="received")

    # Generate the token and send the email
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    token = serializer.dumps(email)
    confirmation_link = url_for(
        "views.confirm", _external=True, token=token, email=email, next=next
    )

    db = current_app.mongo.db
    users = db.users

    # If the email is not in the db error out
    if not users.find_one({"email": email}):
        return abort(404)

    # Create and send the confirmation message
    msg = Message(
        "Confirm your email",
        recipients=[email],
        html=f"""
                <!doctype html>
                <html lang='en'>
                <body style="font-family:sans-serif">
                  <p style="font-size: 1.5rem; font-family: sans-serif;">Hi there!</p>
                  <p style="font-family: sans-serif;">Thanks for joining Good Morning Tech. To confirm your email address and complete your subscription, just click the button below:</p>
                <a href="{confirmation_link}"
                   style="text-decoration:none; font-weight:400; color:#fff;background-color:#DD4444;border-color:black;padding:.3rem .75rem;border-radius: .25rem;"
                   target="_blank">Confirm Email</a>
                  <p>In case the button doesnt works <a href="{confirmation_link}">click me</a></p>
                  
                <p>This link is only active for 5 minutes, so be sure to use it within that time. If you miss the deadline, just resubscribe and we'll send you a new link.</p>
                <p>Need help? Just email us at <a href="mailto:support@goodmorningtech.news" style="text-decoration:none; color: #DD4444; font-weight: 600;">support@goodmorningtech.news</a>. We're happy to help.</p>
                <p>Thanks again,</p>
                <p>Good Morning Tech</p>
                <hr style="border:solid 1px black">
                <small>You can safely ignore this email if you didn't request confirmation.
                Someone else might have typed your email address by mistake.</small>
                </body>
                </html>
    """
    )
    mail.send(msg)

    # this is when the user clicks the confirm Email button
    if request.method == "POST" and token:
        try:
            serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
            email = serializer.loads(token, max_age=300)
        except SignatureExpired:
            return render_template("confirm.html", error="Token expired")
        except:
            return render_template("confirm.html", error="The token is invalid!")

        session["confirmed"] = {"email": email, "confirmed": True}
        if not next:
            # if next is not defined he goes to the homepage
            return redirect(url_for("views.index"))
        # if next is defined he goes to the page he was on before and the session stuff above is to continue
        # from where he left off
        return redirect(url_for(next, email=email))
    return render_template("confirm.html", error=None, email=email, status="sent")


@bp.route("/news")
def news():
    posts = save_posts()
    return render_template("news.html", posts=posts)


@bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html')


@bp.route("/<path:path>")
def catch_all(path):
    return render_template("404.html")
