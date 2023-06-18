import datetime

from bson import ObjectId
from flask import Blueprint, Response, render_template, request, current_app
from flask_login import current_user
from flask_mail import Message

from gmt import mongo, mail
from gmt.utils import parse_json

bp = Blueprint("api", __name__)


@bp.route("/api/")
def api():
    if current_user.is_authenticated:
        current_user.writer = mongo.db.writers.find_one(
            {"_id": ObjectId(current_user.id)}
        )

    if request.method == "POST":
        user_email = request.form.get("email")

        user = mongo.db.users.find_one({"email": user_email})
        if not user:
            return render_template("api/api.html", error="User not found")

        msg = Message(
            "Your API Key",
            recipients=user_email,
            sender=("Good Morning Tech", current_app.config["MAIL_USERNAME"]),
            body=f"""The API key for your account is: {user["_id"]}
            If you didn't request this, you can safely ignore this email.
            """,
        )
        mail.send(msg)
        return render_template("api/api.html", error=None, success=True)

    return render_template("api/api.html", error=None)


@bp.route("/api/news/")
def news():
    api_key = request.headers.get("X-API-KEY")
    if not api_key:
        return Response(status=401)

    user = mongo.db.users.find_one({"_id": ObjectId(api_key)})
    # if the user with that id isn't in the db, return 401
    if not user:
        return Response(status=401)

    posts = list(
        mongo.db.articles.find(
            {
                "date": {
                    "$gte": datetime.datetime.utcnow() - datetime.timedelta(hours=25)
                }
            }
        )
    )

    return parse_json(posts)
