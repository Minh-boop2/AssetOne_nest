from flask import jsonify, request

from .asset_service import (
    list_assets,
    find_asset,
    delete_asset,
    add_asset,
    add_many_assets,
    get_asset_type_options,
    assign_asset,
    unassign_asset,
)


def register_assets_api_routes(app):
    # phân trang và lọc tài sản
    @app.route("/api/assets", methods=["GET"])
    def assets_api():
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
            )
        ), 200

    # lấy danh sách loại tài sản
    @app.route("/api/assets/types", methods=["GET"])
    def asset_types_api():
        return jsonify(get_asset_type_options()), 200

    # tạo tài sản mới đơn lẻ
    @app.route("/api/assets", methods=["POST"])
    def create_asset_api():
        data = request.get_json(silent=True)

        if not data or not isinstance(data, dict):
            return jsonify({
                "message": "Missing JSON body or body is not an object"
            }), 400

        # Tạo tài sản mới:
        # - Chưa cấp phát cho ai
        # - Chưa có phòng ban / vị trí
        # - Trạng thái mặc định là Chưa sử dụng
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
    def create_many_assets_api():
        items = request.get_json(silent=True)

        if not items or not isinstance(items, list):
            return jsonify({
                "message": "Body phải là một mảng JSON"
            }), 400

        normalized_items = []

        for item in items:
            if isinstance(item, dict):
                # Bulk tạo tài sản mới cũng không gán người dùng/phòng ban/vị trí.
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

    # chi tiết tài sản hoặc xóa tài sản
    @app.route("/api/assets/<string:asset_id>", methods=["GET", "DELETE"])
    def asset_detail_api(asset_id):
        if request.method == "GET":
            asset = find_asset(asset_id)

            if not asset:
                return jsonify({
                    "message": "Asset not found"
                }), 404

            return jsonify(asset), 200

        if request.method == "DELETE":
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