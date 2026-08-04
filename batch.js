(function () {
  "use strict";

  var MAJOR_MARKETS = [
    "美国", "加拿大", "英国", "法国", "德国", "意大利", "西班牙",
    "荷兰", "澳大利亚", "新西兰", "日本", "韩国", "新加坡",
    "阿拉伯联合酋长国", "沙特阿拉伯",
  ];
  var form = document.getElementById("batch-form");
  var dataInput = document.getElementById("batch-data");
  var dataStatus = document.getElementById("batch-data-status");
  var preview = document.getElementById("batch-preview");
  var previewBody = document.getElementById("batch-preview-body");
  var previewMore = document.getElementById("batch-preview-more");
  var channelSelect = document.getElementById("batch-channel");
  var countryList = document.getElementById("batch-country-list");
  var countrySearch = document.getElementById("batch-country-search");
  var countryCount = document.getElementById("batch-country-count");
  var errorBox = document.getElementById("batch-error");
  var resultSection = document.getElementById("batch-result");
  var resultTable = document.getElementById("batch-result-table");
  var lastResult = null;

  function node(tagName, className, text) {
    var element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text !== undefined) {
      element.textContent = text;
    }
    return element;
  }

  function formatNumber(value) {
    return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 3 });
  }

  function formatWeightKg(weightG) {
    return formatNumber(weightG / 1000) + " kg";
  }

  function populateChannels() {
    var groups = {};
    channelSelect.replaceChildren();
    window.Pricing.CHANNELS.forEach(function (channel) {
      if (!groups[channel.company]) {
        groups[channel.company] = document.createElement("optgroup");
        groups[channel.company].label = channel.company;
        channelSelect.appendChild(groups[channel.company]);
      }
      var option = document.createElement("option");
      option.value = channel.key;
      option.textContent = channel.name + " · " + channel.cargoType;
      option.selected = channel.key === "economy_general";
      groups[channel.company].appendChild(option);
    });
  }

  function selectedCountries() {
    return Array.from(
      countryList.querySelectorAll(".batch-country-checkbox:checked")
    ).map(function (checkbox) {
      return checkbox.value;
    });
  }

  function updateCountryCount() {
    countryCount.textContent = "已选择 " + selectedCountries().length + " 个";
  }

  function populateCountries(preserveSelection) {
    var previous = preserveSelection ? selectedCountries() : [];
    var supported = window.Pricing.getCountriesForChannel(channelSelect.value);
    var initialSelection = previous.filter(function (country) {
      return supported.indexOf(country) !== -1;
    });
    if (!initialSelection.length) {
      initialSelection = MAJOR_MARKETS.filter(function (country) {
        return supported.indexOf(country) !== -1;
      });
    }
    countryList.replaceChildren();
    supported.forEach(function (country) {
      var label = node("label", "country-option");
      label.dataset.search = country.toLowerCase();
      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "batch-country-checkbox";
      checkbox.value = country;
      checkbox.checked = initialSelection.indexOf(country) !== -1;
      label.appendChild(checkbox);
      label.appendChild(node("span", "", country));
      countryList.appendChild(label);
    });
    countrySearch.value = "";
    updateCountryCount();
  }

  function setCountrySelection(mode) {
    var supported = window.Pricing.getCountriesForChannel(channelSelect.value);
    countryList.querySelectorAll(".batch-country-checkbox").forEach(function (checkbox) {
      if (mode === "all") {
        checkbox.checked = true;
      } else if (mode === "major") {
        checkbox.checked = MAJOR_MARKETS.indexOf(checkbox.value) !== -1 &&
          supported.indexOf(checkbox.value) !== -1;
      } else {
        checkbox.checked = false;
      }
    });
    updateCountryCount();
  }

  function renderDataPreview(parsed) {
    previewBody.replaceChildren();
    parsed.rows.slice(0, 5).forEach(function (row) {
      var tableRow = document.createElement("tr");
      tableRow.appendChild(node("td", "", row.sku));
      tableRow.appendChild(node("td", "", "¥" + formatNumber(row.cost)));
      tableRow.appendChild(node("td", "", formatWeightKg(row.weightG)));
      previewBody.appendChild(tableRow);
    });
    previewMore.textContent = parsed.rows.length > 5
      ? "已预览前 5 行，另有 " + (parsed.rows.length - 5) + " 行。"
      : "";
    preview.hidden = parsed.rows.length === 0;
    dataStatus.className = "batch-data-status" + (parsed.errors.length ? " error" : " success");
    if (parsed.errors.length) {
      dataStatus.textContent = parsed.errors.slice(0, 3).join("；") +
        (parsed.errors.length > 3 ? "；另有 " + (parsed.errors.length - 3) + " 个问题" : "");
    } else {
      dataStatus.textContent = "已识别 " + parsed.rows.length + " 个 SKU，数据格式正确。";
    }
  }

  function parseCurrentRows() {
    return window.BatchPricing.parseRows(dataInput.value);
  }

  function renderResult(result) {
    lastResult = result;
    document.getElementById("batch-result-title").textContent =
      result.company + " · " + result.channelName;
    var successful = result.quoteCount - result.unavailableCount;
    var summary = result.rows.length + " 个 SKU × " + result.countries.length +
      " 个国家，共生成 " + successful + " 个有效报价";
    if (result.unavailableCount) {
      summary += "，" + result.unavailableCount + " 个不可用";
    }
    if (result.zonedCount) {
      summary += "，" + result.zonedCount + " 个分区价格区间";
    }
    document.getElementById("batch-result-summary").textContent = summary;

    var head = document.createElement("thead");
    var headRow = document.createElement("tr");
    ["SKU", "商品成本", "计费重量"].concat(result.countries).forEach(function (heading) {
      headRow.appendChild(node("th", "", heading));
    });
    head.appendChild(headRow);
    var body = document.createElement("tbody");
    result.rows.forEach(function (row) {
      var tableRow = document.createElement("tr");
      tableRow.appendChild(node("th", "batch-sku-cell", row.sku));
      tableRow.appendChild(node("td", "batch-source-cell", "¥" + formatNumber(row.cost)));
      tableRow.appendChild(node("td", "batch-source-cell", formatWeightKg(row.weightG)));
      result.countries.forEach(function (country) {
        var cell = row.cells[country];
        var priceCell = node(
          "td",
          "batch-price-cell " + cell.status,
          cell.status === "unavailable" ? "不可用" : "$" + cell.display
        );
        if (cell.status === "unavailable") {
          priceCell.title = cell.reason;
        } else if (cell.status === "zoned") {
          priceCell.title = "该国家存在多个物流分区，显示最低至最高报价";
        } else {
          priceCell.title = "人民币运费 ¥" + cell.shippingCost.toFixed(2);
        }
        tableRow.appendChild(priceCell);
      });
      body.appendChild(tableRow);
    });
    resultTable.replaceChildren(head, body);
    resultSection.hidden = false;
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function showTemporaryButtonText(button, text) {
    var original = button.textContent;
    button.textContent = text;
    setTimeout(function () { button.textContent = original; }, 1400);
  }

  function fallbackCopy(text) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    var copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  }

  populateChannels();
  populateCountries(false);

  dataInput.addEventListener("input", function () {
    if (!dataInput.value.trim()) {
      dataStatus.className = "batch-data-status";
      dataStatus.textContent = "等待粘贴商品数据";
      preview.hidden = true;
      return;
    }
    renderDataPreview(parseCurrentRows());
  });

  channelSelect.addEventListener("change", function () {
    populateCountries(true);
    resultSection.hidden = true;
    lastResult = null;
  });

  countryList.addEventListener("change", updateCountryCount);
  countrySearch.addEventListener("input", function () {
    var keyword = countrySearch.value.trim().toLowerCase();
    countryList.querySelectorAll(".country-option").forEach(function (option) {
      option.hidden = keyword && option.dataset.search.indexOf(keyword) === -1;
    });
  });
  document.getElementById("select-major-markets").addEventListener("click", function () {
    setCountrySelection("major");
  });
  document.getElementById("select-all-countries").addEventListener("click", function () {
    setCountrySelection("all");
  });
  document.getElementById("clear-countries").addEventListener("click", function () {
    setCountrySelection("clear");
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    errorBox.hidden = true;
    var parsed = parseCurrentRows();
    renderDataPreview(parsed);
    if (parsed.errors.length) {
      showError("请先修正粘贴数据中的问题，再生成报价。");
      return;
    }
    try {
      renderResult(window.BatchPricing.calculateBatch({
        rows: parsed.rows,
        countries: selectedCountries(),
        channelKey: channelSelect.value,
        profit: Number(document.getElementById("batch-profit").value),
        exchangeRate: Number(document.getElementById("batch-exchange-rate").value),
      }));
    } catch (error) {
      showError(error.message);
    }
  });

  document.getElementById("copy-batch-result").addEventListener("click", async function (event) {
    if (!lastResult) {
      return;
    }
    var text = window.BatchPricing.toTsv(lastResult);
    var copied = false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        copied = true;
      }
    } catch (_error) {
      copied = false;
    }
    if (!copied) {
      copied = fallbackCopy(text);
    }
    showTemporaryButtonText(event.currentTarget, copied ? "已复制，可粘贴到表格" : "复制失败");
  });

  document.getElementById("download-batch-result").addEventListener("click", function () {
    if (!lastResult) {
      return;
    }
    var blob = new Blob([window.BatchPricing.toCsv(lastResult)], {
      type: "text/csv;charset=utf-8",
    });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "批量报价-" + lastResult.channelName.replace(/[\\/:*?\"<>|]/g, "-") + ".csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(link.href); }, 0);
  });
})();
