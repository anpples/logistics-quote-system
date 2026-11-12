import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

function rate(country, pricePerKg, registrationFee, zone = "") {
  return {
    country, zone, minKg: 0, maxKg: 1, incrementKg: 0,
    minimumWeightKg: 0, pricePerKg, registrationFee,
    transitTime: "7-12", sourceRow: 1,
  };
}

const channels = [
  { key: "yt_chc_general", company: "云途CHC", name: "CHC普货", cargoType: "普货",
    rates: [rate("法国", 66, 21), rate("罗马尼亚", 50, 20)] },
  { key: "economy_general", company: "云途", name: "云途特惠普货", cargoType: "普货",
    rates: [rate("法国", 66, 21), rate("罗马尼亚", 50, 20)] },
  { key: "wb_special_a", company: "万邦物流", name: "万邦特敏A", cargoType: "特敏A",
    rates: [rate("英国", 58, 16)] },
  { key: "wb_registered_general", company: "万邦物流", name: "万邦专线普货", cargoType: "普货",
    rates: [rate("澳大利亚", 10, 1, "1区"), rate("澳大利亚", 20, 2, "2区"),
      rate("澳大利亚", 30, 3, "3区"), rate("澳大利亚", 40, 4, "4区")] },
  { key: "wb_us_zip_general", company: "万邦物流", name: "万邦美国精选普货", cargoType: "普货",
    rates: [rate("美国", 51, 21)] },
  { key: "wb_japan_test", company: "万邦物流", name: "万邦日本首续重", cargoType: "普货",
    rates: [
      { ...rate("日本", 0, 0), maxKg: 2, incrementKg: 0.5,
        minimumWeightKg: 0.5, billingModel: "first_half_kg",
        firstWeightFee: 29, continuationFee: 8 },
      { ...rate("日本", 0, 0), minKg: 2, maxKg: 10, incrementKg: 0.5,
        minimumWeightKg: 0.5, billingModel: "first_half_kg",
        firstWeightFee: 29, continuationFee: 9 },
    ] },
];

const context = { LOGISTICS_CHANNELS: channels };
vm.createContext(context);
vm.runInContext(fs.readFileSync("business-rules.js", "utf8"), context);
vm.runInContext(fs.readFileSync("pricing.js", "utf8"), context);
const quote = (key, country, weightG) =>
  context.Pricing.calculateChannelQuote({
    country, weightG, cost: 0, profit: 0, exchangeRate: 6.6,
  }, key).offers[0];

const franceChc = quote("yt_chc_general", "法国", 400);
assert.equal(franceChc.shippingCost, 56.76);
assert.equal(franceChc.adjustments.length, 2);
assert.equal(franceChc.adjustments[0].amount, 4.68);
assert.equal(franceChc.adjustments[1].amount, 4.68);
assert.equal(quote("economy_general", "法国", 400).shippingCost, 86.4);
assert.equal(quote("yt_chc_general", "罗马尼亚", 400).shippingCost, 49.36);
assert.equal(quote("economy_general", "罗马尼亚", 400).shippingCost, 79);
assert.equal(quote("yt_chc_general", "法国", 330).shippingCost, 51.32);
assert.equal(quote("yt_chc_general", "法国", 430).shippingCost, 59.09);
assert.equal(quote("yt_chc_general", "法国", 1000).adjustmentTotal, 16.38);
assert.equal(context.Pricing.calculateChannelQuote({
  country: "法国", weightG: 330, cost: 39, profit: 20, exchangeRate: 6.6,
}, "yt_chc_general").offers[0].finalPriceUsd, 16.8);
assert.equal(context.Pricing.calculateChannelQuote({
  country: "法国", weightG: 430, cost: 49, profit: 20, exchangeRate: 6.6,
}, "yt_chc_general").offers[0].finalPriceUsd, 19.5);
assert.equal(quote("wb_special_a", "英国", 400).shippingCost, 41.2);
const australia = quote("wb_registered_general", "澳大利亚", 400);
assert.equal(australia.shippingCost, 11);
assert.equal(australia.pricePerKg, 22);
assert.equal(australia.baseRegistrationFee, 2.2);
assert.equal(quote("wb_japan_test", "日本", 480).shippingCost, 29);
assert.equal(quote("wb_japan_test", "日本", 570).shippingCost, 37);
assert.equal(quote("wb_japan_test", "日本", 2100).shippingCost, 65);
assert.match(quote("wb_us_zip_general", "美国", 400).notices[0].text, /邮编/);
console.log("CHC税费、罗马尼亚、英国、澳洲加权、日本首续重、精选邮编提示均通过");
