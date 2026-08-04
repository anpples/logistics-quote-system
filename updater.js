(function () {
  "use strict";

  var serverRequired = document.getElementById("server-required");
  var cloudUpdateInfo = document.getElementById("cloud-update-info");
  var updateLive = document.getElementById("update-live");
  var fileInput = document.getElementById("price-file");
  var fileLabel = document.getElementById("file-picker-label");
  var previewButton = document.getElementById("preview-update");
  var applyButton = document.getElementById("apply-update");
  var statusBox = document.getElementById("update-status");
  var previewPanel = document.getElementById("preview-panel");
  var publishCloudButton = document.getElementById("publish-cloud-prices");
  var cloudSyncDescription = document.getElementById("cloud-sync-description");
  var localCloudSyncPanel = document.getElementById("local-cloud-sync-panel");
  var versionHistorySection = document.getElementById("version-history-section");
  var stagedToken = "";
  var stagedCloudChannels = null;
  var stagedUpdatedCompany = "";
  var activeVersionId = "";
  var runtimeMode = "file";
  var cloudHasPublishedPrices = true;

  function node(tag, className, text) {
    var element = document.createElement(tag);
    if (className) {
      element.className = className;
    }
    if (text !== undefined) {
      element.textContent = text;
    }
    return element;
  }

  function showStatus(message, type) {
    statusBox.className = "update-status " + (type || "");
    statusBox.textContent = message;
    statusBox.hidden = false;
  }

  function clearStatus() {
    statusBox.hidden = true;
    statusBox.textContent = "";
  }

  function fieldLabel(field) {
    return {
      pricePerKg: "公斤单价",
      registrationFee: "挂号费",
      incrementKg: "进位制",
      minimumWeightKg: "最低计费重",
      transitTime: "参考时效",
    }[field] || field;
  }

  function formatValue(value, field) {
    if (field === "pricePerKg" || field === "registrationFee") {
      return "¥" + Number(value).toFixed(2);
    }
    if (field === "incrementKg" || field === "minimumWeightKg") {
      return value + " kg";
    }
    return String(value);
  }

  function renderPreview(data) {
    stagedToken = data.token;
    document.getElementById("preview-file-name").textContent =
      data.updatedCompany + " · " + data.filename + " · 已通过结构检查";
    var stats = document.getElementById("preview-stats");
    stats.replaceChildren();
    [
      ["新增", data.summary.added, "added"],
      ["变更", data.summary.changed, "changed"],
      ["删除", data.summary.removed, "removed"],
      ["未变化", data.summary.unchanged, "same"],
    ].forEach(function (item) {
      var card = node("div", "stat-card " + item[2]);
      card.appendChild(node("span", "", item[0]));
      card.appendChild(node("strong", "", String(item[1])));
      stats.appendChild(card);
    });

    var channelChecks = document.getElementById("channel-checks");
    channelChecks.replaceChildren();
    data.channelSummaries.forEach(function (channel) {
      var item = node("div", "channel-check");
      item.appendChild(node("strong", "", channel.name));
      item.appendChild(
        node(
          "span",
          "",
          channel.effectiveDate +
            " · " +
            channel.countryCount +
            "个国家/地区 · " +
            channel.rateCount +
            "条费率"
        )
      );
      channelChecks.appendChild(item);
    });

    var totalChanges =
      data.summary.added + data.summary.changed + data.summary.removed;
    var noChanges = document.getElementById("no-price-changes");
    noChanges.hidden = totalChanges !== 0;
    var needsInitialCloudPublish =
      runtimeMode === "cloud" && !cloudHasPublishedPrices;
    noChanges.textContent = needsInitialCloudPublish
      ? "新文件与内置价格完全一致。请确认发布，完成云端价格初始化。"
      : "新文件与当前价格完全一致，无需更新。";
    applyButton.disabled = totalChanges === 0 && !needsInitialCloudPublish;

    var changeList = document.getElementById("change-list");
    changeList.replaceChildren();
    data.details.forEach(function (change) {
      var row = node("article", "change-row");
      var identity = node("div", "change-identity");
      identity.appendChild(node("span", "change-type " + change.type, change.type));
      var name = node("div");
      name.appendChild(node("strong", "", change.channel + " · " + change.country));
      name.appendChild(
        node("small", "", (change.zone ? change.zone + " · " : "") + change.tier)
      );
      identity.appendChild(name);
      row.appendChild(identity);
      if (change.differences.length) {
        var differences = node("div", "difference-list");
        change.differences.forEach(function (difference) {
          differences.appendChild(
            node(
              "span",
              "",
              fieldLabel(difference.field) +
                "：" +
                formatValue(difference.old, difference.field) +
                " → " +
                formatValue(difference.new, difference.field)
            )
          );
        });
        row.appendChild(differences);
      }
      changeList.appendChild(row);
    });
    if (data.detailsTruncated) {
      changeList.appendChild(
        node("p", "change-truncated", "变更较多，当前仅展示前200条明细。")
      );
    }
    previewPanel.hidden = false;
  }

  async function readError(response) {
    try {
      var payload = await response.json();
      if (payload.errors && payload.errors.length) {
        return payload.errors.join("；");
      }
      return payload.error || "操作失败";
    } catch (_error) {
      return "操作失败";
    }
  }

  async function loadVersions() {
    var list = document.getElementById("version-list");
    var statusList = document.getElementById("company-status-list");
    try {
      var response = await fetch("/api/versions", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(await readError(response));
      }
      var data = await response.json();
      activeVersionId = data.activeVersionId;
      var currentCompanyVersions = {};
      statusList.replaceChildren();
      data.companyStatuses.forEach(function (status) {
        currentCompanyVersions[status.company] = status.versionId;
        var card = node("article", "company-status-card");
        var heading = node("div", "company-status-card-heading");
        heading.appendChild(
          node(
            "strong",
            "",
            status.company +
              (status.parentCompany ? "（隶属" + status.parentCompany + "）" : "")
          )
        );
        heading.appendChild(node("span", "current-version-badge", "使用中"));
        card.appendChild(heading);
        card.appendChild(node("p", "company-source-file", status.sourceFile));
        var applied = status.appliedAt ? new Date(status.appliedAt) : null;
        card.appendChild(
          node(
            "span",
            "",
            status.channelCount +
              "个渠道 · " +
              status.rateCount +
              "条费率 · 生效日 " +
              status.effectiveDates.join("、") +
              (applied ? " · 启用于 " + applied.toLocaleString("zh-CN") : "")
          )
        );
        statusList.appendChild(card);
      });

      list.replaceChildren();
      data.versions.forEach(function (version) {
        var item = node("article", "version-row");
        var info = node("div");
        var companies = version.changedCompanies.length
          ? version.changedCompanies.join("、")
          : "历史价格";
        var title = node("strong", "", companies + " · " + version.action + "记录");
        info.appendChild(title);
        var applied = new Date(version.appliedAt);
        info.appendChild(
          node(
            "span",
            "",
            version.sourceFile +
              " · " +
              applied.toLocaleString("zh-CN") +
              (version.id === activeVersionId ? " · 最近一次系统操作" : "")
          )
        );
        if (version.companySummaries.length) {
          info.appendChild(
            node(
              "small",
              "version-company-summary",
              version.companySummaries
                .map(function (summary) {
                  return (
                    summary.company +
                    "：" +
                    summary.channelCount +
                    "个渠道 / " +
                    summary.rateCount +
                    "条费率"
                  );
                })
                .join("；")
            )
          );
        }
        item.appendChild(info);
        var actions = node("div", "version-actions");
        version.companySummaries.forEach(function (summary) {
          if (currentCompanyVersions[summary.company] === version.id) {
            actions.appendChild(
              node("span", "company-in-use-badge", summary.company + "使用中")
            );
            return;
          }
          var button = node(
            "button",
            "rollback-button",
            "恢复" + summary.company + "价格"
          );
          button.type = "button";
          button.dataset.versionId = version.id;
          button.dataset.company = summary.company;
          actions.appendChild(button);
        });
        item.appendChild(actions);
        list.appendChild(item);
      });
    } catch (error) {
      list.replaceChildren(node("p", "version-loading", error.message));
    }
  }

  function loadCloudCurrentPrices() {
    var statusList = document.getElementById("company-status-list");
    var grouped = {};
    window.Pricing.CHANNELS.forEach(function (channel) {
      if (!grouped[channel.company]) {
        grouped[channel.company] = [];
      }
      grouped[channel.company].push(channel);
    });
    var meta = window.LOGISTICS_PRICE_META || {};
    var companyVersions = meta.companyVersions || {};
    activeVersionId = meta.activeVersionId || "";
    statusList.replaceChildren();
    Object.keys(grouped).forEach(function (company) {
      var channels = grouped[company];
      var companyMeta = companyVersions[company] || {};
      var effectiveDates = channels
        .map(function (channel) { return channel.effectiveDate; })
        .filter(function (date, index, dates) { return dates.indexOf(date) === index; });
      var card = node("article", "company-status-card");
      var heading = node("div", "company-status-card-heading");
      heading.appendChild(node("strong", "", company));
      heading.appendChild(node("span", "current-version-badge", "使用中"));
      card.appendChild(heading);
      card.appendChild(
        node("p", "company-source-file", companyMeta.sourceFile || "初始价格快照")
      );
      var applied = companyMeta.updatedAt ? new Date(companyMeta.updatedAt) : null;
      card.appendChild(
        node(
          "span",
          "",
          channels.length +
            "个渠道 · " +
            channels.reduce(function (sum, channel) { return sum + channel.rates.length; }, 0) +
            "条费率 · 生效日 " +
            effectiveDates.join("、") +
            (applied ? " · 启用于 " + applied.toLocaleString("zh-CN") : "")
        )
      );
      statusList.appendChild(card);
    });
  }

  document.querySelectorAll(".mode-button").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".mode-button").forEach(function (item) {
        item.classList.toggle("active", item === button);
      });
      document.querySelectorAll(".app-view").forEach(function (view) {
        view.hidden = view.id !== button.dataset.view;
      });
    });
  });

  fileInput.addEventListener("change", function () {
    clearStatus();
    previewPanel.hidden = true;
    stagedToken = "";
    stagedCloudChannels = null;
    stagedUpdatedCompany = "";
    var file = fileInput.files[0];
    fileLabel.textContent = file ? file.name : "选择 .xlsx 文件";
    previewButton.disabled = !file;
  });

  previewButton.addEventListener("click", async function () {
    var file = fileInput.files[0];
    if (!file) {
      return;
    }
    clearStatus();
    previewButton.disabled = true;
    previewButton.firstChild.textContent = "正在检查价格表… ";
    try {
      var preview;
      if (runtimeMode === "cloud") {
        preview = await window.WebPriceImporter.preview(
          file,
          window.Pricing.CHANNELS,
          function (message) { showStatus(message, ""); }
        );
        stagedCloudChannels = preview.channels;
        stagedUpdatedCompany = preview.updatedCompany;
      } else {
        var response = await fetch("/api/import-preview", {
          method: "POST",
          headers: {
            "Content-Type":
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "X-File-Name": encodeURIComponent(file.name),
          },
          body: file,
        });
        if (!response.ok) {
          throw new Error(await readError(response));
        }
        preview = await response.json();
      }
      renderPreview(preview);
      showStatus("检查通过。请查看下方差异，确认前不会更新价格。", "success");
    } catch (error) {
      previewPanel.hidden = true;
      showStatus(error.message, "error");
    } finally {
      previewButton.disabled = false;
      previewButton.firstChild.textContent = "检查并生成差异预览 ";
    }
  });

  applyButton.addEventListener("click", async function () {
    if (!stagedToken) {
      return;
    }
    var confirmation = runtimeMode === "cloud"
      ? "确认启用预览中的新价格吗？启用后所有同事刷新网页都会使用该版本。"
      : "确认启用预览中的新价格吗？当前版本会保留，可稍后恢复。";
    if (!window.confirm(confirmation)) {
      return;
    }
    applyButton.disabled = true;
    applyButton.textContent = "正在启用…";
    try {
      var response;
      if (runtimeMode === "cloud") {
        if (!stagedCloudChannels) {
          throw new Error("更新预览已失效，请重新选择文件");
        }
        response = await fetch("/api/prices", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            baseVersionId: activeVersionId,
            sourceFile: fileInput.files[0].name,
            updatedCompany: stagedUpdatedCompany,
            channels: stagedCloudChannels,
          }),
        });
      } else {
        response = await fetch("/api/import-apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: stagedToken }),
        });
      }
      if (!response.ok) {
        throw new Error(await readError(response));
      }
      showStatus("新价格已启用，页面即将刷新。", "success");
      setTimeout(function () {
        location.reload();
      }, 900);
    } catch (error) {
      showStatus(error.message, "error");
      applyButton.disabled = false;
      applyButton.textContent = "确认启用新价格";
    }
  });

  document.getElementById("version-list").addEventListener("click", async function (event) {
    var button = event.target.closest(".rollback-button");
    if (!button) {
      return;
    }
    var company = button.dataset.company;
    if (
      !window.confirm(
        "确认恢复" + company + "的这个旧价格吗？其他物流公司的价格不会改变。"
      )
    ) {
      return;
    }
    button.disabled = true;
    button.textContent = "正在恢复…";
    try {
      var response = await fetch("/api/rollback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          versionId: button.dataset.versionId,
          company: company,
        }),
      });
      if (!response.ok) {
        throw new Error(await readError(response));
      }
      location.reload();
    } catch (error) {
      showStatus(error.message, "error");
      button.disabled = false;
      button.textContent = "恢复" + company + "价格";
    }
  });

  publishCloudButton.addEventListener("click", async function () {
    if (publishCloudButton.disabled) {
      return;
    }
    if (!window.confirm("确认把本机当前价格同步到公司共享网页吗？")) {
      return;
    }
    publishCloudButton.disabled = true;
    publishCloudButton.textContent = "正在同步…";
    try {
      var response = await fetch("/api/cloud-publish", { method: "POST" });
      if (!response.ok) {
        throw new Error(await readError(response));
      }
      var result = await response.json();
      showStatus(
        "云端同步成功：" + result.channelCount + "个渠道、" + result.rateCount + "条费率。",
        "success"
      );
      publishCloudButton.textContent = "已同步，可再次发布";
    } catch (error) {
      showStatus(error.message, "error");
      publishCloudButton.textContent = "重新同步当前价格";
    } finally {
      publishCloudButton.disabled = false;
    }
  });

  async function initializeRuntime() {
    serverRequired.hidden = true;
    cloudUpdateInfo.hidden = true;
    updateLive.hidden = true;
    try {
      var response = await fetch("/api/status", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("价格维护服务未启动");
      }
      var status = await response.json();
      if (status.mode === "cloud") {
        runtimeMode = "cloud";
        cloudHasPublishedPrices = Boolean(status.hasPublishedPrices);
        if (!status.storageReady || !status.supportsExcelImport) {
          cloudUpdateInfo.hidden = false;
          cloudUpdateInfo.querySelector("p").textContent =
            "共享价格存储尚未连接，完成Cloudflare数据绑定后即可在线上传价格表。";
          return;
        }
        updateLive.hidden = false;
        localCloudSyncPanel.hidden = true;
        versionHistorySection.hidden = true;
        document.getElementById("upload-processing-note").textContent =
          "文件只在当前浏览器中解析，不会上传原始Excel；确认后仅更新共享费率。";
        loadCloudCurrentPrices();
        return;
      }
      if (status.mode !== "local" || !status.supportsExcelImport) {
        throw new Error("当前服务不支持Excel价格更新");
      }
      updateLive.hidden = false;
      runtimeMode = "local";
      localCloudSyncPanel.hidden = false;
      versionHistorySection.hidden = false;
      if (status.cloudSync && status.cloudSync.configured) {
        publishCloudButton.disabled = false;
        publishCloudButton.textContent = "同步当前价格到公司网页";
        cloudSyncDescription.textContent =
          "已连接 " + status.cloudSync.siteUrl + "。确认Excel更新后，点击右侧按钮即可让所有同事使用新价格。";
      } else {
        publishCloudButton.disabled = true;
        publishCloudButton.textContent = "尚未连接公司网页";
      }
      loadVersions();
    } catch (error) {
      serverRequired.hidden = false;
      serverRequired.querySelector("strong").textContent = "价格更新功能尚未启动";
      serverRequired.querySelector("p").innerHTML =
        "请关闭当前文件页面，在项目文件夹中双击 <code>start.command</code>，再打开终端窗口显示的网址。";
    }
  }

  initializeRuntime();
})();
