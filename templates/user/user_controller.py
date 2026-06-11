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

from templates.permission.permission_service import (
    permission_required,
    get_current_user_from_request,
)


def register_users_api_routes(app):

    @app.route("/api/users/login", methods=["POST"])
    def api_login_user():
        data = request.get_json(silent=True) or {}
        response, status_code = login_user(data)
        return jsonify(response), status_code

    @app.route("/api/users/stats", methods=["GET"])
    @permission_required("users", "view")
    def api_get_users_stats():
        response, status_code = get_users_stats()
        return jsonify(response), status_code

    @app.route("/api/users", methods=["POST"])
    @permission_required("users", "create")
    def api_create_user():
        data = request.get_json(silent=True) or {}
        response, status_code = create_user(data)
        return jsonify(response), status_code

    @app.route("/api/users", methods=["GET"])
    @permission_required("users", "view")
    def api_get_users():
        response, status_code = get_users(request.args)
        return jsonify(response), status_code

    @app.route("/api/users/<id>", methods=["GET"])
    @permission_required("users", "view")
    def api_get_user_by_id(id):
        response, status_code = get_user_by_id(id)
        return jsonify(response), status_code

    @app.route("/api/users/<id>", methods=["PUT"])
    @permission_required("users", "update")
    def api_update_user(id):
        data = request.get_json(silent=True) or {}
        current_user = get_current_user_from_request()

        # NOTE: Truyền user hiện tại xuống service để kiểm tra QUAN_LY được sửa ai.
        response, status_code = update_user(
            id,
            data,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/users/<id>", methods=["DELETE"])
    @permission_required("users", "delete")
    def api_delete_user(id):
        current_user = get_current_user_from_request()

        # NOTE: Giữ bảo vệ ở API delete nếu sau này mở quyền xóa/ngưng hoạt động bằng DELETE.
        response, status_code = delete_user(
            id,
            current_user=current_user,
        )

        return jsonify(response), status_code