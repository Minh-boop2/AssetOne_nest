from .assign_model import (
    get_assigns_paginated,
    get_assign_by_id,
    delete_assign_by_id,
    update_assign_status_by_id,
)


def list_assigns(
    page=1,
    per_page=10,
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
    location="Tất cả",
):
    return get_assigns_paginated(
        page=page,
        per_page=per_page,
        search=search,
        asset_type=asset_type,
        department=department,
        status=status,
        location=location,
    )


def find_assign(assign_id):
    return get_assign_by_id(assign_id)


def delete_assign(assign_id):
    return delete_assign_by_id(assign_id)


def approve_assign(assign_id):
    return update_assign_status_by_id(assign_id, "Đang sử dụng")


def reject_assign(assign_id):
    return update_assign_status_by_id(assign_id, "Chưa dùng")


def update_assign_status(assign_id, status):
    return update_assign_status_by_id(assign_id, status)