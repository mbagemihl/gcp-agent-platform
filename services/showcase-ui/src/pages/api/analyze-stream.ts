import type { APIRoute } from 'astro';

async function fetchMetadataIdentityToken(audience: string): Promise<string | null> {
  if (!audience.startsWith('https://')) {
    return null;
  }
  try {
    const metadataUrl =
      `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(audience)}`;
    const res = await fetch(metadataUrl, {
      headers: { 'Metadata-Flavor': 'Google' },
      signal: AbortSignal.timeout(2500),
    });
    if (!res.ok) return null;
    return (await res.text()).trim();
  } catch {
    return null;
  }
}

export const POST: APIRoute = async ({ request }) => {
  const agentCoreBase = (process.env.AGENT_CORE_URL || 'http://localhost:8082').replace(/\/+$/, '');
  let bodyText: string;

  try {
    bodyText = await request.text();
  } catch {
    return new Response(JSON.stringify({ detail: 'Invalid request body' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const idToken = await fetchMetadataIdentityToken(agentCoreBase);
  if (idToken) {
    headers.Authorization = `Bearer ${idToken}`;
  }

  try {
    const upstream = await fetch(`${agentCoreBase}/api/analyze/stream`, {
      method: 'POST',
      headers,
      body: bodyText,
    });

    if (!upstream.ok || !upstream.body) {
      const errorText = await upstream.text().catch(() => 'Upstream error');
      return new Response(
        JSON.stringify({ detail: `agent-core returned ${upstream.status}: ${errorText}` }),
        { status: upstream.status || 502, headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response(upstream.body, {
      status: 200,
      headers: {
        'Content-Type': 'application/x-ndjson; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return new Response(
      JSON.stringify({ detail: `Could not reach agent-core at ${agentCoreBase}: ${message}` }),
      { status: 502, headers: { 'Content-Type': 'application/json' } }
    );
  }
};
