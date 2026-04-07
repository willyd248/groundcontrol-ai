export default async function handler(req, res) {
  const OPENSKY_URL =
    'https://opensky-network.org/api/states/all?lamin=40.598&lomin=-73.828&lamax=40.675&lomax=-73.738';

  try {
    const upstream = await fetch(OPENSKY_URL, {
      headers: { 'User-Agent': 'groundcontrol-ai/1.0' },
    });

    if (!upstream.ok) {
      return res.status(upstream.status).json({ error: `OpenSky returned ${upstream.status}` });
    }

    const data = await upstream.json();

    res.setHeader('Cache-Control', 's-maxage=10, stale-while-revalidate=5');
    res.setHeader('Access-Control-Allow-Origin', '*');
    return res.status(200).json(data);
  } catch (err) {
    return res.status(502).json({ error: err.message });
  }
}
