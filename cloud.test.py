from __future__ import annotations

import importlib.util
from io import BytesIO
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import server


def passed(name: str, detail: str = "") -> None:
    print(f"通过：{name}")
    if detail:
        print(f"  {detail}")


def call_handler(path: str, method: str = "GET") -> tuple[int, dict]:
    handler = object.__new__(server.QuoteHandler)
    handler.path = path
    handler.headers = {"Content-Length": "0"}
    handler.rfile = BytesIO()
    handler.wfile = BytesIO()
    response = {"status": 0}
    handler.send_response = lambda status: response.update(status=int(status))
    handler.send_header = lambda _name, _value: None
    handler.end_headers = lambda: None
    handler.log_error = lambda *_args: None
    if method == "POST":
        handler.do_POST()
    else:
        handler.do_GET()
    return response["status"], json.loads(handler.wfile.getvalue().decode("utf-8"))


status_code, status = call_handler("/api/status")
assert status_code == 200
assert status["mode"] == "local"
assert status["supportsExcelImport"] is True
assert status["supportsVersionHistory"] is True
passed("本地维护端状态接口", "能区分本地维护端与Cloudflare共享网页")

status_code, prices = call_handler("/api/prices")
assert status_code == 200
assert prices["source"] == "local"
assert len(prices["channels"]) == 55
assert sum(len(channel["rates"]) for channel in prices["channels"]) == 2898
passed("共享价格读取接口", "55个渠道、2898条费率可供网页统一载入")

original_config_path = server.CLOUD_CONFIG_PATH
try:
    server.CLOUD_CONFIG_PATH = Path(tempfile.gettempdir()) / "missing-logistics-cloud-config.json"
    status_code, payload = call_handler("/api/cloud-publish", "POST")
    assert status_code == 400
    assert "Cloudflare" in "".join(payload["errors"])
    passed("云端发布安全边界", "未完成首次部署和配置时不会误发布价格")
finally:
    server.CLOUD_CONFIG_PATH = original_config_path


build_spec = importlib.util.spec_from_file_location(
    "build_cloud", PROJECT_ROOT / "tools/build_cloud.py"
)
build_cloud = importlib.util.module_from_spec(build_spec)
assert build_spec.loader is not None
build_spec.loader.exec_module(build_cloud)
build_cloud.build()

published = {path.name for path in (PROJECT_ROOT / "dist").iterdir()}
assert set(build_cloud.PUBLIC_FILES) == published
assert "server.py" not in published
assert "importer.py" in published
assert "version-history.json" not in published
assert "cloud-config.local.json" not in published
passed(
    "云端发布目录隔离",
    "包含跨平台网页解析规则，不包含本地服务器、价格历史或同步配置",
)

page_source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
app_source = (PROJECT_ROOT / "app.js").read_text(encoding="utf-8")
assert "方尚科技" in page_source
assert 'id="country-search"' in page_source
assert "renderCountryOptions" in app_source
assert "没有找到匹配的国家" in app_source
passed(
    "单件报价品牌与国家搜索入口",
    "页面显示方尚科技标识，并可按中文国家名称即时筛选目的地",
)
