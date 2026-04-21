from flask import jsonify, request
from .asset_service import list_assets, find_asset


def register_assets_api_routes(app):
    @app.route("/api/assets")
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
                status=status
            )
        )

    @app.route("/api/assets/<string:asset_id>")
    def asset_detail_api(asset_id):
        asset = find_asset(asset_id)
        if not asset:
            return jsonify({"message": "Asset not found"}), 404
        return jsonify(asset)