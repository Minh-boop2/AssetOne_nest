from flask import request, jsonify

from templates.user.user_service import (
    create_user,
    get_users,
    get_user_by_id,
    update_user,
    delete_user,
    login_user,
    get_users_stats,
)

from templates.permission.permission_service import permission_required


def register_users_api_routes(app):

    # API đăng nhập user
    # Không gắn permission_required vì chưa đăng nhập thì chưa có X-User-Id
    @app.route("/api/users/login", methods=["POST"])
    def api_login_user():
        data = request.get_json(silent=True) or {}
        response, status_code = login_user(data)
        return jsonify(response), status_code

    # API lấy thống kê user
    @app.route("/api/users/stats", methods=["GET"])
    @permission_required("users", "view")
    def api_get_users_stats():
        response, status_code = get_users_stats()
        return jsonify(response), status_code

    # API tạo user mới
    @app.route("/api/users", methods=["POST"])
    @permission_required("users", "create")
    def api_create_user():
        data = request.get_json(silent=True) or {}
        response, status_code = create_user(data)
        return jsonify(response), status_code

    # API lấy danh sách user
    # Có thể phân trang, tìm kiếm và lọc theo query trên URL
    @app.route("/api/users", methods=["GET"])
    @permission_required("users", "view")
    def api_get_users():
        response, status_code = get_users(request.args)
        return jsonify(response), status_code

    # API lấy chi tiết một user theo id
    @app.route("/api/users/<id>", methods=["GET"])
    @permission_required("users", "view")
    def api_get_user_by_id(id):
        response, status_code = get_user_by_id(id)
        return jsonify(response), status_code

    # API cập nhật thông tin user theo id
    @app.route("/api/users/<id>", methods=["PUT"])
    @permission_required("users", "update")
    def api_update_user(id):
        data = request.get_json(silent=True) or {}
        response, status_code = update_user(id, data)
        return jsonify(response), status_code

    # API xóa user theo id
    @app.route("/api/users/<id>", methods=["DELETE"])
    @permission_required("users", "delete")
    def api_delete_user(id):
        response, status_code = delete_user(id)
        return jsonify(response), status_code