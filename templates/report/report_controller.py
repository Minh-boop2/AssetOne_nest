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

from templates.activity.activity_service import create_activity_log


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


def _get_current_user_id(current_user):
    if not current_user:
        return ""

    return str(current_user.get("_id") or current_user.get("id") or "")


def _get_report_title(report):
    if not report:
        return "báo cáo"

    return (
        report.get("report_name")
        or report.get("title")
        or report.get("name")
        or report.get("report_code")
        or "báo cáo"
    )


def _get_report_code(report):
    if not report:
        return ""

    return report.get("report_code") or ""


def _get_report_type(report):
    if not report:
        return ""

    return report.get("report_type") or report.get("type") or ""


def _get_report_status(report):
    if not report:
        return ""

    return report.get("status") or ""


def _get_report_asset_name(report):
    if not report:
        return ""

    return (
        report.get("asset_name")
        or report.get("asset")
        or report.get("asset_code")
        or ""
    )


def _get_report_id(report):
    if not report:
        return ""

    return report.get("id") or report.get("_id") or report.get("report_code") or ""


def _get_response_report_data(response):
    if not isinstance(response, dict):
        return {}

    data = response.get("data")

    if isinstance(data, dict):
        return data

    return {}


def _build_report_metadata(report):
    if not report:
        return {}

    return {
        "report_id": _get_report_id(report),
        "report_code": report.get("report_code"),
        "report_name": report.get("report_name"),
        "report_type": report.get("report_type"),
        "status": report.get("status"),

        "reporter_user_id": report.get("reporter_user_id"),
        "reporter_employee_code": report.get("reporter_employee_code"),
        "reporter_email": report.get("reporter_email"),
        "reporter": report.get("reporter"),
        "reporter_role": report.get("reporter_role"),

        "asset_id": report.get("asset_id"),
        "asset_code": report.get("asset_code"),
        "asset_name": report.get("asset_name"),
        "asset_type": report.get("asset_type"),
        "asset_status": report.get("asset_status"),

        "department": report.get("department"),
        "location": report.get("location"),
        "description": report.get("description"),

        "approved_by": report.get("approved_by"),
        "approved_at": report.get("approved_at"),
        "approval_note": report.get("approval_note"),

        "cancelled_by": report.get("cancelled_by"),
        "cancelled_at": report.get("cancelled_at"),
        "cancel_reason": report.get("cancel_reason"),

        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
    }


def _log_report_activity(
    current_user,
    action,
    method,
    status_code,
    target_id=None,
    target_name=None,
    metadata=None,
):
    try:
        current_user_id = _get_current_user_id(current_user)

        if not current_user_id:
            return

        create_activity_log(
            user_id=current_user_id,
            action=action,
            module="reports",
            method=method,
            path=request.path,
            status_code=status_code,
            target_id=target_id,
            target_name=target_name,
            metadata=metadata or {},
        )

    except Exception:
        # Không để lỗi ghi log làm hỏng API chính
        pass


def _get_report_before_action(report_id, current_user):
    try:
        response, status_code = get_report_by_id(
            report_id=report_id,
            current_user=current_user,
        )

        if status_code != 200:
            return {}

        return _get_response_report_data(response)

    except Exception:
        return {}


def _build_create_report_action(report):
    report_type = _get_report_type(report)
    asset_name = _get_report_asset_name(report)
    report_title = _get_report_title(report)

    if report_type and asset_name:
        return f"Gửi báo cáo {report_type} cho {asset_name}"

    if report_type:
        return f"Gửi báo cáo {report_type}"

    return f"Tạo báo cáo {report_title}"


def _build_update_report_action(report):
    report_title = _get_report_title(report)
    return f"Cập nhật báo cáo {report_title}"


def _build_approve_report_action(report):
    report_type = _get_report_type(report)
    asset_name = _get_report_asset_name(report)
    report_title = _get_report_title(report)

    if report_type and asset_name:
        return f"Duyệt báo cáo {report_type} cho {asset_name}"

    if report_type:
        return f"Duyệt báo cáo {report_type}"

    return f"Duyệt báo cáo {report_title}"


def _build_cancel_report_action(report):
    report_title = _get_report_title(report)
    return f"Hủy báo cáo {report_title}"


def _build_delete_report_action(report):
    report_title = _get_report_title(report)
    return f"Xóa báo cáo {report_title}"


def _build_delete_report_file_action(report, file_id):
    report_title = _get_report_title(report)
    return f"Xóa file trong báo cáo {report_title}"


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

        if status_code == 201 and response.get("success"):
            report = _get_response_report_data(response)
            report_title = _get_report_title(report)

            _log_report_activity(
                current_user=current_user,
                action=_build_create_report_action(report),
                method=request.method,
                status_code=status_code,
                target_id=_get_report_id(report),
                target_name=report_title,
                metadata={
                    "report": _build_report_metadata(report),
                    "uploaded_file_count": len(uploaded_files),
                },
            )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>", methods=["PUT", "PATCH"])
    @permission_required("reports", "update")
    def api_update_report(report_id):
        current_user = get_current_user_from_request()
        data = _get_request_data()
        uploaded_files = _get_uploaded_files()

        old_report = _get_report_before_action(
            report_id=report_id,
            current_user=current_user,
        )

        response, status_code = update_report(
            report_id=report_id,
            data=data,
            uploaded_files=uploaded_files,
            current_user=current_user,
        )

        if status_code == 200 and response.get("success"):
            updated_report = _get_response_report_data(response)
            report_title = _get_report_title(updated_report)

            _log_report_activity(
                current_user=current_user,
                action=_build_update_report_action(updated_report),
                method=request.method,
                status_code=status_code,
                target_id=_get_report_id(updated_report) or report_id,
                target_name=report_title,
                metadata={
                    "before": _build_report_metadata(old_report),
                    "after": _build_report_metadata(updated_report),
                    "changed_fields": list(data.keys()),
                    "uploaded_file_count": len(uploaded_files),
                },
            )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>/approve", methods=["POST", "PATCH"])
    @permission_required("reports", "update")
    def api_approve_report(report_id):
        current_user = get_current_user_from_request()
        data = _get_request_data()

        old_report = _get_report_before_action(
            report_id=report_id,
            current_user=current_user,
        )

        response, status_code = approve_report(
            report_id=report_id,
            data=data,
            current_user=current_user,
        )

        if status_code == 200 and response.get("success"):
            approved_report = _get_response_report_data(response)
            report_title = _get_report_title(approved_report)

            _log_report_activity(
                current_user=current_user,
                action=_build_approve_report_action(approved_report),
                method=request.method,
                status_code=status_code,
                target_id=_get_report_id(approved_report) or report_id,
                target_name=report_title,
                metadata={
                    "before": _build_report_metadata(old_report),
                    "after": _build_report_metadata(approved_report),
                    "approval_note": data.get("approval_note") or data.get("note") or "",
                    "asset_action_result": response.get("asset_action_result"),
                },
            )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>/cancel", methods=["POST", "PATCH"])
    @permission_required("reports", "update")
    def api_cancel_report(report_id):
        current_user = get_current_user_from_request()
        data = _get_request_data()

        old_report = _get_report_before_action(
            report_id=report_id,
            current_user=current_user,
        )

        response, status_code = cancel_report(
            report_id=report_id,
            data=data,
            current_user=current_user,
        )

        if status_code == 200 and response.get("success"):
            cancelled_report = _get_response_report_data(response)
            report_title = _get_report_title(cancelled_report)

            _log_report_activity(
                current_user=current_user,
                action=_build_cancel_report_action(cancelled_report),
                method=request.method,
                status_code=status_code,
                target_id=_get_report_id(cancelled_report) or report_id,
                target_name=report_title,
                metadata={
                    "before": _build_report_metadata(old_report),
                    "after": _build_report_metadata(cancelled_report),
                    "cancel_reason": data.get("cancel_reason") or data.get("reason") or "",
                },
            )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>", methods=["DELETE"])
    @permission_required("reports", "delete")
    def api_delete_report(report_id):
        current_user = get_current_user_from_request()

        response, status_code = delete_report(report_id)

        if status_code == 200 and response.get("success"):
            deleted_report = _get_response_report_data(response)
            report_title = _get_report_title(deleted_report)

            _log_report_activity(
                current_user=current_user,
                action=_build_delete_report_action(deleted_report),
                method=request.method,
                status_code=status_code,
                target_id=_get_report_id(deleted_report) or report_id,
                target_name=report_title,
                metadata=_build_report_metadata(deleted_report),
            )

        return jsonify(response), status_code

    @app.route("/api/reports/<report_id>/files/<file_id>", methods=["DELETE"])
    @permission_required("reports", "update")
    def api_delete_report_file(report_id, file_id):
        current_user = get_current_user_from_request()

        old_report = _get_report_before_action(
            report_id=report_id,
            current_user=current_user,
        )

        response, status_code = delete_report_file(
            report_id=report_id,
            file_id=file_id,
            current_user=current_user,
        )

        if status_code == 200 and response.get("success"):
            deleted_file = response.get("data") or {}
            report_title = _get_report_title(old_report)

            _log_report_activity(
                current_user=current_user,
                action=_build_delete_report_file_action(old_report, file_id),
                method=request.method,
                status_code=status_code,
                target_id=_get_report_id(old_report) or report_id,
                target_name=report_title,
                metadata={
                    "report": _build_report_metadata(old_report),
                    "deleted_file": deleted_file,
                    "file_id": file_id,
                },
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