(function (root) {
  "use strict";

  var MAX_ROWS = 500;
  var HEADER_NAMES = {
    sku: ["sku", "产品sku", "商品sku", "产品编号", "商品编号", "货号", "款号"],
    cost: ["成本", "商品成本", "产品成本", "成本价", "成本rmb", "商品成本rmb"],
    weight: [
      "计费重量", "商品重量", "产品重量", "重量",
      "计费重量g", "重量g", "计费重量克", "重量克",
      "计费重量kg", "重量kg", "计费重量千克", "重量千克",
      "计费重量公斤", "重量公斤",
    ],
  };

  function normalizeHeader(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[\s_\-（）()【】\[\]:：/\\.]/g, "");
  }

  function splitDelimitedLine(line, delimiter) {
    if (delimiter === "\t") {
      return line.split("\t");
    }
    var cells = [];
    var current = "";
    var inQuotes = false;
    for (var index = 0; index < line.length; index += 1) {
      var character = line[index];
      if (character === '"') {
        if (inQuotes && line[index + 1] === '"') {
          current += '"';
          index += 1;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (character === delimiter && !inQuotes) {
        cells.push(current);
        current = "";
      } else {
        current += character;
      }
    }
    cells.push(current);
    return cells;
  }

  function findHeaderIndex(cells, field) {
    var accepted = HEADER_NAMES[field];
    return cells.findIndex(function (cell) {
      return accepted.indexOf(normalizeHeader(cell)) !== -1;
    });
  }

  function detectWeightUnit(value) {
    var text = String(value || "").trim().toLowerCase();
    if (/kg|千克|公斤/.test(text)) {
      return "kg";
    }
    if (/g|克/.test(text)) {
      return "g";
    }
    return "kg";
  }

  function parseNumber(value, field, defaultWeightUnit) {
    var text = String(value || "")
      .trim()
      .replace(/[￥¥,，]/g, "");
    var multiplier = 1;
    if (field === "weight" && /(?:kg|千克|公斤)$/i.test(text)) {
      multiplier = 1000;
      text = text.replace(/(?:kg|千克|公斤)$/i, "").trim();
    } else if (field === "weight" && /(?:g|克)$/i.test(text)) {
      text = text.replace(/(?:g|克)$/i, "").trim();
    } else if (field === "weight" && defaultWeightUnit !== "g") {
      multiplier = 1000;
    }
    var number = Number(text);
    return Number.isFinite(number) ? number * multiplier : NaN;
  }

  function parseRows(rawText) {
    var text = String(rawText || "").replace(/^\uFEFF/, "").trim();
    if (!text) {
      return { rows: [], errors: ["请从 Excel/WPS 复制并粘贴 SKU、商品成本和计费重量三列。"] };
    }
    var lines = text.split(/\r?\n/).filter(function (line) {
      return line.trim() !== "";
    });
    var delimiter = text.indexOf("\t") !== -1 ? "\t" : ",";
    var firstCells = splitDelimitedLine(lines[0], delimiter);
    var indexes = {
      sku: findHeaderIndex(firstCells, "sku"),
      cost: findHeaderIndex(firstCells, "cost"),
      weight: findHeaderIndex(firstCells, "weight"),
    };
    var recognizedHeaders = [indexes.sku, indexes.cost, indexes.weight].filter(function (index) {
      return index !== -1;
    }).length;
    var hasHeader = recognizedHeaders > 0;
    if (hasHeader && recognizedHeaders < 3) {
      return {
        rows: [],
        errors: ["表头需要同时包含 SKU、商品成本和计费重量。"],
      };
    }
    if (!hasHeader) {
      indexes = { sku: 0, cost: 1, weight: 2 };
    }
    var weightUnit = hasHeader
      ? detectWeightUnit(firstCells[indexes.weight])
      : "kg";

    var dataLines = hasHeader ? lines.slice(1) : lines;
    var rows = [];
    var errors = [];
    var seenSkus = {};
    dataLines.slice(0, MAX_ROWS + 1).forEach(function (line, rowIndex) {
      var displayRow = rowIndex + (hasHeader ? 2 : 1);
      var cells = splitDelimitedLine(line, delimiter);
      var sku = String(cells[indexes.sku] || "").trim();
      var cost = parseNumber(cells[indexes.cost], "cost");
      var weightG = parseNumber(cells[indexes.weight], "weight", weightUnit);
      if (!sku) {
        errors.push("第 " + displayRow + " 行缺少 SKU。 ");
      } else if (seenSkus[sku]) {
        errors.push("第 " + displayRow + " 行 SKU“" + sku + "”重复。 ");
      }
      if (!Number.isFinite(cost) || cost < 0) {
        errors.push("第 " + displayRow + " 行商品成本无效。 ");
      }
      if (!Number.isFinite(weightG) || weightG <= 0) {
        errors.push("第 " + displayRow + " 行计费重量必须大于 0 千克。 ");
      }
      if (
        sku &&
        !seenSkus[sku] &&
        Number.isFinite(cost) &&
        cost >= 0 &&
        Number.isFinite(weightG) &&
        weightG > 0
      ) {
        seenSkus[sku] = true;
        rows.push({ sku: sku, cost: cost, weightG: weightG });
      }
    });
    if (dataLines.length > MAX_ROWS) {
      errors.push("一次最多支持 " + MAX_ROWS + " 个 SKU，请分批报价。 ");
    }
    if (!rows.length && !errors.length) {
      errors.push("没有识别到可报价的商品数据。 ");
    }
    return {
      rows: rows,
      errors: errors.map(function (message) { return message.trim(); }),
      hasHeader: hasHeader,
      delimiter: delimiter,
      weightUnit: weightUnit,
    };
  }

  function formatPrice(value) {
    return Number(value).toFixed(1);
  }

  function calculateBatch(options) {
    var pricing = root.Pricing;
    var rows = options.rows || [];
    var countries = options.countries || [];
    var channel = pricing.CHANNELS.find(function (item) {
      return item.key === options.channelKey;
    });
    if (!rows.length) {
      throw new Error("请先粘贴有效的商品数据");
    }
    if (!channel) {
      throw new Error("请选择物流渠道");
    }
    if (!countries.length) {
      throw new Error("请至少勾选一个目的国家");
    }

    var unavailableCount = 0;
    var zonedCount = 0;
    var resultRows = rows.map(function (row) {
      var cells = {};
      countries.forEach(function (country) {
        var quote = pricing.calculateChannelQuote(
          {
            country: country,
            cost: row.cost,
            weightG: row.weightG,
            profit: options.profit,
            exchangeRate: options.exchangeRate,
          },
          channel.key
        );
        if (!quote.offers.length) {
          unavailableCount += 1;
          cells[country] = {
            status: "unavailable",
            display: "不可用",
            reason: quote.unavailable.length
              ? quote.unavailable[0].reason
              : "当前重量没有可用报价",
          };
          return;
        }
        var prices = quote.offers.map(function (offer) {
          return offer.finalPriceUsd;
        }).sort(function (left, right) { return left - right; });
        var minimum = prices[0];
        var maximum = prices[prices.length - 1];
        if (Math.abs(maximum - minimum) > 1e-9) {
          zonedCount += 1;
          cells[country] = {
            status: "zoned",
            display: formatPrice(minimum) + "–" + formatPrice(maximum),
            minimumUsd: minimum,
            maximumUsd: maximum,
            offers: quote.offers,
          };
          return;
        }
        cells[country] = {
          status: "quoted",
          display: formatPrice(minimum),
          priceUsd: minimum,
          shippingCost: quote.offers[0].shippingCost,
          offer: quote.offers[0],
        };
      });
      return {
        sku: row.sku,
        cost: row.cost,
        weightG: row.weightG,
        cells: cells,
      };
    });

    return {
      channelKey: channel.key,
      channelName: channel.name,
      company: channel.company,
      cargoType: channel.cargoType,
      profit: Number(options.profit),
      exchangeRate: Number(options.exchangeRate),
      countries: countries.slice(),
      rows: resultRows,
      quoteCount: rows.length * countries.length,
      unavailableCount: unavailableCount,
      zonedCount: zonedCount,
    };
  }

  function resultToRows(result) {
    var rows = [["SKU", "商品成本(RMB)", "计费重量(kg)"].concat(
      result.countries.map(function (country) { return country + "(USD)"; })
    )];
    result.rows.forEach(function (row) {
      rows.push([row.sku, row.cost, row.weightG / 1000].concat(
        result.countries.map(function (country) {
          return row.cells[country].display;
        })
      ));
    });
    return rows;
  }

  function toTsv(result) {
    return resultToRows(result).map(function (row) {
      return row.join("\t");
    }).join("\n");
  }

  function escapeCsvCell(value) {
    var text = String(value);
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  function toCsv(result) {
    return "\uFEFF" + resultToRows(result).map(function (row) {
      return row.map(escapeCsvCell).join(",");
    }).join("\r\n");
  }

  root.BatchPricing = {
    MAX_ROWS: MAX_ROWS,
    parseRows: parseRows,
    calculateBatch: calculateBatch,
    toTsv: toTsv,
    toCsv: toCsv,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
