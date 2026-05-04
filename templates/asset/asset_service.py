from .asset_model import (
    get_assets_paginated,
    get_asset_by_id,
    delete_asset_by_id,
    create_asset,
    create_many_assets,
)


def list_assets(
    page=1,
    per_page=10,
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
):
    return get_assets_paginated(
        page=page,
        per_page=per_page,
        search=search,
        asset_type=asset_type,
        department=department,
        status=status,
    )


def find_asset(asset_id):
    return get_asset_by_id(asset_id)


def delete_asset(asset_id):
    return delete_asset_by_id(asset_id)


def add_asset(data):
    return create_asset(data)


def add_many_assets(items):
    return create_many_assets(items)