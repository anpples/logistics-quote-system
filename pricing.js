(function (root) {
  "use strict";

  var CHANNELS = root.LOGISTICS_CHANNELS || root.YUNTU_CHANNELS || [];
  var RULES = root.BusinessRules;

  function roundMoney(value) {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }

  function roundQuoteUpToTenth(value) {
    return Math.ceil((value - 1e-12) * 10) / 10;
  }

  function requirePositiveNumber(value, fieldName, allowZero) {
    var number = Number(value);
    var valid = Number.isFinite(number) && (allowZero ? number >= 0 : number > 0);
    if (!valid) {
      throw new Error(fieldName + (allowZero ? "不能小于 0" : "必须大于 0"));
    }
    return number;
  }

  function roundUp(value, increment) {
    if (!increment) {
      return value;
    }
    return Math.ceil((value - 1e-12) / increment) * increment;
  }

  function groupRatesByZone(rates) {
    return rates.reduce(function (groups, rate) {
      var key = rate.zone || "";
      if (!groups[key]) {
        groups[key] = [];
      }
      groups[key].push(rate);
      return groups;
    }, {});
  }

  function findTierAndWeight(rates, actualWeightKg) {
    var minimumWeightKg = rates.reduce(function (current, rate) {
      return Math.max(current, rate.minimumWeightKg || 0);
    }, 0);
    var baseWeightKg = Math.max(actualWeightKg, minimumWeightKg);
    var tier = null;
    var chargeableWeightKg = baseWeightKg;

    for (var attempt = 0; attempt < 6; attempt += 1) {
      tier = rates.find(function (candidate) {
        return (
          chargeableWeightKg > candidate.minKg - 1e-12 &&
          chargeableWeightKg <= candidate.maxKg + 1e-12
        );
      });
      if (!tier) {
        return null;
      }
      var roundedWeightKg = roundUp(baseWeightKg, tier.incrementKg || 0);
      if (Math.abs(roundedWeightKg - chargeableWeightKg) < 1e-12) {
        break;
      }
      chargeableWeightKg = roundedWeightKg;
    }

    if (
      !tier ||
      chargeableWeightKg <= tier.minKg - 1e-12 ||
      chargeableWeightKg > tier.maxKg + 1e-12
    ) {
      tier = rates.find(function (candidate) {
        return (
          chargeableWeightKg > candidate.minKg - 1e-12 &&
          chargeableWeightKg <= candidate.maxKg + 1e-12
        );
      });
    }
    return tier ? { tier: tier, chargeableWeightKg: chargeableWeightKg } : null;
  }

  function calculateBaseOffer(rates, actualWeightKg) {
    var matched = findTierAndWeight(rates, actualWeightKg);
    if (!matched) {
      return null;
    }
    return {
      chargeableWeightKg: matched.chargeableWeightKg,
      incrementKg: matched.tier.incrementKg,
      minimumWeightKg: matched.tier.minimumWeightKg,
      minKg: matched.tier.minKg,
      maxKg: matched.tier.maxKg,
      pricePerKg: matched.tier.pricePerKg,
      baseRegistrationFee: matched.tier.registrationFee,
      transitTime: matched.tier.transitTime,
      sourceRow: matched.tier.sourceRow,
    };
  }

  function calculateAustraliaAverage(groups, actualWeightKg) {
    var availableZones = Object.keys(groups);
    var weights = RULES.getAustraliaZoneWeights(availableZones);
    if (!weights) {
      return {
        offer: null,
        reason:
          "澳大利亚当前有 " +
          availableZones.length +
          " 个分区，仅支持三区等权或四区30%/30%/30%/10%加权",
      };
    }
    var requiredZones = Object.keys(weights);

    var zoneOffers = requiredZones.map(function (zone) {
      return { zone: zone, offer: calculateBaseOffer(groups[zone], actualWeightKg) };
    });
    if (zoneOffers.some(function (item) { return !item.offer; })) {
      return { offer: null, reason: "重量超出澳大利亚分区报价范围" };
    }

    var firstWeight = zoneOffers[0].offer.chargeableWeightKg;
    var sameChargeableWeight = zoneOffers.every(function (item) {
      return Math.abs(item.offer.chargeableWeightKg - firstWeight) < 1e-12;
    });
    if (!sameChargeableWeight) {
      return { offer: null, reason: "澳大利亚各区计费重量不一致，需人工确认" };
    }

    var averagePricePerKg = roundMoney(
      zoneOffers.reduce(function (sum, item) {
        return sum + item.offer.pricePerKg * weights[item.zone];
      }, 0)
    );
    var averageRegistrationFee = roundMoney(
      zoneOffers.reduce(function (sum, item) {
        return sum + item.offer.baseRegistrationFee * weights[item.zone];
      }, 0)
    );
    var tiers = zoneOffers.map(function (item) {
      return item.offer.minKg + "-" + item.offer.maxKg;
    });
    var sameTier = tiers.every(function (tier) { return tier === tiers[0]; });

    return {
      offer: {
        chargeableWeightKg: firstWeight,
        incrementKg: zoneOffers[0].offer.incrementKg,
        minimumWeightKg: zoneOffers[0].offer.minimumWeightKg,
        minKg: zoneOffers[0].offer.minKg,
        maxKg: zoneOffers[0].offer.maxKg,
        pricePerKg: averagePricePerKg,
        baseRegistrationFee: averageRegistrationFee,
        transitTime: zoneOffers[0].offer.transitTime,
        sourceRow: zoneOffers.map(function (item) { return item.offer.sourceRow; }),
        weightTier: sameTier
          ? zoneOffers[0].offer.minKg + "＜W≤" + zoneOffers[0].offer.maxKg + " kg"
          : "各区对应档位",
        zone: requiredZones.length === 3 ? "三区等权均价" : "四区加权均价",
        isWeightedAverage: true,
      },
      reason: "",
    };
  }

  function applyBusinessAdjustments(channel, country, baseOffer, input) {
    var adjustments = RULES.getAdjustments(channel.key, country);
    var adjustmentTotal = roundMoney(
      adjustments.reduce(function (sum, item) { return sum + item.amount; }, 0)
    );
    var registrationFee = roundMoney(
      baseOffer.baseRegistrationFee + adjustmentTotal
    );
    var shippingCost = roundMoney(
      baseOffer.chargeableWeightKg * baseOffer.pricePerKg + registrationFee
    );

    return {
      channelKey: channel.key,
      company: channel.company,
      channelName: channel.name,
      fullName: channel.fullName,
      cargoType: channel.cargoType,
      countryName: country,
      zone: baseOffer.zone || "",
      isWeightedAverage: Boolean(baseOffer.isWeightedAverage),
      transitTime: baseOffer.transitTime,
      actualWeightG: input.weightG,
      chargeableWeightG: roundMoney(baseOffer.chargeableWeightKg * 1000),
      incrementKg: baseOffer.incrementKg,
      minimumWeightKg: baseOffer.minimumWeightKg,
      weightTier:
        baseOffer.weightTier ||
        baseOffer.minKg + "＜W≤" + baseOffer.maxKg + " kg",
      pricePerKg: baseOffer.pricePerKg,
      baseRegistrationFee: baseOffer.baseRegistrationFee,
      adjustments: adjustments,
      adjustmentTotal: adjustmentTotal,
      registrationFee: registrationFee,
      shippingCost: shippingCost,
      finalPriceUsd: roundQuoteUpToTenth(
        (input.cost + input.profit + shippingCost) / input.exchangeRate
      ),
      sourceRow: baseOffer.sourceRow,
    };
  }

  function getCountries() {
    var countries = {};
    CHANNELS.forEach(function (channel) {
      channel.rates.forEach(function (rate) {
        countries[rate.country] = true;
      });
    });
    return Object.keys(countries).sort(function (left, right) {
      return left.localeCompare(right, "zh-CN");
    });
  }

  function getChannelsForCountry(country) {
    var normalizedCountry = String(country || "").trim();
    return CHANNELS.filter(function (channel) {
      return (
        RULES.getRoutingDecision(channel.key, normalizedCountry).allowed &&
        channel.rates.some(function (rate) {
          return rate.country === normalizedCountry;
        })
      );
    }).map(function (channel) {
      return {
        key: channel.key,
        company: channel.company,
        name: channel.name,
        cargoType: channel.cargoType,
      };
    });
  }

  function getCountriesForChannel(channelKey) {
    var selectedChannel = CHANNELS.find(function (channel) {
      return channel.key === channelKey;
    });
    if (!selectedChannel) {
      return [];
    }
    var countries = {};
    selectedChannel.rates.forEach(function (rate) {
      if (RULES.getRoutingDecision(selectedChannel.key, rate.country).allowed) {
        countries[rate.country] = true;
      }
    });
    return Object.keys(countries).sort(function (left, right) {
      return left.localeCompare(right, "zh-CN");
    });
  }

  function calculateQuotes(input, selectedChannel) {
    var normalizedInput = {
      country: String(input.country || "").trim(),
      cost: requirePositiveNumber(input.cost, "商品成本", true),
      weightG: requirePositiveNumber(input.weightG, "商品重量", false),
      profit: requirePositiveNumber(input.profit, "利润", true),
      exchangeRate: requirePositiveNumber(input.exchangeRate, "汇率", false),
    };
    if (!normalizedInput.country) {
      throw new Error("请选择目的国家");
    }

    var offers = [];
    var unavailable = [];
    var actualWeightKg = normalizedInput.weightG / 1000;

    var channelsToCalculate = selectedChannel ? [selectedChannel] : CHANNELS;
    channelsToCalculate.forEach(function (channel) {
      var routing = RULES.getRoutingDecision(channel.key, normalizedInput.country);
      if (!routing.allowed) {
        unavailable.push({
          company: channel.company,
          channelName: channel.name,
          cargoType: channel.cargoType,
          reason: routing.reason,
        });
        return;
      }

      var countryRates = channel.rates.filter(function (rate) {
        return rate.country === normalizedInput.country;
      });
      if (!countryRates.length) {
        unavailable.push({
          company: channel.company,
          channelName: channel.name,
          cargoType: channel.cargoType,
          reason: "该国家未开通",
        });
        return;
      }

      var groups = groupRatesByZone(countryRates);
      if (
        normalizedInput.country === "澳大利亚" &&
        (Object.keys(groups).length > 1 || !Object.prototype.hasOwnProperty.call(groups, ""))
      ) {
        var averaged = calculateAustraliaAverage(groups, actualWeightKg);
        if (averaged.offer) {
          offers.push(
            applyBusinessAdjustments(
              channel,
              normalizedInput.country,
              averaged.offer,
              normalizedInput
            )
          );
        } else {
          unavailable.push({
            company: channel.company,
            channelName: channel.name,
            cargoType: channel.cargoType,
            reason: averaged.reason,
          });
        }
        return;
      }

      var channelOffers = [];
      Object.keys(groups).forEach(function (zone) {
        var baseOffer = calculateBaseOffer(groups[zone], actualWeightKg);
        if (!baseOffer) {
          return;
        }
        baseOffer.zone = zone;
        channelOffers.push(
          applyBusinessAdjustments(
            channel,
            normalizedInput.country,
            baseOffer,
            normalizedInput
          )
        );
      });

      if (channelOffers.length) {
        offers = offers.concat(channelOffers);
      } else {
        unavailable.push({
          company: channel.company,
          channelName: channel.name,
          cargoType: channel.cargoType,
          reason: "重量超出该渠道范围",
        });
      }
    });

    offers.sort(function (left, right) {
      return left.finalPriceUsd - right.finalPriceUsd || left.shippingCost - right.shippingCost;
    });

    return {
      countryName: normalizedInput.country,
      offers: offers,
      unavailable: unavailable,
      hasZones: offers.some(function (offer) {
        return Boolean(offer.zone) && !offer.isWeightedAverage;
      }),
    };
  }

  function calculateAllQuotes(input) {
    return calculateQuotes(input, null);
  }

  function calculateChannelQuote(input, channelKey) {
    var selectedChannel = CHANNELS.find(function (channel) {
      return channel.key === channelKey;
    });
    if (!selectedChannel) {
      throw new Error("请选择物流渠道");
    }
    return calculateQuotes(input, selectedChannel);
  }

  root.Pricing = {
    CHANNELS: CHANNELS,
    getCountries: getCountries,
    getChannelsForCountry: getChannelsForCountry,
    getCountriesForChannel: getCountriesForChannel,
    calculateAllQuotes: calculateAllQuotes,
    calculateChannelQuote: calculateChannelQuote,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
