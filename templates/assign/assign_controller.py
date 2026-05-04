from flask import jsonify, request
from .assign_service import (
    list_assigns,
    find_assign,
    delete_assign,
    approve_assign,
    reject_assign,
    update_assign_status,
)


def register_assign_api_routes(app):

    @app.route("/api/assign", methods=["GET"])
    def assigns_api():
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
            )
        )

    @app.route("/api/assign/<string:assign_id>", methods=["GET", "DELETE"])
    def assign_detail_api(assign_id):
        if request.method == "GET":
            assign = find_assign(assign_id)

            if not assign:
                return jsonify({"message": "Assign not found"}), 404

            return jsonify(assign), 200

        if request.method == "DELETE":
            result = delete_assign(assign_id)

            if not result["deleted"]:
                return jsonify({"message": "Assign not found"}), 404

            return jsonify({
                "message": "Assign deleted successfully",
                "assign_id": assign_id,
                "deleted_count": result["deleted_count"],
            }), 200

    @app.route("/api/assign/<string:assign_id>/approve", methods=["PATCH", "POST"])
    def assign_approve_api(assign_id):
        result = approve_assign(assign_id)

        if not result["updated"]:
            return jsonify({"message": "Assign not found"}), 404

        return jsonify({
            "message": "Assign approved successfully",
            "assign_id": assign_id,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200

    @app.route("/api/assign/<string:assign_id>/reject", methods=["PATCH", "POST"])
    def assign_reject_api(assign_id):
        result = reject_assign(assign_id)

        if not result["updated"]:
            return jsonify({"message": "Assign not found"}), 404

        return jsonify({
            "message": "Assign rejected successfully",
            "assign_id": assign_id,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200

    @app.route("/api/assign/<string:assign_id>/status", methods=["PATCH"])
    def assign_update_status_api(assign_id):
        body = request.get_json(silent=True) or {}
        status = body.get("status")

        if not status:
            return jsonify({"message": "Missing status"}), 400

        result = update_assign_status(assign_id, status)

        if not result["updated"]:
            return jsonify({"message": "Assign not found"}), 404

        return jsonify({
            "message": "Assign status updated successfully",
            "assign_id": assign_id,
            "status": status,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200