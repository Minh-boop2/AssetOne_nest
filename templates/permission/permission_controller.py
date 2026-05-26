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


# Đăng ký toàn bộ API liên quan đến phân quyền
# File này chỉ nhận request, gọi service xử lý, rồi trả response về frontend
def register_permissions_api_routes(app):

    # Khởi tạo quyền mặc định cho các role trong hệ thống
    # Thường gọi một lần khi mới setup project hoặc muốn reset quyền mặc định
    @app.route("/api/permissions/seed", methods=["POST"])
    @permission_required("permissions", "update")
    def api_seed_default_permissions():
        response, status_code = seed_default_permissions()
        return jsonify(response), status_code

    # Lấy danh sách module và action có thể phân quyền
    # Dùng để frontend hiển thị các checkbox quyền
    @app.route("/api/permissions/options", methods=["GET"])
    @permission_required("permissions", "view")
    def api_get_permission_options():
        response, status_code = get_permission_options()
        return jsonify(response), status_code

    # Lấy quyền của chính user đang đăng nhập
    # Frontend dùng API này để biết user được xem hoặc thao tác trang nào
    @app.route("/api/permissions/me", methods=["GET"])
    def api_get_my_permissions():
        response, status_code = get_my_permissions()
        return jsonify(response), status_code

    # Kiểm tra một user có quyền làm một action trong module hay không
    # Ví dụ kiểm tra user có quyền update tài sản không
    @app.route("/api/permissions/check", methods=["POST"])
    def api_check_permission():
        data = request.get_json(silent=True) or {}
        response, status_code = check_permission(data)
        return jsonify(response), status_code

    # Lấy danh sách phân quyền của tất cả role được phép cấu hình
    @app.route("/api/permissions", methods=["GET"])
    @permission_required("permissions", "view")
    def api_get_permissions():
        response, status_code = get_permissions()
        return jsonify(response), status_code

    # Lấy chi tiết quyền của một role cụ thể
    # Ví dụ: QUAN_LY hoặc NHAN_VIEN
    @app.route("/api/permissions/<role>", methods=["GET"])
    @permission_required("permissions", "view")
    def api_get_permission_by_role(role):
        response, status_code = get_permission_by_role(role)
        return jsonify(response), status_code

    # Cập nhật quyền cho một role cụ thể
    # Body gửi lên cần có field permissions
    @app.route("/api/permissions/<role>", methods=["PUT"])
    @permission_required("permissions", "update")
    def api_update_permission_by_role(role):
        data = request.get_json(silent=True) or {}
        response, status_code = update_permission_by_role(role, data)
        return jsonify(response), status_code
