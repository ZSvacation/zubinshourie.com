// Vercel serverless — Yahoo Finance chart API, no external dependencies
module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');

  const { symbols } = req.query;
  if (!symbols) return res.status(400).json({ error: 'symbols param required' });

  const symList = symbols.split(',').map(s => s.trim()).filter(Boolean);

  async function fetchSymbol(sym) {
    const url = `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=1d&range=1d`;
    const r = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
      },
    });
    if (!r.ok) return null;
    const data = await r.json();
    const result = data?.chart?.result?.[0];
    if (!result) return null;

    const meta      = result.meta;
    const price     = meta.regularMarketPrice ?? meta.price;
    const prevClose = meta.chartPreviousClose ?? meta.previousClose ?? meta.regularMarketPreviousClose;
    if (price == null || prevClose == null) return null;

    const change    = price - prevClose;
    const changePct = (change / prevClose) * 100;

    return {
      symbol:                       sym,
      regularMarketPrice:           price,
      regularMarketChange:          change,
      regularMarketChangePercent:   changePct,
      regularMarketPreviousClose:   prevClose,
    };
  }

  try {
    const results      = await Promise.all(symList.map(fetchSymbol));
    const validResults = results.filter(Boolean);
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
    return res.status(200).json({ quoteResponse: { result: validResults, error: null } });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
