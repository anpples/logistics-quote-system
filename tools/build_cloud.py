from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
PUBLIC_FILES = [
    "index.html",
    "styles.css",
    "channel-data.js",
    "business-rules.js",
    "cloud-data.js",
    "bootstrap.js",
    "pricing.js",
    "batch-pricing.js",
    "app.js",
    "batch.js",
    "web-importer.js",
    "updater.js",
    "importer.py",
    "_headers",
]
PYODIDE_SOURCE = ROOT / "node_modules" / "pyodide"


def install_cloud_runtime() -> None:
    if PYODIDE_SOURCE.exists():
        return
    if os.environ.get("CF_PAGES") != "1":
        print("本地构建未安装网页Excel解析组件；Cloudflare部署时会自动安装。")
        return
    subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
        cwd=ROOT,
        check=True,
    )


def build() -> None:
    install_cloud_runtime()
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    for filename in PUBLIC_FILES:
        source = ROOT / filename
        if not source.exists():
            raise SystemExit(f"缺少云端发布文件：{filename}")
        shutil.copy2(source, OUTPUT / filename)
    if PYODIDE_SOURCE.exists():
        shutil.copytree(PYODIDE_SOURCE, OUTPUT / "vendor" / "pyodide")
    print(f"云端发布目录已生成：{OUTPUT}")
    print(
        f"共复制 {len(PUBLIC_FILES)} 个公开文件；包含浏览器价格解析规则，"
        "不包含本地服务器、价格历史或同步配置。"
    )


if __name__ == "__main__":
    build()
