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

        return jsonify({
            "message": "Asset created successfully",
            "item": result["item"],
        }), 201

    # tạo nhiều tài sản cùng lúc
    @app.route("/api/assets/bulk", methods=["POST"])
    @permission_required("assets", "create")
    def create_many_assets_api():
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

        return jsonify({
            "message": result["message"],
            "item": result["item"],
        }), 200

    # xóa tài sản
    @app.route("/api/assets/<string:asset_id>", methods=["DELETE"])
    @permission_required("assets", "delete")
    def delete_asset_api(asset_id):
        result = delete_asset(asset_id)

        if not result["deleted"]:
            return jsonify({
                "message": "Asset not found"
            }), 404

        return jsonify({
            "message": "Asset deleted successfully",
            "asset_id": asset_id,
            "deleted_count": result["deleted_count"],
        }), 200

    # gán tài sản cho người dùng
    @app.route("/api/assets/<string:asset_id>/assign", methods=["PATCH"])
    @permission_required("assets", "update")
    def assign_asset_api(asset_id):
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

        return jsonify({
            "message": result["message"],
            "item": result["item"],
        }), 200

    # hủy gán tài sản
    @app.route("/api/assets/<string:asset_id>/unassign", methods=["PATCH"])
    @permission_required("assets", "update")
    def unassign_asset_api(asset_id):
        result = unassign_asset(asset_id)

        if not result["success"]:
            return jsonify({
                "message": result["message"]
            }), result.get("status_code", 400)

        return jsonify({
            "message": result["message"],
            "item": result["item"],
        }), 200