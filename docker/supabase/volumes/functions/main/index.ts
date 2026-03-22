// Placeholder edge function to prevent the supabase-edge-functions container
// from crashing on startup. NoobBook does not use Supabase Edge Functions.
Deno.serve(() => new Response("ok"));
