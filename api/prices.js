// Vercel serverless — Stooq financial data, no API key required
module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');

  const { symbols } = req.query;
  if (!symbols) return res.status(400).json({ error: 'symbols param required' });

  const symList = symbols.split(',').map(s => s.trim()).filter(Boolean);

  // Map Yahoo Finance symbol format → Stooq symbol format
  const STOOQ_MAP = {
    '^GSPC':   '^SPX',
    '^NDX':    '^NDX',
    'BTC-USD': 'BTC.V.USD',
    'ETH-USD': 'ETH.V.USD',
    'GC=F':    'GC.F',
    'CL=F':    'CL.F',
    'BZ=F':    'BZ.F',
    '^TNX':    'TNX.B',
    '^VIX':    '^VIX',
  };

  function toStooqSym(sym) {
    if (STOOQ_MAP[sym]) return STOOQ_MAP[sym];
    // US-listed stocks and ETFs: append .US
    if (!sym.includes('.') && !sym.startsWith('^') && !sym.includes('=') && !sym.includes('-')) {
      return sym + '.US';
    }
    return sym;
  }

  async function fetchSymbol(sym) {
    const stooqSym = toStooqSym(sym);
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
      const data = await r.json();
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

  try {
    const results      = await Promise.all(symList.map(fetchSymbol));
    const validResults = results.filter(Boolean);
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
    return res.status(200).json({ quoteResponse: { result: validResults, error: null } });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
