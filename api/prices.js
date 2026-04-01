// Vercel serverless function — proxies Yahoo Finance via yahoo-finance2
// Deployed at: /api/prices?symbols=SPY,QQQ,...
const yahooFinance = require('yahoo-finance2').default;

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');

  const { symbols } = req.query;
  if (!symbols) return res.status(400).json({ error: 'symbols param required' });

  try {
    const symList = symbols.split(',').map(s => s.trim()).filter(Boolean);
    const results = await Promise.all(
      symList.map(sym =>
        yahooFinance.quote(sym, {}, { validateResult: false }).catch(() => null)
      )
    );

    const validResults = results.filter(Boolean);
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
    return res.status(200).json({
      quoteResponse: { result: validResults, error: null }
    });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
