from flask import request, jsonify, send_from_directory

from templates.report.report_model import UPLOAD_FOLDER

from templates.report.report_service import (
    get_report_options,
    get_my_report_asset_options,
    get_reports,
    get_report_by_id,
    create_report,
    update_report,
    approve_report,
    cancel_report,
    delete_report,
    delete_report_file,
    get_report_overview,
)

from templates.permission.permission_service import (
    permission_required,
    get_current_user_from_request,
)


def _get_request_data():
    if request.form:
        return request.form.to_dict(flat=True)

    return request.get_json(silent=True) or {}


def _get_uploaded_files():
    uploaded_files = []

    for field_name in request.files:
        uploaded_files.extend(request.files.getlist(field_name))

    return [
        uploaded_file
        for uploaded_file in uploaded_files
        if uploaded_file and uploaded_file.filename
    ]


def register_reports_api_routes(app):

    @app.route("/api/reports/options", methods=["GET"])
    @permission_required("reports", "view")
    def api_get_report_options():
        current_user = get_current_user_from_request()
        response, status_code = get_report_options(current_user=current_user)
        return jsonify(response), status_code

    @app.route("/api/reports/assets/options", methods=["GET"])
    @permission_required("reports", "view")
    def api_get_my_report_asset_options():
        current_user = get_current_user_from_request()
        response, status_code = get_my_report_asset_options(current_user=current_user)
        return jsonify(response), status_code

    @app.route("/api/reports/overview", methods=["GET"])
    @permission_required("reports", "view")
    def api_get_report_overview():
        current_user = get_current_user_from_request()
        response, status_code = get_report_overview(current_user=current_user)
        return jsonify(response), status_code

    @app.route("/api/reports", methods=["GET"])
    @permission_required("reports", "view")
    def api_get_reports():
        current_user = get_current_user_from_request()
        filters = request.args.to_dict()

        response, status_code = get_reports(
            filters=filters,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>", methods=["GET"])
    @permission_required("reports", "view")
    def api_get_report_by_id(report_id):
        current_user = get_current_user_from_request()

        response, status_code = get_report_by_id(
            report_id=report_id,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/reports", methods=["POST"])
    @permission_required("reports", "create")
    def api_create_report():
        current_user = get_current_user_from_request()
        data = _get_request_data()
        uploaded_files = _get_uploaded_files()

        response, status_code = create_report(
            data=data,
            uploaded_files=uploaded_files,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>", methods=["PUT", "PATCH"])
    @permission_required("reports", "update")
    def api_update_report(report_id):
        current_user = get_current_user_from_request()
        data = _get_request_data()
        uploaded_files = _get_uploaded_files()

        response, status_code = update_report(
            report_id=report_id,
            data=data,
            uploaded_files=uploaded_files,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>/approve", methods=["POST", "PATCH"])
    @permission_required("reports", "update")
    def api_approve_report(report_id):
        current_user = get_current_user_from_request()
        data = _get_request_data()

        response, status_code = approve_report(
            report_id=report_id,
            data=data,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>/cancel", methods=["POST", "PATCH"])
    @permission_required("reports", "update")
    def api_cancel_report(report_id):
        current_user = get_current_user_from_request()
        data = _get_request_data()

        response, status_code = cancel_report(
            report_id=report_id,
            data=data,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>", methods=["DELETE"])
    @permission_required("reports", "delete")
    def api_delete_report(report_id):
        response, status_code = delete_report(report_id)
        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>/files/<file_id>", methods=["DELETE"])
    @permission_required("reports", "update")
    def api_delete_report_file(report_id, file_id):
        current_user = get_current_user_from_request()

        response, status_code = delete_report_file(
            report_id=report_id,
            file_id=file_id,
            current_user=current_user,
        )

        return jsonify(response), status_code

    @app.route("/api/reports/files/<path:filename>", methods=["GET"])
    @permission_required("reports", "view")
    def api_get_report_file(filename):
        as_attachment = request.args.get("download") == "1"

        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=as_attachment
        )