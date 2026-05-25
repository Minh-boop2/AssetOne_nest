from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from templates.report.report_controller import register_reports_api_routes
from templates.asset.asset_controller import register_assets_api_routes
from templates.assign.assign_controller import register_assign_api_routes
from templates.user.user_controller import register_users_api_routes
from templates.mail.mail_controller import register_mail_api_routes
from templates.permission.permission_controller import register_permissions_api_routes
from templates.activity.activity_controller import register_activity_api_routes


load_dotenv()

app = Flask(__name__)
CORS(app)

register_assets_api_routes(app)
register_assign_api_routes(app)
register_users_api_routes(app)
register_mail_api_routes(app)
register_permissions_api_routes(app)
register_reports_api_routes(app)
register_activity_api_routes(app)


@app.route("/")
def home():
    return jsonify({
        "message": "Backend API is running",
        "assets_api": "/api/assets",
        "assign_api": "/api/assign",
        "users_api": "/api/users",
        "mail_api": "/api/mail",
        "permissions_api": "/api/permissions",
        "reports_api": "/api/reports",
        "activities_api": "/api/activities"
    })


if __name__ == "__main__":
    app.run(debug=True, port=5001)