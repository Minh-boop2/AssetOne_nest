from flask import request, jsonify

from templates.activity.activity_service import (
    create_activity_log,
    get_activities,
    get_activity_by_id,
    get_activity_stats,
    get_activity_filter_options,
    build_action_from_request,
    detect_module_from_path,
    clean_metadata,
)


def get_current_user_id_from_header():
    return request.headers.get("X-User-Id")


def register_activity_api_routes(app):

    @app.route("/api/activities", methods=["GET"])
    def api_get_activities():
        current_user_id = get_current_user_id_from_header()

        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        response, status_code = get_activities(request.args, current_user_id)

        return jsonify(response), status_code

    @app.route("/api/activities/filter-options", methods=["GET"])
    def api_get_activity_filter_options():
        current_user_id = get_current_user_id_from_header()

        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        response, status_code = get_activity_filter_options(current_user_id)

        return jsonify(response), status_code

    @app.route("/api/activities/stats", methods=["GET"])
    def api_get_activity_stats():
        current_user_id = get_current_user_id_from_header()

        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        response, status_code = get_activity_stats(current_user_id)

        return jsonify(response), status_code

    @app.route("/api/activities/<activity_id>", methods=["GET"])
    def api_get_activity_by_id(activity_id):
        current_user_id = get_current_user_id_from_header()

        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        response, status_code = get_activity_by_id(activity_id, current_user_id)

        return jsonify(response), status_code

    @app.route("/api/activities", methods=["POST"])
    def api_create_activity():
        current_user_id = get_current_user_id_from_header()

        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        data = request.get_json(silent=True) or {}

        response, status_code = create_activity_log(
            user_id=current_user_id,
            action=data.get("action"),
            module=data.get("module"),
            method=request.method,
            path=request.path,
            status_code=201,
            target_id=data.get("target_id"),
            target_name=data.get("target_name"),
            metadata=clean_metadata(data.get("metadata", {})),
        )

        return jsonify(response), status_code

    @app.after_request
    def auto_log_activity(response):
        try:
            manual_log_paths = [
                "/api/assets",
                "/api/assign",
                "/api/reports",
            ]

            for path_prefix in manual_log_paths:
                if request.path.startswith(path_prefix):
                    return response

            if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
                return response

            if request.path.startswith("/api/activities"):
                return response

            if request.path == "/api/users/login":
                return response

            if not request.path.startswith("/api/"):
                return response

            if response.status_code >= 400:
                return response

            current_user_id = get_current_user_id_from_header()

            if not current_user_id:
                return response

            data = request.get_json(silent=True) or {}

            action = (
                data.get("activity_action")
                or data.get("action_log")
                or data.get("log_action")
                or build_action_from_request(request.method, request.path)
            )

            module = detect_module_from_path(request.path)

            target_id = (
                data.get("target_id")
                or data.get("asset_id")
                or data.get("user_id")
                or data.get("assign_id")
                or data.get("report_id")
            )

            target_name = (
                data.get("target_name")
                or data.get("asset_name")
                or data.get("full_name")
                or data.get("employee_name")
                or data.get("name")
                or data.get("title")
            )

            create_activity_log(
                user_id=current_user_id,
                action=action,
                module=module,
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                target_id=target_id,
                target_name=target_name,
                metadata=clean_metadata(data),
            )

            return response

        except Exception:
            return response