# File này khai báo các API liên quan đến hồ sơ cá nhân
# Frontend gọi các API này để lấy thông tin user đang đăng nhập, cập nhật hồ sơ và đổi mật khẩu

from flask import request, jsonify, session

from templates.profile.profile_service import (
    get_my_profile,
    update_my_profile,
    change_my_password,
)


# Lấy id người dùng hiện tại từ header X-User-Id hoặc từ session
def get_current_user_id():
    user_id = request.headers.get("X-User-Id")

    if user_id:
        return str(user_id)

    user_id = (
        session.get("current_user_id")
        or session.get("user_id")
        or session.get("id")
    )

    if user_id:
        return str(user_id)

    user = session.get("user") or session.get("current_user")

    if isinstance(user, dict):
        return str(user.get("id") or user.get("_id") or user.get("user_id") or "")

    return ""


# Đăng ký toàn bộ route API cho hồ sơ cá nhân
def register_profile_api_routes(app):

    @app.route("/api/profile/me", methods=["GET"])
    # API lấy thông tin hồ sơ của người đang đăng nhập
    def api_get_my_profile():
        user_id = get_current_user_id()
        response, status_code = get_my_profile(user_id)
        return jsonify(response), status_code

    @app.route("/api/profile/me", methods=["PUT"])
    # API cập nhật thông tin hồ sơ của người đang đăng nhập
    def api_update_my_profile():
        user_id = get_current_user_id()
        data = request.get_json(silent=True) or {}
        response, status_code = update_my_profile(user_id, data)
        return jsonify(response), status_code

    @app.route("/api/profile/change-password", methods=["POST"])
    # API đổi mật khẩu của người đang đăng nhập
    def api_change_my_password():
        user_id = get_current_user_id()
        data = request.get_json(silent=True) or {}
        response, status_code = change_my_password(user_id, data)
        return jsonify(response), status_code