from mongo import assets_collection
from bson import ObjectId
import math
import re

SEARCH_FIELDS = [
    "asset_name",
    "asset",
    "asset_code",
    "user",
    "receiver",
    "department",
    "location",
    "status",
    "type",
    "warranty"
]


def normalize_asset(item):
    row = dict(item)

    row["id"] = str(row.get("_id", ""))
    row["asset"] = row.get("asset") or row.get("asset_name") or ""
    row["asset_name"] = row.get("asset_name") or row.get("asset") or ""
    row["user"] = row.get("user") or row.get("receiver") or ""
    row["receiver"] = row.get("receiver") or row.get("user") or ""

    row.pop("_id", None)
    return row


def build_asset_query(search="", asset_type="Tất cả", department="Tất cả", status="Tất cả"):
    query = {}

    if search:
        safe_search = re.escape(search.strip())
        query["$or"] = [
            {field: {"$regex": safe_search, "$options": "i"}}
            for field in SEARCH_FIELDS
        ]

    if asset_type != "Tất cả":
        query["type"] = asset_type

    if department != "Tất cả":
        query["department"] = department

    if status != "Tất cả":
        if status == "using":
            query["status"] = {"$in": ["using", "Hoàn thành", "Đang sử dụng"]}
        elif status == "available":
            query["status"] = {"$in": ["available", "Chưa sử dụng"]}
        elif status == "maintenance":
            query["status"] = {"$in": ["maintenance", "Bảo trì"]}
        else:
            query["status"] = status

    return query


def get_asset_filter_counts():
    return {
        "type": {
            "all": assets_collection.count_documents({}),
            "laptop": assets_collection.count_documents({"type": "laptop"}),
            "pc": assets_collection.count_documents({"type": "pc"}),
            "printer": assets_collection.count_documents({"type": "printer"}),
        },
        "status": {
            "all": assets_collection.count_documents({}),
            "using": assets_collection.count_documents({
                "status": {"$in": ["using", "Hoàn thành", "Đang sử dụng"]}
            }),
            "available": assets_collection.count_documents({
                "status": {"$in": ["available", "Chưa sử dụng"]}
            }),
            "maintenance": assets_collection.count_documents({
                "status": {"$in": ["maintenance", "Bảo trì"]}
            }),
            "pending": assets_collection.count_documents({
                "status": "Chờ duyệt"
            }),
        }
    }


def get_assets_paginated(page=1, per_page=10, search="", asset_type="Tất cả", department="Tất cả", status="Tất cả"):
    page = max(1, int(page))
    per_page = max(1, int(per_page))

    query = build_asset_query(search, asset_type, department, status)

    total_items = assets_collection.count_documents(query)
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

    if page > total_pages:
        page = total_pages

    skip = (page - 1) * per_page

    cursor = assets_collection.find(query).skip(skip).limit(per_page)
    items = [normalize_asset(item) for item in cursor]

    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        },
        "filter_counts": get_asset_filter_counts()
    }


def get_asset_by_id(asset_id):
    try:
        query = {"_id": ObjectId(asset_id)}
    except Exception:
        query = {"asset_code": asset_id}

    item = assets_collection.find_one(query)
    if not item:
        return None

    return normalize_asset(item)


def delete_asset_by_id(asset_id):
    try:
        query = {"_id": ObjectId(asset_id)}
    except Exception:
        query = {"asset_code": asset_id}

    result = assets_collection.delete_one(query)

    return {
        "deleted": result.deleted_count > 0,
        "deleted_count": result.deleted_count
    }