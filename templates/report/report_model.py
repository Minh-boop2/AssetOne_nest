import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bson import ObjectId
from werkzeug.utils import secure_filename

from mongo import reports_collection


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

VN_TZ = timezone(timedelta(hours=7))


REPORT_TYPES = [
    "Báo hỏng",
    "Cần cấp mới",
    "Khác",
]

REPORT_STATUSES = [
    "Chờ xử lý",
    "Hoàn thành",
    "Đã hủy",
]

REPORTER_ROLES = [
    "Admin",
    "Manager",
    "Staff",
]

ALLOWED_FILE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "zip",
    "rar",
}


def current_vietnam_datetime():
    return datetime.now(VN_TZ)


def current_vietnam_time():
    return current_vietnam_datetime().strftime("%H:%M %d/%m/%Y")


def format_datetime_vietnam(value):
    if not value:
        return ""

    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M")


def is_valid_object_id(value):
    return ObjectId.is_valid(str(value))


def build_report_id_query(report_id):
    report_id = str(report_id)

    if ObjectId.is_valid(report_id):
        return {"_id": ObjectId(report_id)}

    return {"report_code": report_id}


def serialize_report(report):
    if not report:
        return None

    item = dict(report)

    item["id"] = str(item.get("_id", ""))
    item.pop("_id", None)

    item["created_at"] = format_datetime_vietnam(item.get("created_at"))
    item["updated_at"] = format_datetime_vietnam(item.get("updated_at"))
    item["approved_at"] = format_datetime_vietnam(item.get("approved_at"))
    item["cancelled_at"] = format_datetime_vietnam(item.get("cancelled_at"))

    item["report_code"] = item.get("report_code") or ""
    item["report_name"] = item.get("report_name") or ""
    item["report_type"] = item.get("report_type") or ""
    item["status"] = item.get("status") or "Chờ xử lý"

    item["reporter_user_id"] = item.get("reporter_user_id") or ""
    item["reporter_employee_code"] = item.get("reporter_employee_code") or ""
    item["reporter_email"] = item.get("reporter_email") or ""
    item["reporter"] = item.get("reporter") or ""
    item["reporter_role"] = item.get("reporter_role") or ""

    item["asset_id"] = item.get("asset_id") or ""
    item["asset_code"] = item.get("asset_code") or ""
    item["asset_name"] = item.get("asset_name") or "Chưa xác định"
    item["asset_type"] = item.get("asset_type") or ""
    item["asset_status"] = item.get("asset_status") or ""

    item["department"] = item.get("department") or ""
    item["location"] = item.get("location") or ""
    item["description"] = item.get("description") or ""
    item["time"] = item.get("time") or ""

    files = item.get("files", [])

    if not isinstance(files, list):
        files = []

    item["files"] = files

    return item


def count_reports(query=None):
    return reports_collection.count_documents(query or {})


def find_reports(query=None, skip=0, limit=10, sort_field="_id", sort_order=-1):
    return list(
        reports_collection
        .find(query or {})
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
    )


def find_report_by_query(query):
    return reports_collection.find_one(query)


def insert_report(data):
    return reports_collection.insert_one(data)


def update_report_by_query(query, update_data):
    return reports_collection.update_one(
        query,
        {
            "$set": update_data
        }
    )


def delete_report_by_query(query):
    return reports_collection.delete_one(query)


def find_report_by_code(report_code):
    return reports_collection.find_one({
        "report_code": report_code
    })


def generate_report_code():
    last_report = reports_collection.find_one(
        {
            "report_code": {
                "$regex": r"^Report-\d{6}$"
            }
        },
        sort=[("report_code", -1)]
    )

    if not last_report:
        return "Report-000001"

    last_code = last_report.get("report_code", "Report-000000")

    try:
        number = int(last_code.replace("Report-", ""))
    except Exception:
        number = 0

    next_number = number + 1

    while True:
        report_code = f"Report-{next_number:06d}"

        if not find_report_by_code(report_code):
            return report_code

        next_number += 1


def is_allowed_file(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_FILE_EXTENSIONS


def save_uploaded_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    original_filename = file_storage.filename
    safe_filename = secure_filename(original_filename)

    if not safe_filename:
        raise ValueError("Tên file không hợp lệ.")

    if not is_allowed_file(safe_filename):
        raise ValueError(f"Định dạng file không được hỗ trợ: {original_filename}")

    extension = safe_filename.rsplit(".", 1)[1].lower()
    stored_filename = f"{uuid4().hex}.{extension}"
    full_path = os.path.join(UPLOAD_FOLDER, stored_filename)

    file_storage.save(full_path)

    return {
        "id": uuid4().hex,
        "original_name": original_filename,
        "stored_name": stored_filename,
        "extension": extension,
        "mime_type": file_storage.mimetype,
        "size": os.path.getsize(full_path),
        "url": f"/api/reports/files/{stored_filename}",
        "uploaded_at": current_vietnam_time(),
    }


def delete_uploaded_file(file_record):
    if not file_record:
        return False

    stored_name = file_record.get("stored_name")

    if not stored_name:
        return False

    full_path = os.path.join(UPLOAD_FOLDER, stored_name)

    if os.path.exists(full_path):
        os.remove(full_path)
        return True

    return False