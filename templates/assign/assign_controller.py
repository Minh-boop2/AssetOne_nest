from flask import jsonify, request

from .assign_service import (
    list_assigns,
    find_assign,
    delete_assign,
    approve_assign,
    reject_assign,
    update_assign_status,
)

from templates.permission.permission_service import (
    permission_required,
    get_current_user_from_request,
)


def register_assign_api_routes(app):

    # Lấy danh sách cấp phát tài sản
    # ADMIN / QUAN_LY: thấy toàn bộ
    # NHAN_VIEN: chỉ thấy tài sản/cấp phát của chính mình nếu được cấp quyền assign/view
    @app.route("/api/assign", methods=["GET"])
    @permission_required("assign", "view")
    def assigns_api():
        current_user = get_current_user_from_request()

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        search = request.args.get("search", "", type=str).strip()

        asset_type = request.args.get("type", "Tất cả", type=str)
        department = request.args.get("department", "Tất cả", type=str)
        status = request.args.get("status", "Tất cả", type=str)
        location = request.args.get("location", "Tất cả", type=str)

        return jsonify(
            list_assigns(
                page=page,
                per_page=per_page,
                search=search,
                asset_type=asset_type,
                department=department,
                status=status,
                location=location,
                current_user=current_user,
            )
        ), 200

    # Xem chi tiết một bản ghi cấp phát
    @app.route("/api/assign/<string:assign_id>", methods=["GET"])
    @permission_required("assign", "view")
    def get_assign_detail_api(assign_id):
        current_user = get_current_user_from_request()

        assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        if not assign:
            return jsonify({
                "message": "Assign not found"
            }), 404

        return jsonify(assign), 200

    # Xóa một bản ghi cấp phát
    # Lưu ý: assign đang là view từ assets, delete nghĩa là xóa asset.
    @app.route("/api/assign/<string:assign_id>", methods=["DELETE"])
    @permission_required("assign", "delete")
    def delete_assign_api(assign_id):
        current_user = get_current_user_from_request()

        result = delete_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["deleted"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        return jsonify({
            "message": "Assign deleted successfully",
            "assign_id": assign_id,
            "deleted_count": result["deleted_count"],
        }), 200

    # Duyệt yêu cầu cấp phát tài sản
    @app.route("/api/assign/<string:assign_id>/approve", methods=["PATCH", "POST"])
    @permission_required("assign", "approve")
    def assign_approve_api(assign_id):
        current_user = get_current_user_from_request()

        result = approve_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        return jsonify({
            "message": "Assign approved successfully",
            "assign_id": assign_id,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200

    # Từ chối / hủy cấp phát tài sản
    @app.route("/api/assign/<string:assign_id>/reject", methods=["PATCH", "POST"])
    @permission_required("assign", "approve")
    def assign_reject_api(assign_id):
        current_user = get_current_user_from_request()

        result = reject_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        return jsonify({
            "message": "Assign rejected successfully",
            "assign_id": assign_id,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200

    # Cập nhật trạng thái của bản ghi cấp phát
    @app.route("/api/assign/<string:assign_id>/status", methods=["PATCH"])
    @permission_required("assign", "update")
    def assign_update_status_api(assign_id):
        current_user = get_current_user_from_request()

        body = request.get_json(silent=True) or {}
        status = body.get("status")

        if not status:
            return jsonify({
                "message": "Missing status"
            }), 400

        result = update_assign_status(
            assign_id,
            status,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        return jsonify({
            "message": "Assign status updated successfully",
            "assign_id": assign_id,
            "status": status,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200