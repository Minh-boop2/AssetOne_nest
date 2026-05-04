from mongo import assets_collection
from bson import ObjectId
from datetime import datetime
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
    "category",
    "warranty",
    "spec",
    "notes",
]


TYPE_ALIASES = {
    "laptop": ["laptop", "Laptop", "LAPTOP"],
    "pc": ["pc", "PC", "Máy tính bàn", "May tinh ban", "Desktop", "desktop"],
    "printer": ["printer", "Printer", "Máy in", "May in"],
    "monitor": ["monitor", "Monitor", "Màn hình", "Man hinh"],
    "phone": ["phone", "Phone", "Điện thoại", "Dien thoai"],
    "projector": ["projector", "Projector", "Máy chiếu", "May chieu"],
}

STATUS_ALIASES = {
    "using": ["using", "Đang sử dụng", "Dang su dung", "Hoàn thành"],
    "available": ["available", "Chưa sử dụng", "Chua su dung"],
    "maintenance": ["maintenance", "Bảo trì", "Bao tri"],
    "broken": ["broken", "Hỏng", "Hong"],
    "pending": ["pending", "Chờ duyệt", "Cho duyet"],
}


def normalize_type_code(value):
    value = (value or "").strip()

    for code, aliases in TYPE_ALIASES.items():
        if value in aliases:
            return code

    return "other"


def normalize_status_code(value):
    value = (value or "").strip()

    for code, aliases in STATUS_ALIASES.items():
        if value in aliases:
            return code

    return "pending"


def aliases_for_type(asset_type):
    if not asset_type or asset_type == "Tất cả":
        return None

    if asset_type == "other":
        known_values = []
        for aliases in TYPE_ALIASES.values():
            known_values.extend(aliases)
        return {"$nin": known_values}

    code = normalize_type_code(asset_type)
    return TYPE_ALIASES.get(code, [asset_type])


def aliases_for_status(status):
    if not status or status == "Tất cả":
        return None

    code = normalize_status_code(status)
    return STATUS_ALIASES.get(code, [status])


def normalize_asset(item):
    row = dict(item)

    raw_type = row.get("type") or row.get("category") or ""
    raw_status = row.get("status") or ""

    type_code = normalize_type_code(raw_type)
    status_code = normalize_status_code(raw_status)

    row["id"] = str(row.get("_id", ""))
    row["asset"] = row.get("asset") or row.get("asset_name") or ""
    row["asset_name"] = row.get("asset_name") or row.get("asset") or ""
    row["user"] = row.get("user") or row.get("receiver") or ""
    row["receiver"] = row.get("receiver") or row.get("user") or ""

    row["type"] = type_code
    row["category"] = type_code
    row["status"] = status_code

    row["raw_type"] = raw_type
    row["raw_status"] = raw_status

    row["department"] = row.get("department") or ""
    row["location"] = row.get("location") or ""
    row["asset_code"] = row.get("asset_code") or ""
    row["warranty"] = row.get("warranty") or ""
    row["spec"] = row.get("spec") or row.get("notes") or ""
    row["notes"] = row.get("notes") or row.get("spec") or ""

    row.pop("_id", None)
    return row


def normalize_asset_payload(data):
    data = dict(data)

    asset_name = data.get("asset_name") or data.get("asset") or ""
    user = data.get("user") or data.get("receiver") or ""
    raw_type = data.get("type") or data.get("category") or ""
    raw_status = data.get("status") or "Chưa sử dụng"

    type_code = normalize_type_code(raw_type)
    status_code = normalize_status_code(raw_status)

    data["asset_name"] = asset_name
    data["asset"] = asset_name
    data["user"] = user
    data["receiver"] = user

    data["type"] = type_code
    data["category"] = type_code
    data["status"] = status_code

    data["asset_code"] = data.get("asset_code") or ""
    data["department"] = data.get("department") or ""
    data["location"] = data.get("location") or ""
    data["warranty"] = data.get("warranty") or ""
    data["spec"] = data.get("spec") or data.get("notes") or ""
    data["notes"] = data.get("notes") or data.get("spec") or ""

    now = datetime.utcnow()
    data["created_at"] = data.get("created_at") or now
    data["updated_at"] = now

    return data


def validate_asset_payload(data):
    errors = {}

    if not data.get("asset_code"):
        errors["asset_code"] = "Mã tài sản là bắt buộc"

    if not data.get("asset_name") and not data.get("asset"):
        errors["asset_name"] = "Tên tài sản là bắt buộc"

    if not data.get("type") and not data.get("category"):
        errors["type"] = "Loại tài sản là bắt buộc"

    if not data.get("status"):
        errors["status"] = "Trạng thái là bắt buộc"

    return errors


def build_asset_query(
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
):
    conditions = []

    if search:
        safe_search = re.escape(search.strip())
        conditions.append({
            "$or": [
                {field: {"$regex": safe_search, "$options": "i"}}
                for field in SEARCH_FIELDS
            ]
        })

    type_values = aliases_for_type(asset_type)

    if type_values:
        if isinstance(type_values, dict):
            conditions.append({
                "$or": [
                    {"type": type_values},
                    {"category": type_values},
                ]
            })
        else:
            conditions.append({
                "$or": [
                    {"type": {"$in": type_values}},
                    {"category": {"$in": type_values}},
                ]
            })

    if department and department != "Tất cả":
        conditions.append({"department": department})

    status_values = aliases_for_status(status)
    if status_values:
        conditions.append({"status": {"$in": status_values}})

    if not conditions:
        return {}

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}


def get_asset_filter_counts():
    type_counts = {
        "all": 0,
        "laptop": 0,
        "pc": 0,
        "printer": 0,
        "monitor": 0,
        "phone": 0,
        "projector": 0,
        "other": 0,
    }

    status_counts = {
        "all": 0,
        "using": 0,
        "available": 0,
        "maintenance": 0,
        "broken": 0,
        "pending": 0,
    }

    department_counts = {"all": 0}
    location_counts = {"all": 0}

    cursor = assets_collection.find({}, {
        "type": 1,
        "category": 1,
        "status": 1,
        "department": 1,
        "location": 1,
    })

    for item in cursor:
        type_code = normalize_type_code(item.get("type") or item.get("category"))
        status_code = normalize_status_code(item.get("status"))

        type_counts["all"] += 1
        status_counts["all"] += 1
        department_counts["all"] += 1
        location_counts["all"] += 1

        type_counts[type_code] = type_counts.get(type_code, 0) + 1
        status_counts[status_code] = status_counts.get(status_code, 0) + 1

        department = item.get("department")
        location = item.get("location")

        if department:
            department_counts[department] = department_counts.get(department, 0) + 1

        if location:
            location_counts[location] = location_counts.get(location, 0) + 1

    return {
        "type": type_counts,
        "status": status_counts,
        "department": department_counts,
        "location": location_counts,
    }


def get_assets_paginated(
    page=1,
    per_page=10,
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
):
    page = max(1, int(page))
    per_page = max(1, int(per_page))

    query = build_asset_query(
        search=search,
        asset_type=asset_type,
        department=department,
        status=status,
    )

    total_items = assets_collection.count_documents(query)
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

    if page > total_pages:
        page = total_pages

    skip = (page - 1) * per_page

    cursor = (
        assets_collection
        .find(query)
        .sort("_id", -1)
        .skip(skip)
        .limit(per_page)
    )

    items = [normalize_asset(item) for item in cursor]

    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages,
        },
        "filter_counts": get_asset_filter_counts(),
    }


def get_asset_by_id(asset_id):
    if ObjectId.is_valid(asset_id):
        query = {"_id": ObjectId(asset_id)}
    else:
        query = {"asset_code": asset_id}

    item = assets_collection.find_one(query)

    if not item:
        return None

    return normalize_asset(item)


def delete_asset_by_id(asset_id):
    if ObjectId.is_valid(asset_id):
        query = {"_id": ObjectId(asset_id)}
    else:
        query = {"asset_code": asset_id}

    result = assets_collection.delete_one(query)

    return {
        "deleted": result.deleted_count > 0,
        "deleted_count": result.deleted_count,
    }


def create_asset(data):
    data = normalize_asset_payload(data)
    errors = validate_asset_payload(data)

    if errors:
        return {
            "created": False,
            "message": "Dữ liệu không hợp lệ",
            "errors": errors,
            "status_code": 400,
        }

    existed = assets_collection.find_one({
        "asset_code": data["asset_code"]
    })

    if existed:
        return {
            "created": False,
            "message": "Mã tài sản đã tồn tại",
            "status_code": 409,
        }

    result = assets_collection.insert_one(data)
    created_item = assets_collection.find_one({"_id": result.inserted_id})

    return {
        "created": True,
        "item": normalize_asset(created_item),
    }


def create_many_assets(items):
    if not isinstance(items, list):
        return {
            "created": False,
            "message": "Body phải là một mảng JSON",
            "inserted_count": 0,
            "status_code": 400,
        }

    if len(items) == 0:
        return {
            "created": False,
            "message": "Danh sách rỗng",
            "inserted_count": 0,
            "status_code": 400,
        }

    normalized_items = []
    skipped_items = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            skipped_items.append({
                "index": index,
                "reason": "Item không phải object JSON",
            })
            continue

        normalized = normalize_asset_payload(item)
        errors = validate_asset_payload(normalized)

        if errors:
            skipped_items.append({
                "index": index,
                "asset_code": normalized.get("asset_code"),
                "reason": "Dữ liệu không hợp lệ",
                "errors": errors,
            })
            continue

        existed = assets_collection.find_one({
            "asset_code": normalized["asset_code"]
        })

        if existed:
            skipped_items.append({
                "index": index,
                "asset_code": normalized.get("asset_code"),
                "reason": "Mã tài sản đã tồn tại",
            })
            continue

        normalized_items.append(normalized)

    if not normalized_items:
        return {
            "created": False,
            "message": "Không có dữ liệu hợp lệ để thêm",
            "inserted_count": 0,
            "skipped_items": skipped_items,
            "status_code": 400,
        }

    result = assets_collection.insert_many(normalized_items)

    created_items = list(assets_collection.find({
        "_id": {"$in": result.inserted_ids}
    }))

    return {
        "created": True,
        "message": "Inserted successfully",
        "inserted_count": len(result.inserted_ids),
        "ids": [str(item_id) for item_id in result.inserted_ids],
        "items": [normalize_asset(item) for item in created_items],
        "skipped_items": skipped_items,
    }