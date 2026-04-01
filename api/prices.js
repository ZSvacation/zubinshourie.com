// Vercel serverless — Stooq financial data, no API key required
module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');

  const { symbols } = req.query;
  if (!symbols) return res.status(400).json({ error: 'symbols param required' });

  const symList = symbols.split(',').map(s => s.trim()).filter(Boolean);

  // Map Yahoo Finance symbol format → Stooq symbol format (null = not available, skip)
  const STOOQ_MAP = {
    '^GSPC':   '^SPX',
    '^NDX':    '^NDX',
    'BTC-USD': 'BTCUSD',
    'ETH-USD': 'ETHUSD',
    'GC=F':    'XAUUSD',  // spot gold — close proxy for gold futures
    'CL=F':    'CL.F',    // WTI crude oil futures
    'BZ=F':    null,      // Brent crude — not on Stooq
    '^TNX':    null,      // 10Y yield — not on Stooq
    '^VIX':    null,      // VIX — not on Stooq
  };

  function toStooqSym(sym) {
    if (sym in STOOQ_MAP) return STOOQ_MAP[sym]; // null = skip
    // US-listed stocks and ETFs: append .US
    if (!sym.includes('.') && !sym.startsWith('^') && !sym.includes('=') && !sym.includes('-')) {
      return sym + '.US';
    }
    return sym;
  }

  async function fetchSymbol(sym) {
    const stooqSym = toStooqSym(sym);
    if (!stooqSym) return null; // explicitly skipped

    // JSON quote endpoint — close = last price, open = today's open (used as prev close proxy)
    const url = `https://stooq.com/q/l/?s=${encodeURIComponent(stooqSym)}&f=sd2t2ohlcvn&h&e=json`;
    try {
      const r = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
          'Accept': 'application/json',
        },
      });
      if (!r.ok) return null;

      // Stooq sometimes returns malformed JSON (e.g. "volume":, with empty value) — repair it
      const text = await r.text();
      const fixed = text.replace(/:,/g, ':null,').replace(/:}/g, ':null}');
      const data = JSON.parse(fixed);

      const s = data?.symbols?.[0];
      if (!s || !s.close || s.close === 'N/D') return null;

      const price     = parseFloat(s.close);
      const prevClose = parseFloat(s.open); // today's open ≈ yesterday's close
      if (isNaN(price) || isNaN(prevClose) || prevClose === 0 || price === 0) return null;

      const change    = price - prevClose;
      const changePct = (change / prevClose) * 100;

      return {
        symbol:                     sym,
        regularMarketPrice:         price,
        regularMarketChange:        change,
        regularMarketChangePercent: changePct,
        regularMarketPreviousClose: prevClose,
      };
    } catch {
      return null;
    }
  }

  // Fully sequential with 80ms gap — prevents Stooq rate-limiting even when
  // multiple API calls fire simultaneously from the browser
  async function fetchBatched(syms, delayMs = 80) {
    const results = [];
    for (const sym of syms) {
      results.push(await fetchSymbol(sym));
      await new Promise(r => setTimeout(r, delayMs));
    }
    return results;
  }

  try {
    const results      = await fetchBatched(symList);
    const validResults = results.filter(Boolean);
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
    return res.status(200).json({ quoteResponse: { result: validResults, error: null } });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
