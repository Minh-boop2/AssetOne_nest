# File: statistical_controller.py
# File này khai báo API cho module thống kê
# Chỉ đọc dữ liệu, không sửa dữ liệu module khác

from flask import jsonify

from templates.statistical.statistical_service import (
    get_statistical_overview,
    get_statistical_employees,
    get_statistical_assets,
    get_statistical_assign,
    get_statistical_report,
)


def register_statistical_api_routes(app):
    print("REGISTER STATISTICAL API ROUTES OK")

    @app.route("/api/statistical/test", methods=["GET"])
    def api_statistical_test():
        return jsonify({
            "success": True,
            "message": "Statistical API registered"
        }), 200

    @app.route("/api/statistical/overview", methods=["GET"])
    def api_get_statistical_overview():
        response, status_code = get_statistical_overview()

        return jsonify(response), status_code

    @app.route("/api/statistical/employees", methods=["GET"])
    def api_get_statistical_employees():
        response, status_code = get_statistical_employees()

        return jsonify(response), status_code

    @app.route("/api/statistical/assets", methods=["GET"])
    def api_get_statistical_assets():
        response, status_code = get_statistical_assets()

        return jsonify(response), status_code

    @app.route("/api/statistical/assign", methods=["GET"])
    def api_get_statistical_assign():
        response, status_code = get_statistical_assign()

        return jsonify(response), status_code

    @app.route("/api/statistical/report", methods=["GET"])
    def api_get_statistical_report():
        response, status_code = get_statistical_report()

        return jsonify(response), status_code