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

  var CHANNEL_COUNTRY_FEES = {
    economy_general: {
      阿拉伯联合酋长国: { amount: 1.68, label: "国家专项税费" },
      沙特阿拉伯: { amount: 39.04, label: "国家专项税费（5.04+34）" },
      卡塔尔: { amount: 41, label: "国家专项税费" },
      约旦: { amount: 47.4, label: "国家专项税费" },
      马达加斯加: { amount: 6.72, label: "国家专项税费" },
      塞舌尔: { amount: 10.08, label: "国家专项税费" },
      赞比亚: { amount: 8.4, label: "国家专项税费" },
      摩洛哥: { amount: 18.81, label: "国家专项税费" },
      罗马尼亚: { amount: 41, label: "渠道国家税费" },
    },
    economy_battery: {
      智利: { amount: 7.42, label: "国家专项税费" },
      阿拉伯联合酋长国: { amount: 1.68, label: "国家专项税费" },
      沙特阿拉伯: { amount: 39.04, label: "国家专项税费（5.04+34）" },
      卡塔尔: { amount: 41, label: "国家专项税费" },
      约旦: { amount: 47.4, label: "国家专项税费" },
      马达加斯加: { amount: 6.72, label: "国家专项税费" },
      塞舌尔: { amount: 10.08, label: "国家专项税费" },
      赞比亚: { amount: 8.4, label: "国家专项税费" },
      摩洛哥: { amount: 18.81, label: "国家专项税费" },
      罗马尼亚: { amount: 41, label: "渠道国家税费" },
    },
    cosmetics: {
      新西兰: { amount: 8.72, label: "新西兰税费" },
      阿拉伯联合酋长国: { amount: 1.68, label: "国家专项税费" },
      沙特阿拉伯: { amount: 39.04, label: "国家专项税费（5.04+34）" },
      卡塔尔: { amount: 41, label: "国家专项税费" },
      罗马尼亚: { amount: 41, label: "渠道国家税费" },
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
      adjustments.push({ label: "欧盟27国税费", amount: 24 });
    }
    if (country === "英国") {
      adjustments.push({ label: "英国偏远附加费", amount: 2 });
    }
    var channelFees = CHANNEL_COUNTRY_FEES[channelKey] || {};
    if (channelFees[country]) {
      adjustments.push(channelFees[country]);
    }
    return adjustments;
  }

  function getRoutingDecision(channelKey, country) {
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
      channelKey !== "cosmetics" &&
      channelKey !== "yp_nz_remote" &&
      channelKey !== "ubi_nz_general" &&
      channelKey !== "ubi_nz_battery"
    ) {
      return {
        allowed: false,
        reason: "公司规则指定普货/带电使用 UBI，化妆品使用云途",
      };
    }
    return { allowed: true, reason: "" };
  }

  root.BusinessRules = {
    EU_27: EU_27,
    AUSTRALIA_ZONE_WEIGHTS: AUSTRALIA_ZONE_WEIGHTS,
    getAustraliaZoneWeights: getAustraliaZoneWeights,
    getAdjustments: getAdjustments,
    getRoutingDecision: getRoutingDecision,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
