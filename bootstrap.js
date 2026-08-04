(function () {
  "use strict";

  var applicationScripts = [
    "pricing.js",
    "batch-pricing.js",
    "app.js",
    "batch.js",
    "web-importer.js",
    "updater.js",
  ];

  function loadScript(source) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = source;
      script.onload = resolve;
      script.onerror = function () {
        reject(new Error("无法载入 " + source));
      };
      document.body.appendChild(script);
    });
  }

  async function start() {
    try {
      await window.LOGISTICS_DATA_READY;
      for (var index = 0; index < applicationScripts.length; index += 1) {
        await loadScript(applicationScripts[index]);
      }
    } catch (error) {
      var message = document.getElementById("startup-error");
      if (message) {
        message.textContent = "系统启动失败：" + error.message;
        message.hidden = false;
      }
    }
  }

  start();
})();
