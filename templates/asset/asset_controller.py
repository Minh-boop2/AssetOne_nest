from flask import Flask, render_template, request
from asset_service import get_all_assets

app = Flask(__name__)

@app.route("/assets")
def assets_page():
    search = request.args.get("search")
    assets = get_all_assets(search)
    return render_template("assets/index.html", assets=assets)