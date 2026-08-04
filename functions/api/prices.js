const CURRENT_PRICE_KEY = "current-prices";
const MAX_PAYLOAD_BYTES = 20 * 1024 * 1024;

function json(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function validateChannels(channels) {
  if (!Array.isArray(channels) || channels.length === 0) {
    return "价格数据中没有物流渠道";
  }
  const keys = new Set();
  let rateCount = 0;
  for (const channel of channels) {
    if (
      !channel ||
      typeof channel.key !== "string" ||
      !channel.key ||
      typeof channel.company !== "string" ||
      typeof channel.name !== "string" ||
      !Array.isArray(channel.rates)
    ) {
      return "价格数据中的渠道结构不完整";
    }
    if (keys.has(channel.key)) {
      return `发现重复渠道：${channel.key}`;
    }
    keys.add(channel.key);
    rateCount += channel.rates.length;
    for (const rate of channel.rates) {
      if (
        !rate ||
        typeof rate.country !== "string" ||
        !Number.isFinite(Number(rate.minKg)) ||
        !Number.isFinite(Number(rate.maxKg)) ||
        !Number.isFinite(Number(rate.pricePerKg)) ||
        !Number.isFinite(Number(rate.registrationFee))
      ) {
        return `渠道 ${channel.name} 中存在无法识别的费率`;
      }
    }
  }
  return rateCount > 0 ? "" : "价格数据中没有费率";
}

export async function onRequestGet(context) {
  if (!context.env.PRICE_DATA) {
    return json({ error: "Cloudflare KV 尚未绑定" }, 503);
  }
  const stored = await context.env.PRICE_DATA.get(CURRENT_PRICE_KEY);
  if (!stored) {
    return json({ error: "云端尚未发布价格，网页将使用内置价格" }, 404);
  }
  return new Response(stored, {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export async function onRequestPut(context) {
  if (!context.env.PRICE_DATA) {
    return json({ error: "云端价格存储尚未配置" }, 503);
  }
  const raw = await context.request.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_PAYLOAD_BYTES) {
    return json({ error: "价格数据超过20MB，已拒绝更新" }, 413);
  }
  let input;
  try {
    input = JSON.parse(raw);
  } catch (_error) {
    return json({ error: "价格数据不是有效的JSON" }, 400);
  }
  const validationError = validateChannels(input.channels);
  if (validationError) {
    return json({ error: validationError }, 400);
  }
  const now = new Date().toISOString();
  const stored = await context.env.PRICE_DATA.get(CURRENT_PRICE_KEY, "json");
  const currentVersionId = stored ? String(stored.activeVersionId || "") : "";
  const baseVersionId = String(input.baseVersionId || "");
  if (stored && baseVersionId !== currentVersionId) {
    return json(
      {
        error: "价格已被其他同事更新，请刷新网页后重新导入",
        currentVersionId,
      },
      409
    );
  }
  const versionId = crypto.randomUUID();
  const companies = Array.from(
    new Set(input.channels.map((channel) => channel.company))
  );
  const companyVersions = stored && stored.companyVersions
    ? { ...stored.companyVersions }
    : Object.fromEntries(
        companies.map((company) => [
          company,
          {
            sourceFile: "初始价格快照",
            updatedAt: now,
            versionId,
          },
        ])
      );
  const updatedCompany = String(input.updatedCompany || "");
  if (updatedCompany && companies.includes(updatedCompany)) {
    companyVersions[updatedCompany] = {
      sourceFile: String(input.sourceFile || "网页上传价格表"),
      updatedAt: now,
      versionId,
    };
  }
  const payload = {
    schemaVersion: 1,
    source: "cloud",
    updatedAt: now,
    activeVersionId: versionId,
    sourceFile: String(input.sourceFile || "网页上传价格表"),
    updatedCompany,
    companyVersions,
    channelCount: input.channels.length,
    rateCount: input.channels.reduce((sum, channel) => sum + channel.rates.length, 0),
    channels: input.channels,
  };
  await context.env.PRICE_DATA.put(CURRENT_PRICE_KEY, JSON.stringify(payload));
  return json({
    success: true,
    updatedAt: payload.updatedAt,
    activeVersionId: payload.activeVersionId,
    channelCount: payload.channelCount,
    rateCount: payload.rateCount,
  });
}

export async function onRequest(context) {
  if (context.request.method === "GET") {
    return onRequestGet(context);
  }
  if (context.request.method === "PUT") {
    return onRequestPut(context);
  }
  return json({ error: "请求方法不支持" }, 405);
}
