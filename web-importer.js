(function (root) {
  "use strict";

  var PYODIDE_VERSION = "0.27.7";
  var PYODIDE_BASE =
    "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";
  var MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
  var runtimePromise = null;

  function loadScript(source) {
    return new Promise(function (resolve, reject) {
      var existing = document.querySelector('script[data-runtime="pyodide"]');
      if (existing) {
        existing.addEventListener("load", resolve, { once: true });
        existing.addEventListener("error", reject, { once: true });
        return;
      }
      var script = document.createElement("script");
      script.src = source;
      script.dataset.runtime = "pyodide";
      script.onload = resolve;
      script.onerror = function () {
        reject(new Error("Excel解析引擎下载失败，请检查网络后重试"));
      };
      document.head.appendChild(script);
    });
  }

  async function loadRuntime(onProgress) {
    if (runtimePromise) {
      return runtimePromise;
    }
    runtimePromise = (async function () {
      if (onProgress) {
        onProgress("首次使用正在加载Excel解析引擎，请稍候…");
      }
      if (typeof root.loadPyodide !== "function") {
        await loadScript(PYODIDE_BASE + "pyodide.js");
      }
      var pyodide = await root.loadPyodide({ indexURL: PYODIDE_BASE });
      var sourceResponse = await fetch("importer.py", { cache: "no-store" });
      if (!sourceResponse.ok) {
        throw new Error("无法读取物流价格表解析规则");
      }
      await pyodide.runPythonAsync(await sourceResponse.text());
      return pyodide;
    })();
    try {
      return await runtimePromise;
    } catch (error) {
      runtimePromise = null;
      throw error;
    }
  }

  async function preview(file, currentChannels, onProgress) {
    if (!file || !file.name.toLowerCase().endsWith(".xlsx")) {
      throw new Error("只支持 .xlsx 文件");
    }
    if (file.size <= 0 || file.size > MAX_UPLOAD_BYTES) {
      throw new Error("文件为空或超过50MB，已拒绝读取");
    }
    var pyodide = await loadRuntime(onProgress);
    if (onProgress) {
      onProgress("正在识别物流公司、渠道和价格档位…");
    }
    var bytes = new Uint8Array(await file.arrayBuffer());
    pyodide.FS.writeFile("/tmp/logistics-price.xlsx", bytes);
    pyodide.FS.writeFile(
      "/tmp/current-prices.json",
      new TextEncoder().encode(JSON.stringify(currentChannels))
    );
    var resultText = await pyodide.runPythonAsync(`
import json

def _web_price_preview():
    try:
        with open("/tmp/logistics-price.xlsx", "rb") as handle:
            incoming = parse_price_workbook(handle.read())
        with open("/tmp/current-prices.json", "r", encoding="utf-8") as handle:
            current = json.load(handle)
        merged = merge_company_channels(current, incoming)
        comparison = compare_channels(current, merged)
        return json.dumps({
            "ok": True,
            "updatedCompany": incoming[0]["company"],
            "channels": merged,
            **comparison,
        }, ensure_ascii=False, separators=(",", ":"))
    except ImportValidationError as exc:
        return json.dumps({"ok": False, "errors": exc.errors}, ensure_ascii=False)
    except Exception:
        return json.dumps({
            "ok": False,
            "errors": ["浏览器无法读取这份Excel，请确认文件未损坏且格式与物流公司原表一致"],
        }, ensure_ascii=False)

_web_price_preview()
`);
    var result = JSON.parse(resultText);
    if (!result.ok) {
      throw new Error((result.errors || ["价格表检查未通过"]).join("；"));
    }
    return {
      token: "browser-" + Date.now(),
      filename: file.name,
      updatedCompany: result.updatedCompany,
      channels: result.channels,
      summary: result.summary,
      details: result.details,
      detailsTruncated: result.detailsTruncated,
      channelSummaries: result.channelSummaries,
    };
  }

  root.WebPriceImporter = {
    preview: preview,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
