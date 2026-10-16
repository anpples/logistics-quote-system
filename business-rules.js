(function (root) {
  "use strict";

  var EU_27 = [
    "奥地利",
    "比利时",
    "保加利亚",
    "克罗地亚",
    "塞浦路斯",
    "捷克",
    "丹麦",
    "爱沙尼亚",
    "芬兰",
    "法国",
    "德国",
    "希腊",
    "匈牙利",
    "爱尔兰",
    "意大利",
    "拉脱维亚",
    "立陶宛",
    "卢森堡",
    "马耳他",
    "荷兰",
    "波兰",
    "葡萄牙",
    "罗马尼亚",
    "斯洛伐克",
    "斯洛文尼亚",
    "西班牙",
    "瑞典",
  ];

  var YUNTU_DUTY_CHANNELS = [
    "economy_general",
    "economy_battery",
    "yt_clothing",
  ];

  var DDP_COUNTRY_FEES = {
    阿拉伯联合酋长国: { amount: 1.68, label: "DDP专项税费" },
    沙特阿拉伯: { amount: 39.04, label: "DDP专项税费（5.04+34）" },
    卡塔尔: { amount: 41, label: "DDP专项税费" },
    约旦: { amount: 47.4, label: "DDP专项税费" },
    巴林: { amount: 0, label: "DDP税费" },
    科威特: { amount: 0, label: "DDP税费" },
    摩洛哥: { amount: 18.81, label: "DDP专项税费" },
    罗马尼亚: { amount: 41, label: "DDP专项税费" },
  };

  var DDU_COUNTRY_FEES = {
    阿塞拜疆: null,
    安哥拉: null,
    塞内加尔: null,
    毛里求斯: null,
    留尼汪: null,
    马达加斯加: 6.72,
    塞舌尔: 10.08,
    赞比亚: 8.4,
    马约特: null,
  };

  var TEMPORARILY_UNAVAILABLE_COUNTRIES = [
    "刚果共和国（布）",
    "刚果民主共和国（金）",
    "刚果（布）",
    "刚果（金）",
    "贝宁",
    "马里",
  ];

  var CUSTOMER_ROUTE_PROFILES = {
    "100RANCOEUR": {
      yt_clothing: [
        "法国", "德国", "意大利", "西班牙", "葡萄牙", "奥地利",
        "比利时", "加拿大", "瑞典", "挪威", "丹麦", "爱尔兰", "阿拉伯联合酋长国",
      ],
      economy_general: [
        "英国", "美国", "澳大利亚", "卡塔尔", "沙特阿拉伯", "科威特",
        "瑞士", "芬兰", "波兰", "罗马尼亚", "摩洛哥", "留尼汪", "马约特",
        "塞内加尔", "马达加斯加",
      ],
      economy_battery: ["卢森堡"],
      yw_air_registered_general: [
        "阿尔及利亚", "突尼斯", "摩纳哥", "多哥", "喀麦隆", "加蓬", "几内亚",
      ],
      yw_air_registered_special: ["瓜德罗普", "马提尼克", "法属圭亚那", "科特迪瓦"],
    },
  };

  var AUSTRALIA_ZONE_WEIGHTS = {
    "1区": 0.3,
    "2区": 0.3,
    "3区": 0.3,
    "4区": 0.1,
  };

  function getAustraliaZoneWeights(availableZones) {
    if (
      availableZones.length === 4 &&
      Object.keys(AUSTRALIA_ZONE_WEIGHTS).every(function (zone) {
        return availableZones.indexOf(zone) !== -1;
      })
    ) {
      return AUSTRALIA_ZONE_WEIGHTS;
    }
    if (availableZones.length === 3) {
      return availableZones.reduce(function (weights, zone) {
        weights[zone] = 1 / 3;
        return weights;
      }, {});
    }
    return null;
  }

  function getAdjustments(channelKey, country) {
    var adjustments = [];
    if (EU_27.indexOf(country) !== -1) {
      adjustments.push({ label: "欧盟27国关税附加费", amount: 24 });
    }
    if (country === "英国") {
      adjustments.push({ label: "英国偏远附加费", amount: 2 });
    }
    if (
      YUNTU_DUTY_CHANNELS.indexOf(channelKey) !== -1 &&
      DDP_COUNTRY_FEES[country] &&
      DDP_COUNTRY_FEES[country].amount > 0
    ) {
      adjustments.push(DDP_COUNTRY_FEES[country]);
    }
    return adjustments;
  }

  function getDutyInfo(channelKey, country) {
    if (YUNTU_DUTY_CHANNELS.indexOf(channelKey) === -1) {
      return null;
    }
    if (Object.prototype.hasOwnProperty.call(DDP_COUNTRY_FEES, country)) {
      return {
        mode: "DDP",
        payer: "发件人",
        includedInQuote: true,
        amount: DDP_COUNTRY_FEES[country].amount,
      };
    }
    if (Object.prototype.hasOwnProperty.call(DDU_COUNTRY_FEES, country)) {
      return {
        mode: "DDU",
        payer: "收件人",
        includedInQuote: false,
        referenceAmount: DDU_COUNTRY_FEES[country],
      };
    }
    return null;
  }

  function getQuoteNotices(channelKey, country) {
    var notices = [];
    var dutyInfo = getDutyInfo(channelKey, country);
    if (dutyInfo && dutyInfo.mode === "DDP") {
      notices.push({
        type: "duty",
        text: dutyInfo.amount > 0
          ? "DDP：关税由发件人支付，已按申报价值5美元将专项税费计入报价。"
          : "DDP：关税由发件人支付，当前规则未指定额外税额。",
      });
    }
    if (dutyInfo && dutyInfo.mode === "DDU") {
      var dduText = "DDU：关税由收件人自行支付，未计入最终报价。";
      if (dutyInfo.referenceAmount !== null) {
        dduText += "参考税费约¥" + dutyInfo.referenceAmount.toFixed(2) + "，以当地海关实际征收为准。";
      }
      notices.push({ type: "duty", text: dduText });
    }
    if (country === "沙特阿拉伯") {
      notices.push({
        type: "address",
        text: "沙特派送必须填写4位字母+4位数字的国家短地址（例：RAGI2929），否则可能影响清关、派送并产生罚款。",
      });
    }
    return notices;
  }

  function getCustomerRoute(profileName, country, weightKg) {
    if (TEMPORARILY_UNAVAILABLE_COUNTRIES.indexOf(country) !== -1) {
      return { allowed: false, configured: true, channelKey: "", reason: "暂时无法配送" };
    }
    var profile = CUSTOMER_ROUTE_PROFILES[profileName];
    if (!profile) {
      return { allowed: false, configured: false, channelKey: "", reason: "未知客户方案" };
    }
    if (profileName === "100RANCOEUR" && country === "荷兰") {
      return {
        allowed: true,
        configured: true,
        channelKey:
          weightKg <= 0.2 || (weightKg > 0.5 && weightKg <= 2)
            ? "economy_general"
            : "yt_clothing",
        reason: "荷兰按重量分段选线",
      };
    }
    var channelKey = Object.keys(profile).find(function (key) {
      return profile[key].indexOf(country) !== -1;
    });
    return channelKey
      ? { allowed: true, configured: true, channelKey: channelKey, reason: "" }
      : { allowed: false, configured: false, channelKey: "", reason: "该国家尚未配置100RANCOEUR专用选线" };
  }

  function getRoutingDecision(channelKey, country) {
    if (TEMPORARILY_UNAVAILABLE_COUNTRIES.indexOf(country) !== -1) {
      return {
        allowed: false,
        reason: "公司规则：该国家暂时无法配送",
      };
    }
    if (
      country === "墨西哥" &&
      channelKey !== "yt_selected_general" &&
      channelKey !== "yt_selected_battery"
    ) {
      return {
        allowed: false,
        reason: "公司规则指定使用云途精选普货/带电",
      };
    }
    if (
      country === "新西兰" &&
      channelKey !== "ubi_nz_general" &&
      channelKey !== "ubi_nz_battery"
    ) {
      return {
        allowed: false,
        reason: "公司规则指定新西兰使用 UBI",
      };
    }
    return { allowed: true, reason: "" };
  }

  root.BusinessRules = {
    EU_27: EU_27,
    AUSTRALIA_ZONE_WEIGHTS: AUSTRALIA_ZONE_WEIGHTS,
    DDP_COUNTRY_FEES: DDP_COUNTRY_FEES,
    DDU_COUNTRY_FEES: DDU_COUNTRY_FEES,
    TEMPORARILY_UNAVAILABLE_COUNTRIES: TEMPORARILY_UNAVAILABLE_COUNTRIES,
    CUSTOMER_ROUTE_PROFILES: CUSTOMER_ROUTE_PROFILES,
    getAustraliaZoneWeights: getAustraliaZoneWeights,
    getAdjustments: getAdjustments,
    getDutyInfo: getDutyInfo,
    getQuoteNotices: getQuoteNotices,
    getCustomerRoute: getCustomerRoute,
    getRoutingDecision: getRoutingDecision,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
