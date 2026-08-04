const CURRENT_PRICE_KEY = "current-prices";

export async function onRequestGet(context) {
  const storageReady = Boolean(context.env.PRICE_DATA);
  const hasPublishedPrices = storageReady
    ? Boolean(await context.env.PRICE_DATA.get(CURRENT_PRICE_KEY))
    : false;
  return Response.json(
    {
      ready: true,
      mode: "cloud",
      supportsExcelImport: storageReady,
      supportsVersionHistory: false,
      storageReady,
      hasPublishedPrices,
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}

export async function onRequest(context) {
  if (context.request.method !== "GET") {
    return Response.json({ error: "请求方法不支持" }, { status: 405 });
  }
  return onRequestGet(context);
}
