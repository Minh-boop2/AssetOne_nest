from mongo import assets_collection
from bson import ObjectId
import math


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
        query["$or"] = [
            {"asset_name": {"$regex": search, "$options": "i"}},
            {"asset": {"$regex": search, "$options": "i"}},
            {"asset_code": {"$regex": search, "$options": "i"}}
        ]

    if asset_type != "Tất cả":
        query["type"] = asset_type

    if department != "Tất cả":
        query["department"] = department

    if status != "Tất cả":
        if status == "using":
            query["status"] = {"$in": ["using", "Hoàn thành", "Đang sử dụng"]}
        else:
            query["status"] = status

    return query


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
        }
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