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

from templates.activity.activity_service import create_activity_log


def get_assign_asset_name(assign):
    if not assign:
        return "tài sản"

    return (
        assign.get("asset_name")
        or assign.get("asset")
        or assign.get("asset_code")
        or "tài sản"
    )


def get_assign_receiver(assign):
    if not assign:
        return ""

    return (
        assign.get("receiver")
        or assign.get("user")
        or assign.get("employee_code")
        or ""
    )


def build_assign_metadata(assign):
    if not assign:
        return {}

    return {
        "assign_id": assign.get("id") or assign.get("mongo_id"),
        "mongo_id": assign.get("mongo_id"),
        "asset_code": assign.get("asset_code"),
        "asset_name": assign.get("asset_name") or assign.get("asset"),
        "type": assign.get("type") or assign.get("category"),
        "status": assign.get("status"),
        "asset_status": assign.get("asset_status"),
        "user_id": assign.get("user_id"),
        "employee_code": assign.get("employee_code"),
        "receiver": assign.get("receiver") or assign.get("user"),
        "department": assign.get("department"),
        "location": assign.get("location"),
        "date": assign.get("date"),
        "return_date": assign.get("return_date"),
    }


def log_assign_activity(
    current_user,
    action,
    method,
    status_code,
    target_id=None,
    target_name=None,
    metadata=None,
):
    try:
        if not current_user:
            return

        user_id = current_user.get("_id")

        if not user_id:
            return

        create_activity_log(
            user_id=str(user_id),
            action=action,
            module="assign",
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


def build_approve_action(assign):
    asset_name = get_assign_asset_name(assign)
    receiver = get_assign_receiver(assign)

    if receiver:
        return f"Duyệt cấp phát {asset_name} cho {receiver}"

    return f"Duyệt cấp phát {asset_name}"


def build_reject_action(assign):
    asset_name = get_assign_asset_name(assign)
    receiver = get_assign_receiver(assign)

    if receiver:
        return f"Từ chối / hủy cấp phát {asset_name} của {receiver}"

    return f"Từ chối / hủy cấp phát {asset_name}"


def build_update_status_action(assign, status):
    asset_name = get_assign_asset_name(assign)
    receiver = get_assign_receiver(assign)

    if status in ["Chưa dùng", "Chưa sử dụng"]:
        if receiver:
            return f"Thu hồi {asset_name} từ {receiver}"

        return f"Thu hồi {asset_name}"

    if status == "Đang sử dụng":
        if receiver:
            return f"Cập nhật cấp phát {asset_name} cho {receiver}"

        return f"Cập nhật cấp phát {asset_name}"

    return f"Cập nhật trạng thái cấp phát {asset_name} thành {status}"


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

        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        if not old_assign:
            return jsonify({
                "message": "Assign not found"
            }), 404

        result = delete_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["deleted"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        asset_name = get_assign_asset_name(old_assign)
        receiver = get_assign_receiver(old_assign)

        if receiver:
            action = f"Xóa bản ghi cấp phát {asset_name} của {receiver}"
        else:
            action = f"Xóa bản ghi cấp phát {asset_name}"

        log_assign_activity(
            current_user=current_user,
            action=action,
            method=request.method,
            status_code=200,
            target_id=old_assign.get("id") or assign_id,
            target_name=asset_name,
            metadata=build_assign_metadata(old_assign),
        )

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

        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        result = approve_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        item = result.get("item") or old_assign
        asset_name = get_assign_asset_name(item)

        log_assign_activity(
            current_user=current_user,
            action=build_approve_action(item),
            method=request.method,
            status_code=200,
            target_id=item.get("id") or assign_id,
            target_name=asset_name,
            metadata={
                "before": build_assign_metadata(old_assign),
                "after": build_assign_metadata(item),
            },
        )

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

        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        result = reject_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        item = result.get("item") or old_assign
        asset_name = get_assign_asset_name(item)

        log_assign_activity(
            current_user=current_user,
            action=build_reject_action(old_assign or item),
            method=request.method,
            status_code=200,
            target_id=(old_assign or item).get("id") or assign_id,
            target_name=asset_name,
            metadata={
                "before": build_assign_metadata(old_assign),
                "after": build_assign_metadata(item),
            },
        )

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

        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        result = update_assign_status(
            assign_id,
            status,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        item = result.get("item") or old_assign
        asset_name = get_assign_asset_name(item or old_assign)

        log_assign_activity(
            current_user=current_user,
            action=build_update_status_action(old_assign or item, status),
            method=request.method,
            status_code=200,
            target_id=(old_assign or item).get("id") or assign_id,
            target_name=asset_name,
            metadata={
                "status": status,
                "before": build_assign_metadata(old_assign),
                "after": build_assign_metadata(item),
            },
        )

        return jsonify({
            "message": "Assign status updated successfully",
            "assign_id": assign_id,
            "status": status,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200