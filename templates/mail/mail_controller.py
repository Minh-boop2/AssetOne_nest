from flask import request, jsonify

from templates.mail.mail_service import (
    request_forgot_password,
    verify_reset_password_token,
    reset_password,
)


def register_mail_api_routes(app):

    @app.route("/api/mail/forgot-password", methods=["POST"])
    def api_forgot_password():
        data = request.get_json(silent=True) or {}

        result, status_code = request_forgot_password(data)

        return jsonify(result), status_code

    @app.route("/api/mail/reset-password/verify/<string:token>", methods=["GET"])
    def api_verify_reset_password_token(token):
        result, status_code = verify_reset_password_token(token)

        return jsonify(result), status_code

    @app.route("/api/mail/reset-password", methods=["POST"])
    def api_reset_password():
        data = request.get_json(silent=True) or {}

        result, status_code = reset_password(data)

        return jsonify(result), status_code