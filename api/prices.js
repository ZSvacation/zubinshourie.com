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
    '^VIX':    '__VIX__', // handled by fetchVIX() via CBOE
  };

  function toStooqSym(sym) {
    if (sym in STOOQ_MAP) return STOOQ_MAP[sym]; // null = skip
    // US-listed stocks and ETFs: append .US
    if (!sym.includes('.') && !sym.startsWith('^') && !sym.includes('=') && !sym.includes('-')) {
      return sym + '.US';
    }
    return sym;
  }

  // VIX: tries Stooq, then CBOE quotes, then CBOE historical chart
  async function fetchVIX() {
    const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36';

    // 1. Stooq — ^VIX may work now that fetches are sequential (prior failure was under rate-limiting)
    try {
      const r = await fetch('https://stooq.com/q/l/?s=%5EVIX&f=sd2t2ohlcvn&h&e=json', {
        headers: { 'User-Agent': UA, 'Accept': 'application/json' },
      });
      if (r.ok) {
        const text  = await r.text();
        const fixed = text.replace(/:,/g, ':null,').replace(/:}/g, ':null}');
        const data  = JSON.parse(fixed);
        const s     = data?.symbols?.[0];
        if (s && s.close && s.close !== 'N/D') {
          const price     = parseFloat(s.close);
          const prevClose = parseFloat(s.open);
          if (!isNaN(price) && !isNaN(prevClose) && prevClose > 0 && price > 0) {
            const change    = price - prevClose;
            const changePct = (change / prevClose) * 100;
            return { symbol: '^VIX', regularMarketPrice: price, regularMarketChange: change, regularMarketChangePercent: changePct, regularMarketPreviousClose: prevClose };
          }
        }
      }
    } catch {}

    // 2. CBOE delayed quotes endpoint — _VIX is CBOE's own underscore format
    try {
      const r = await fetch('https://cdn.cboe.com/api/global/delayed_quotes/quotes/_VIX.json', {
        headers: { 'User-Agent': UA, 'Accept': 'application/json' },
      });
      if (r.ok) {
        const d     = await r.json();
        const data  = d?.data;
        // Handle multiple possible field names across API versions
        const price     = parseFloat(data?.last_trade_price ?? data?.close ?? data?.price);
        const prevClose = parseFloat(data?.close ?? data?.prev_close ?? data?.previous_close);
        const change    = parseFloat(data?.change);
        const changePct = parseFloat(data?.change_percent ?? data?.change_pct);
        if (!isNaN(price) && price > 0) {
          const c  = !isNaN(change) ? change : (!isNaN(prevClose) ? price - prevClose : 0);
          const cp = !isNaN(changePct) ? changePct : (prevClose > 0 ? (c / prevClose) * 100 : 0);
          return { symbol: '^VIX', regularMarketPrice: price, regularMarketChange: c, regularMarketChangePercent: cp, regularMarketPreviousClose: isNaN(prevClose) ? price - c : prevClose };
        }
      }
    } catch {}

    // 3. CBOE historical chart — last two closes give price + prev close
    try {
      const r = await fetch('https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/_VIX.json', {
        headers: { 'User-Agent': UA, 'Accept': 'application/json' },
      });
      if (r.ok) {
        const d      = await r.json();
        const closes = d?.data?.close ?? d?.data?.chart?.close ?? d?.data?.series?.close;
        if (Array.isArray(closes) && closes.length >= 2) {
          const price     = parseFloat(closes[closes.length - 1]);
          const prevClose = parseFloat(closes[closes.length - 2]);
          if (!isNaN(price) && !isNaN(prevClose) && prevClose > 0 && price > 0) {
            const change    = price - prevClose;
            const changePct = (change / prevClose) * 100;
            return { symbol: '^VIX', regularMarketPrice: price, regularMarketChange: change, regularMarketChangePercent: changePct, regularMarketPreviousClose: prevClose };
          }
        }
      }
    } catch {}

    return null;
  }

  async function fetchSymbol(sym) {
    // VIX: route to CBOE instead of Stooq
    if (sym === '^VIX') return fetchVIX();

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
