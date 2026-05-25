from flask import jsonify, request

from .asset_service import (
    list_assets,
    find_asset,
    delete_asset,
    add_asset,
    add_many_assets,
    update_asset,
    get_asset_type_options,
    assign_asset,
    unassign_asset,
)

from templates.permission.permission_service import (
    permission_required,
    get_current_user_from_request,
)

from templates.activity.activity_service import create_activity_log


def get_asset_name(asset):
    if not asset:
        return "tài sản"

    return (
        asset.get("asset_name")
        or asset.get("asset")
        or asset.get("asset_code")
        or "tài sản"
    )


def get_asset_receiver(asset):
    if not asset:
        return ""

    return (
        asset.get("receiver")
        or asset.get("user")
        or asset.get("employee_code")
        or ""
    )


def build_asset_metadata(asset):
    if not asset:
        return {}

    return {
        "asset_id": asset.get("id"),
        "asset_code": asset.get("asset_code"),
        "asset_name": asset.get("asset_name") or asset.get("asset"),
        "type": asset.get("type"),
        "status": asset.get("status"),
        "receiver": asset.get("receiver") or asset.get("user"),
        "employee_code": asset.get("employee_code"),
        "department": asset.get("department"),
        "location": asset.get("location"),
    }


def log_asset_activity(
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
            module="assets",
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


def register_assets_api_routes(app):
    # phân trang và lọc tài sản
    # ADMIN / QUAN_LY: thấy toàn bộ tài sản
    # NHAN_VIEN: chỉ thấy tài sản đã cấp phát cho chính nhân viên đó
    @app.route("/api/assets", methods=["GET"])
    @permission_required("assets", "view")
    def assets_api():
        current_user = get_current_user_from_request()

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        search = request.args.get("search", "", type=str).strip()
        asset_type = request.args.get("type", "Tất cả", type=str)
        department = request.args.get("department", "Tất cả", type=str)
        status = request.args.get("status", "Tất cả", type=str)

        return jsonify(
            list_assets(
                page=page,
                per_page=per_page,
                search=search,
                asset_type=asset_type,
                department=department,
                status=status,
                current_user=current_user,
            )
        ), 200

    # lấy danh sách loại tài sản
    @app.route("/api/assets/types", methods=["GET"])
    @permission_required("assets", "view")
    def asset_types_api():
        current_user = get_current_user_from_request()
        return jsonify(get_asset_type_options(current_user=current_user)), 200

    # tạo tài sản mới đơn lẻ
    @app.route("/api/assets", methods=["POST"])
    @permission_required("assets", "create")
    def create_asset_api():
        current_user = get_current_user_from_request()
        data = request.get_json(silent=True)

        if not data or not isinstance(data, dict):
            return jsonify({
                "message": "Missing JSON body or body is not an object"
            }), 400

        data["status"] = data.get("status") or "available"
        data["user_id"] = ""
        data["employee_code"] = ""
        data["user"] = ""
        data["receiver"] = ""
        data["department"] = ""
        data["location"] = ""
        data["assigned_at"] = ""
        data["returned_at"] = ""

        result = add_asset(data)

        if not result["created"]:
            return jsonify({
                "message": result["message"],
                "errors": result.get("errors", {}),
            }), result.get("status_code", 400)

        item = result["item"]
        asset_name = get_asset_name(item)

        log_asset_activity(
            current_user=current_user,
            action=f"Tạo mới tài sản {asset_name}",
            method=request.method,
            status_code=201,
            target_id=item.get("id"),
            target_name=asset_name,
            metadata=build_asset_metadata(item),
        )

        return jsonify({
            "message": "Asset created successfully",
            "item": item,
        }), 201

    # tạo nhiều tài sản cùng lúc
    @app.route("/api/assets/bulk", methods=["POST"])
    @permission_required("assets", "create")
    def create_many_assets_api():
        current_user = get_current_user_from_request()
        items = request.get_json(silent=True)

        if not items or not isinstance(items, list):
            return jsonify({
                "message": "Body phải là một mảng JSON"
            }), 400

        normalized_items = []

        for item in items:
            if isinstance(item, dict):
                item["status"] = item.get("status") or "available"
                item["user_id"] = ""
                item["employee_code"] = ""
                item["user"] = ""
                item["receiver"] = ""
                item["department"] = ""
                item["location"] = ""
                item["assigned_at"] = ""
                item["returned_at"] = ""

            normalized_items.append(item)

        result = add_many_assets(normalized_items)

        if not result["created"]:
            return jsonify({
                "message": result["message"],
                "inserted_count": result.get("inserted_count", 0),
                "skipped_items": result.get("skipped_items", []),
            }), result.get("status_code", 400)

        log_asset_activity(
            current_user=current_user,
            action=f"Tạo mới {result['inserted_count']} tài sản",
            method=request.method,
            status_code=201,
            target_id=None,
            target_name=f"{result['inserted_count']} tài sản",
            metadata={
                "inserted_count": result["inserted_count"],
                "ids": result.get("ids", []),
                "skipped_items": result.get("skipped_items", []),
            },
        )

        return jsonify({
            "message": "Assets created successfully",
            "inserted_count": result["inserted_count"],
            "ids": result["ids"],
            "items": result["items"],
            "skipped_items": result.get("skipped_items", []),
        }), 201

    # chi tiết tài sản
    @app.route("/api/assets/<string:asset_id>", methods=["GET"])
    @permission_required("assets", "view")
    def get_asset_detail_api(asset_id):
        current_user = get_current_user_from_request()
        asset = find_asset(asset_id, current_user=current_user)

        if not asset:
            return jsonify({
                "message": "Asset not found"
            }), 404

        return jsonify(asset), 200

    # cập nhật tài sản
    @app.route("/api/assets/<string:asset_id>", methods=["PUT", "PATCH"])
    @permission_required("assets", "update")
    def update_asset_api(asset_id):
        current_user = get_current_user_from_request()
        data = request.get_json(silent=True)

        if not data or not isinstance(data, dict):
            return jsonify({
                "message": "Missing JSON body or body is not an object"
            }), 400

        old_asset = find_asset(asset_id, current_user=current_user)

        result = update_asset(
            asset_id=asset_id,
            data=data,
            current_user=current_user,
        )

        if not result["success"]:
            return jsonify({
                "message": result["message"],
                "errors": result.get("errors", {}),
            }), result.get("status_code", 400)

        item = result["item"]
        asset_name = get_asset_name(item)

        log_asset_activity(
            current_user=current_user,
            action=f"Cập nhật tài sản {asset_name}",
            method=request.method,
            status_code=200,
            target_id=item.get("id"),
            target_name=asset_name,
            metadata={
                "before": build_asset_metadata(old_asset),
                "after": build_asset_metadata(item),
                "changed_fields": list(data.keys()),
            },
        )

        return jsonify({
            "message": result["message"],
            "item": item,
        }), 200

    # xóa tài sản
    @app.route("/api/assets/<string:asset_id>", methods=["DELETE"])
    @permission_required("assets", "delete")
    def delete_asset_api(asset_id):
        current_user = get_current_user_from_request()

        old_asset = find_asset(asset_id, current_user=current_user)

        if not old_asset:
            return jsonify({
                "message": "Asset not found"
            }), 404

        result = delete_asset(asset_id)

        if not result["deleted"]:
            return jsonify({
                "message": "Asset not found"
            }), 404

        asset_name = get_asset_name(old_asset)

        log_asset_activity(
            current_user=current_user,
            action=f"Xóa tài sản {asset_name}",
            method=request.method,
            status_code=200,
            target_id=old_asset.get("id") or asset_id,
            target_name=asset_name,
            metadata=build_asset_metadata(old_asset),
        )

        return jsonify({
            "message": "Asset deleted successfully",
            "asset_id": asset_id,
            "deleted_count": result["deleted_count"],
        }), 200

    # gán tài sản cho người dùng
    @app.route("/api/assets/<string:asset_id>/assign", methods=["PATCH"])
    @permission_required("assets", "update")
    def assign_asset_api(asset_id):
        current_user = get_current_user_from_request()
        data = request.get_json(silent=True)

        if not data or not isinstance(data, dict):
            return jsonify({
                "message": "Body phải là object JSON. Cần gửi user_id, employee_code hoặc email."
            }), 400

        result = assign_asset(asset_id, data)

        if not result["success"]:
            return jsonify({
                "message": result["message"]
            }), result.get("status_code", 400)

        item = result["item"]
        asset_name = get_asset_name(item)
        receiver = get_asset_receiver(item)

        log_asset_activity(
            current_user=current_user,
            action=f"Cấp phát {asset_name} cho {receiver}",
            method=request.method,
            status_code=200,
            target_id=item.get("id"),
            target_name=asset_name,
            metadata=build_asset_metadata(item),
        )

        return jsonify({
            "message": result["message"],
            "item": item,
        }), 200

    # hủy gán tài sản
    @app.route("/api/assets/<string:asset_id>/unassign", methods=["PATCH"])
    @permission_required("assets", "update")
    def unassign_asset_api(asset_id):
        current_user = get_current_user_from_request()

        old_asset = find_asset(asset_id, current_user=current_user)
        old_receiver = get_asset_receiver(old_asset)

        result = unassign_asset(asset_id)

        if not result["success"]:
            return jsonify({
                "message": result["message"]
            }), result.get("status_code", 400)

        item = result["item"]
        asset_name = get_asset_name(item)

        if old_receiver:
            action = f"Thu hồi {asset_name} từ {old_receiver}"
        else:
            action = f"Thu hồi {asset_name}"

        log_asset_activity(
            current_user=current_user,
            action=action,
            method=request.method,
            status_code=200,
            target_id=item.get("id"),
            target_name=asset_name,
            metadata={
                "before": build_asset_metadata(old_asset),
                "after": build_asset_metadata(item),
            },
        )

        return jsonify({
            "message": result["message"],
            "item": item,
        }), 200