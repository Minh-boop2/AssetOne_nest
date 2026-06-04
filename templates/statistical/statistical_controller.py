# File: statistical_controller.py
# Nhiệm vụ:
# - Khai báo API cho module thống kê nhân viên.
# - Chỉ giữ API nhân viên.
# - Không còn API doanh thu, tài sản, cấp phát, báo cáo.

from flask import jsonify

from templates.statistical.statistical_service import (
    get_statistical_overview,
    get_statistical_employees,
)


def register_statistical_api_routes(app):
    print("REGISTER STATISTICAL EMPLOYEE API ROUTES OK")

    # API test nhanh để kiểm tra module statistical đã được register chưa
    @app.route("/api/statistical/test", methods=["GET"])
    def api_statistical_test():
        return jsonify({
            "success": True,
            "message": "Statistical employee API registered"
        }), 200

    # API overview giữ lại để tránh lỗi nếu frontend cũ còn gọi route này.
    # Dữ liệu trả về vẫn là thống kê nhân viên.
    @app.route("/api/statistical/overview", methods=["GET"])
    def api_get_statistical_overview():
        response, status_code = get_statistical_overview()

        return jsonify(response), status_code

    # API chính cho trang thống kê nhân viên
    @app.route("/api/statistical/employees", methods=["GET"])
    def api_get_statistical_employees():
        response, status_code = get_statistical_employees()

        return jsonify(response), status_code