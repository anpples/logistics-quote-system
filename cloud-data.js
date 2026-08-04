(function (root) {
  "use strict";

  var fallbackChannels = root.LOGISTICS_CHANNELS || [];

  function validChannels(channels) {
    return (
      Array.isArray(channels) &&
      channels.length > 0 &&
      channels.every(function (channel) {
        return (
          channel &&
          typeof channel.key === "string" &&
          typeof channel.company === "string" &&
          Array.isArray(channel.rates)
        );
      })
    );
  }

  async function loadCurrentPrices() {
    var canUseApi = location.protocol === "http:" || location.protocol === "https:";
    if (!canUseApi) {
      root.LOGISTICS_PRICE_META = {
        source: "embedded",
        label: "本地内置价格",
      };
      return fallbackChannels;
    }

    try {
      var response = await fetch("/api/prices", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("价格接口暂不可用");
      }
      var payload = await response.json();
      if (!validChannels(payload.channels)) {
        throw new Error("共享价格数据结构异常");
      }
      root.LOGISTICS_CHANNELS = payload.channels;
      root.YUNTU_CHANNELS = payload.channels;
      root.LOGISTICS_PRICE_META = {
        source: payload.source || "shared",
        label:
          payload.source === "cloud"
            ? "云端共享价格"
            : "本机当前价格",
        updatedAt: payload.updatedAt || "",
        activeVersionId: payload.activeVersionId || "",
        sourceFile: payload.sourceFile || "",
        companyVersions: payload.companyVersions || {},
        channelCount: payload.channelCount || payload.channels.length,
        rateCount: payload.rateCount || 0,
      };
      return payload.channels;
    } catch (error) {
      root.LOGISTICS_CHANNELS = fallbackChannels;
      root.YUNTU_CHANNELS = fallbackChannels;
      root.LOGISTICS_PRICE_META = {
        source: "embedded-fallback",
        label: "内置价格（共享数据暂不可用）",
        warning: error.message,
      };
      return fallbackChannels;
    }
  }

  root.LOGISTICS_DATA_READY = loadCurrentPrices();
})(typeof globalThis !== "undefined" ? globalThis : this);
