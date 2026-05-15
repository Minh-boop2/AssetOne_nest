from flask import request, jsonify

from templates.permission.permission_service import (
    seed_default_permissions,
    get_permission_options,
    get_permissions,
    get_permission_by_role,
    update_permission_by_role,
    check_permission,
    get_my_permissions,
    permission_required,
)


def register_permissions_api_routes(app):

    @app.route("/api/permissions/seed", methods=["POST"])
    @permission_required("permissions", "update")
    def api_seed_default_permissions():
        response, status_code = seed_default_permissions()
        return jsonify(response), status_code

    @app.route("/api/permissions/options", methods=["GET"])
    @permission_required("permissions", "view")
    def api_get_permission_options():
        response, status_code = get_permission_options()
        return jsonify(response), status_code

    @app.route("/api/permissions/me", methods=["GET"])
    def api_get_my_permissions():
        response, status_code = get_my_permissions()
        return jsonify(response), status_code

    @app.route("/api/permissions/check", methods=["POST"])
    def api_check_permission():
        data = request.get_json(silent=True) or {}
        response, status_code = check_permission(data)
        return jsonify(response), status_code

    @app.route("/api/permissions", methods=["GET"])
    @permission_required("permissions", "view")
    def api_get_permissions():
        response, status_code = get_permissions()
        return jsonify(response), status_code

    @app.route("/api/permissions/<role>", methods=["GET"])
    @permission_required("permissions", "view")
    def api_get_permission_by_role(role):
        response, status_code = get_permission_by_role(role)
        return jsonify(response), status_code

    @app.route("/api/permissions/<role>", methods=["PUT"])
    @permission_required("permissions", "update")
    def api_update_permission_by_role(role):
        data = request.get_json(silent=True) or {}
        response, status_code = update_permission_by_role(role, data)
        return jsonify(response), status_code