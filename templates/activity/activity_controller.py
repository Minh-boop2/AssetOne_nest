# File này khai báo các API liên quan đến lịch sử hoạt động

from flask import request, jsonify, send_file
from bson import ObjectId
from mongo import users_collection

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


# Bổ sung: lấy id đối tượng từ URL API, ví dụ /api/users/<id>
def get_api_target_id_from_path(path):
    parts = [part for part in str(path or "").split("/") if part]

    if len(parts) >= 3 and parts[0] == "api":
        return parts[2]

    return None


# Bổ sung: lấy dữ liệu JSON từ response để biết tên đối tượng sau khi API chạy xong
def get_response_json_data(response):
    try:
        return response.get_json(silent=True) or {}
    except Exception:
        return {}


# Bổ sung: lấy giá trị đầu tiên có tồn tại trong dict
def get_first_value_from_dict(data, *keys):
    if not isinstance(data, dict):
        return None

    for key in keys:
        value = data.get(key)

        if value not in [None, ""]:
            return value

    return None


# Bổ sung: lấy tên đối tượng từ response JSON trả về của API
def get_target_name_from_response_json(response_json):
    if not isinstance(response_json, dict):
        return None

    data = response_json.get("data")

    if isinstance(data, dict):
        return get_first_value_from_dict(
            data,
            "target_name",
            "asset_name",
            "full_name",
            "employee_name",
            "name",
            "title",
            "email",
            "employee_code",
        )

    return get_first_value_from_dict(
        response_json,
        "target_name",
        "asset_name",
        "full_name",
        "employee_name",
        "name",
        "title",
        "email",
        "employee_code",
    )


# Bổ sung: lấy id đối tượng từ response JSON trả về của API
def get_target_id_from_response_json(response_json):
    if not isinstance(response_json, dict):
        return None

    data = response_json.get("data")

    if isinstance(data, dict):
        return get_first_value_from_dict(
            data,
            "target_id",
            "id",
            "_id",
            "asset_id",
            "user_id",
            "assign_id",
            "report_id",
        )

    return get_first_value_from_dict(
        response_json,
        "target_id",
        "id",
        "_id",
        "asset_id",
        "user_id",
        "assign_id",
        "report_id",
    )


# Bổ sung: lấy tên người dùng từ database nếu URL là /api/users/<id>
def get_user_display_name_by_id(user_id):
    if not user_id or not ObjectId.is_valid(str(user_id)):
        return None

    user = users_collection.find_one(
        {"_id": ObjectId(str(user_id))},
        {
            "full_name": 1,
            "email": 1,
            "employee_code": 1,
        }
    )

    if not user:
        return None

    return (
        user.get("full_name")
        or user.get("email")
        or user.get("employee_code")
    )


# Bổ sung: tên mặc định theo module để không còn hiện /api/... trên giao diện
def get_default_target_name_by_module(module):
    module = str(module or "").lower()

    module_name_map = {
        "users": "Người dùng",
        "profile": "Hồ sơ cá nhân",
        "assets": "Tài sản",
        "assign": "Cấp phát",
        "reports": "Báo cáo",
        "activities": "Hoạt động",
        "permissions": "Phân quyền",
        "mail": "Mail",
        "system": "Hệ thống",
    }

    return module_name_map.get(module, None)


# Bổ sung: gom logic lấy target_id và target_name cho auto log
def build_auto_log_target_info(data, response, module, path):
    response_json = get_response_json_data(response)

    target_id = (
        data.get("target_id")
        or data.get("asset_id")
        or data.get("user_id")
        or data.get("assign_id")
        or data.get("report_id")
        or get_target_id_from_response_json(response_json)
        or get_api_target_id_from_path(path)
    )

    target_name = (
        data.get("target_name")
        or data.get("asset_name")
        or data.get("full_name")
        or data.get("employee_name")
        or data.get("name")
        or data.get("title")
        or get_target_name_from_response_json(response_json)
    )

    # Bổ sung: riêng module user thì lấy tên user từ database bằng id trong URL
    if not target_name and str(module or "").lower() == "users":
        target_name = get_user_display_name_by_id(target_id)

    # Bổ sung: fallback cuối cùng để giao diện không hiển thị path API
    if not target_name:
        target_name = get_default_target_name_by_module(module)

    return target_id, target_name


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

            # Bổ sung: lấy target_id và target_name thông minh hơn để không hiển thị /api/users/<id>
            target_id, target_name = build_auto_log_target_info(
                data=data,
                response=response,
                module=module,
                path=request.path,
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