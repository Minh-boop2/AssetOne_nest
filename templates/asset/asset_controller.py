from flask import jsonify, request

from .asset_service import (
    list_assets,
    find_asset,
    delete_asset,
    add_asset,
    add_many_assets,
    get_asset_type_options,
)




def register_assets_api_routes(app):
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
    
    @app.route("/api/assets/types", methods=["GET"])
    def asset_types_api():
        return jsonify(get_asset_type_options()), 200
    
    @app.route("/api/assets", methods=["POST"])
    def create_asset_api():
        data = request.get_json(silent=True)

        if not data or not isinstance(data, dict):
            return jsonify({
                "message": "Missing JSON body or body is not an object"
            }), 400

        # Mặc định khi tạo tài sản mới
        # Trạng thái: Chưa sử dụng
        # Chưa có người nhận, phòng ban, vị trí
        data["status"] = data.get("status") or "available"
        data["user"] = data.get("user") or ""
        data["receiver"] = data.get("receiver") or ""
        data["department"] = data.get("department") or ""
        data["location"] = data.get("location") or ""

        result = add_asset(data)

        if not result["created"]:
            return jsonify({
                "message": result["message"]
            }), result.get("status_code", 400)

        return jsonify({
            "message": "Asset created successfully",
            "item": result["item"],
        }), 201

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
                item["status"] = item.get("status") or "available"
                item["user"] = item.get("user") or ""
                item["receiver"] = item.get("receiver") or ""
                item["department"] = item.get("department") or ""
                item["location"] = item.get("location") or ""

            normalized_items.append(item)

        result = add_many_assets(normalized_items)

        if not result["created"]:
            return jsonify({
                "message": result["message"],
                "inserted_count": result.get("inserted_count", 0),
            }), result.get("status_code", 400)

        return jsonify({
            "message": "Assets created successfully",
            "inserted_count": result["inserted_count"],
            "ids": result["ids"],
            "items": result["items"],
        }), 201

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