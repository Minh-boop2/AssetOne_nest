# File: activity_controller.py
# File này khai báo các API liên quan đến lịch sử hoạt động

from flask import request, jsonify, send_file
from templates.activity.activity_service import (
    create_activity_log,
    get_activities,
    get_activity_by_id,
    get_activity_stats,
    get_activity_filter_options,
    get_activities_export,
    build_action_from_request,
    detect_module_from_path,
    clean_metadata,
)


# Lấy id người dùng hiện tại từ header X-User-Id
def get_current_user_id_from_header():
    return request.headers.get("X-User-Id")


# Đăng ký toàn bộ route API cho màn hình hoạt động
def register_activity_api_routes(app):

    @app.route("/api/activities", methods=["GET"])
    # API lấy danh sách hoạt động, có phân trang và bộ lọc
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
    # API lấy danh sách lựa chọn cho bộ lọc hoạt động
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
    # API lấy thống kê tổng số hoạt động tạo, sửa, xóa
    def api_get_activity_stats():
        current_user_id = get_current_user_id_from_header()

        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        response, status_code = get_activity_stats(current_user_id)

        return jsonify(response), status_code
    
    @app.route("/api/activities/export", methods=["GET"])
    # API xuất danh sách hoạt động ra file Excel
    def api_export_activities():
        current_user_id = get_current_user_id_from_header()

        if not current_user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        file_stream, filename, error_response, status_code = get_activities_export(
            request.args,
            current_user_id
        )

        if error_response:
            return jsonify(error_response), status_code

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    @app.route("/api/activities/<activity_id>", methods=["GET"])
    # API lấy chi tiết 1 hoạt động theo id
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
    # API tạo log hoạt động thủ công
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
    # Tự động ghi log sau khi API thay đổi dữ liệu chạy xong
    def auto_log_activity(response):
        try:
            # Các path này đã tự ghi log riêng nên không ghi thêm lần nữa
            manual_log_paths = [
                "/api/assets",
                "/api/assign",
                "/api/reports",
            ]

            for path_prefix in manual_log_paths:
                if request.path.startswith(path_prefix):
                    return response

            # Chỉ ghi log cho các method có thể làm thay đổi dữ liệu
            if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
                return response

            if request.path.startswith("/api/activities"):
                return response

            if request.path == "/api/users/login":
                return response

            if not request.path.startswith("/api/"):
                return response

            # Nếu API lỗi thì không ghi log thành công
            if response.status_code >= 400:
                return response

            current_user_id = get_current_user_id_from_header()

            if not current_user_id:
                return response

            data = request.get_json(silent=True) or {}

            # Ưu tiên action frontend gửi lên, nếu không có thì tự tạo action theo method và path
            action = (
                data.get("activity_action")
                or data.get("action_log")
                or data.get("log_action")
                or build_action_from_request(request.method, request.path)
            )

            module = detect_module_from_path(request.path)

            # Cố gắng lấy id đối tượng bị tác động từ body request
            target_id = (
                data.get("target_id")
                or data.get("asset_id")
                or data.get("user_id")
                or data.get("assign_id")
                or data.get("report_id")
            )

            # Cố gắng lấy tên đối tượng bị tác động từ body request
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