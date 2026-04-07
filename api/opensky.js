export default async function handler(req, res) {
  const OPENSKY_URL =
    'https://opensky-network.org/api/states/all?lamin=40.598&lomin=-73.828&lamax=40.675&lomax=-73.738';

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 's-maxage=15, stale-while-revalidate=30');

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const upstream = await fetch(OPENSKY_URL, {
      headers: { 'User-Agent': 'groundcontrol-ai/1.0' },
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!upstream.ok) {
      console.error(`OpenSky error: HTTP ${upstream.status}`);
      return res.status(200).json({ states: [], error: `OpenSky returned ${upstream.status}` });
    }

    const data = await upstream.json();
    return res.status(200).json(data);
  } catch (err) {
    clearTimeout(timeout);
    const reason = err.name === 'AbortError' ? 'timeout after 8s' : err.message;
    console.error(`OpenSky fetch failed: ${reason}`);
    // Return empty states so the frontend degrades gracefully
    return res.status(200).json({ states: [], error: reason });
  }
}
