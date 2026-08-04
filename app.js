(function () {
  "use strict";

  var form = document.getElementById("quote-form");
  var countrySelect = document.getElementById("country");
  var channelSelect = document.getElementById("channel");
  var submitButton = document.getElementById("calculate-selected");
  var compareAllButton = document.getElementById("compare-all");
  var emptyResult = document.getElementById("empty-result");
  var quoteResult = document.getElementById("quote-result");
  var errorBox = document.getElementById("form-error");
  var offersList = document.getElementById("offers-list");
  var unavailableSection = document.getElementById("unavailable-section");
  var unavailableList = document.getElementById("unavailable-list");
  var zoneNotice = document.getElementById("zone-notice");

  function formatMoney(value) {
    return "¥" + value.toFixed(2);
  }

  function formatUsdQuote(value) {
    return "$" + value.toFixed(1).replace(/\.0$/, "");
  }

  function element(tagName, className, text) {
    var node = document.createElement(tagName);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function addDetail(container, label, value) {
    var item = element("div", "offer-detail");
    item.appendChild(element("span", "", label));
    item.appendChild(element("strong", "", value));
    container.appendChild(item);
  }

  function renderOffer(offer, index, comparisonMode) {
    var card = element("article", "offer-card" + (index === 0 ? " best-offer" : ""));
    var header = element("div", "offer-header");
    var identity = element("div", "offer-identity");
    var rank = element(
      "span",
      "offer-rank",
      comparisonMode ? (index === 0 ? "推荐" : String(index + 1)) : "所选"
    );
    var nameWrap = element("div");
    nameWrap.appendChild(element("h3", "", offer.channelName));
    var tags = element("div", "offer-tags");
    tags.appendChild(element("span", "company-tag", offer.company));
    tags.appendChild(element("span", "cargo-tag", offer.cargoType));
    if (offer.zone) {
      tags.appendChild(element("span", "zone-tag", offer.zone));
    }
    nameWrap.appendChild(tags);
    identity.appendChild(rank);
    identity.appendChild(nameWrap);

    var price = element("div", "offer-price");
    price.appendChild(element("span", "", "最终报价"));
    price.appendChild(element("strong", "", formatUsdQuote(offer.finalPriceUsd)));
    header.appendChild(identity);
    header.appendChild(price);
    card.appendChild(header);

    var details = element("div", "offer-details");
    addDetail(details, "人民币运费", formatMoney(offer.shippingCost));
    addDetail(
      details,
      "计费重量",
      Number(offer.chargeableWeightG / 1000).toLocaleString("zh-CN", {
        maximumFractionDigits: 3,
      }) + " kg"
    );
    addDetail(details, "重量档位", offer.weightTier);
    addDetail(
      details,
      offer.isWeightedAverage ? "加权公斤单价" : "公斤单价",
      formatMoney(offer.pricePerKg)
    );
    addDetail(
      details,
      offer.isWeightedAverage ? "加权原挂号费" : "原挂号费",
      formatMoney(offer.baseRegistrationFee)
    );
    addDetail(details, "调整后挂号费", formatMoney(offer.registrationFee));
    addDetail(details, "参考时效", offer.transitTime || "—");
    card.appendChild(details);

    if (offer.adjustments.length) {
      var adjustmentLine = element("p", "adjustment-line");
      adjustmentLine.appendChild(element("span", "", "公司调整"));
      adjustmentLine.appendChild(
        element(
          "strong",
          "",
          offer.adjustments
            .map(function (item) {
              return item.label + " +" + formatMoney(item.amount);
            })
            .join("；")
        )
      );
      card.appendChild(adjustmentLine);
    }
    return card;
  }

  function renderResult(result, comparisonMode) {
    document.getElementById("result-country").textContent = result.countryName;
    document.getElementById("available-count").textContent =
      result.offers.length + " 个报价结果";
    offersList.replaceChildren();
    result.offers.forEach(function (offer, index) {
      offersList.appendChild(renderOffer(offer, index, comparisonMode));
    });

    zoneNotice.hidden = !result.hasZones;
    zoneNotice.textContent = result.hasZones
      ? "该国家存在物流分区，当前已分别展示各区价格；正式报价前需结合邮编确认分区。"
      : "";

    unavailableList.replaceChildren();
    result.unavailable.forEach(function (item) {
      unavailableList.appendChild(
        element(
          "span",
          "",
          item.company + " · " + item.channelName + " · " + item.reason
        )
      );
    });
    unavailableSection.hidden = result.unavailable.length === 0;

    if (!result.offers.length) {
      offersList.appendChild(
        element("p", "no-offers", "当前重量在所选国家没有可用报价。")
      );
    }

    emptyResult.hidden = true;
    quoteResult.hidden = false;
  }

  window.Pricing.getCountries().forEach(function (country) {
    var option = document.createElement("option");
    option.value = country;
    option.textContent = country;
    option.selected = country === "美国";
    countrySelect.appendChild(option);
  });

  function populateChannels() {
    var previousValue = channelSelect.value;
    var channels = window.Pricing.getChannelsForCountry(countrySelect.value);
    var companies = {};
    channelSelect.replaceChildren();
    channels.forEach(function (channel) {
      if (!companies[channel.company]) {
        companies[channel.company] = document.createElement("optgroup");
        companies[channel.company].label = channel.company;
        channelSelect.appendChild(companies[channel.company]);
      }
      var option = document.createElement("option");
      option.value = channel.key;
      option.textContent = channel.name + " · " + channel.cargoType;
      option.selected = channel.key === previousValue;
      companies[channel.company].appendChild(option);
    });
    if (!channels.length) {
      var emptyOption = document.createElement("option");
      emptyOption.value = "";
      emptyOption.textContent = "当前国家暂无已录入的可用渠道";
      channelSelect.appendChild(emptyOption);
    }
    channelSelect.disabled = channels.length === 0;
    submitButton.disabled = channels.length === 0;
    document.getElementById("channel-help").textContent = channels.length
      ? "当前国家共有 " + channels.length + " 个已录入渠道可选择"
      : "当前国家需要的指定渠道尚未录入";
  }

  function readInput() {
    return {
      country: countrySelect.value,
      cost: Number(document.getElementById("cost").value),
      weightG: Number(document.getElementById("weight").value) * 1000,
      profit: Number(document.getElementById("profit").value),
      exchangeRate: Number(document.getElementById("exchange-rate").value),
    };
  }

  function showCalculationError(error) {
    quoteResult.hidden = true;
    emptyResult.hidden = false;
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }

  function updateDataSummary() {
    var companyCounts = {};
    window.Pricing.CHANNELS.forEach(function (channel) {
      companyCounts[channel.company] = (companyCounts[channel.company] || 0) + 1;
    });
    var companies = Object.keys(companyCounts);
    document.getElementById("company-count").textContent = companies.length;
    document.getElementById("channel-count").textContent =
      window.Pricing.CHANNELS.length;
    document.getElementById("footer-data-summary").textContent =
      "当前录入" +
      companies
        .map(function (company) {
          return company.replace("物流", "") + companyCounts[company] + "个";
        })
        .join("、") +
      "渠道；新价格必须经过检查、预览和人工确认后才会启用。";

    var dataMeta = window.LOGISTICS_PRICE_META || {};
    document.getElementById("run-mode").textContent =
      dataMeta.label || "当前价格已载入";
    document.querySelector(".privacy-badge").title = dataMeta.warning || "";
  }

  countrySelect.addEventListener("change", function () {
    populateChannels();
    quoteResult.hidden = true;
    emptyResult.hidden = false;
    errorBox.hidden = true;
  });

  updateDataSummary();
  populateChannels();

  var effectiveDates = window.Pricing.CHANNELS.map(function (channel) {
    return channel.effectiveDate;
  }).filter(function (date, index, dates) {
    return dates.indexOf(date) === index;
  });
  document.getElementById("effective-date").textContent =
    effectiveDates.length === 1
      ? "价格生效日 " + effectiveDates[0]
      : "各渠道价格日期：" + effectiveDates.join("、");

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    errorBox.hidden = true;
    try {
      renderResult(
        window.Pricing.calculateChannelQuote(readInput(), channelSelect.value),
        false
      );
    } catch (error) {
      showCalculationError(error);
    }
  });

  compareAllButton.addEventListener("click", function () {
    errorBox.hidden = true;
    try {
      renderResult(window.Pricing.calculateAllQuotes(readInput()), true);
    } catch (error) {
      showCalculationError(error);
    }
  });
})();
