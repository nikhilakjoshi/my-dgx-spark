# Future: remote access (off-WiFi dictation) + multi-user notes

Parked. Today the dictation only works when the Mac is on the same WiFi as the Spark (RFC1918 LAN). This doc captures the path to enable off-network use.

## Scope assumption

Most colleagues who'd want this also have their own DGX Sparks. So the primary use case here is "me, dictating from anywhere on my laptops, talking to my Spark." Multi-user sharing of one Spark is a secondary concern — captured at the bottom in case it becomes relevant.

## Recommended path: Tailscale (zero-trust mesh VPN)

Free for personal use. Every device joins a private "tailnet" and gets a stable hostname. No public ports, no router config, no DNS.

### Setup sketch

Spark:
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# accept the auth URL on first run
# enable MagicDNS in the Tailscale admin console
```

Each Mac:
```bash
brew install --cask tailscale
# launch, sign in
```

Client `.env` flips from LAN IP to tailnet name:
```
SPARK_URL=http://spark-9970:8000/transcribe
```

### Why it fits

- No public ports — attack surface stays zero
- NAT traversal is automatic
- Works through Zscaler in most cases (Tailscale itself is a userspace WireGuard with QUIC fallback)
- Adding people later = invite via admin console; ACLs scope who reaches what
- Bandwidth is peer-to-peer when possible (fast); DERP relay fallback when not

### Trade-offs

- Each client must install Tailscale (one-time)
- Free tier is generous but capped (~100 devices, plenty)
- Tailscale company sits in your trust chain (auth + coordination only; not in the data path)

## Alternative: Cloudflare Tunnel + Cloudflare Access

For colleagues who can't install a VPN client. `cloudflared` on Spark dials out to Cloudflare; you get `dictate.yourdomain.com` gated behind Cloudflare Access (email OTP / SSO).

- Pros: nothing to install on clients; browser login
- Cons: adds 50-100 ms (CF edge round trip); needs a domain you own; CF is in the path

## Anti-pattern: forward 8000 on the home router

Exposes `whisper-server` to the public internet. It has no auth, no rate limit, no TLS. Do not do this.

## Multi-user on one Spark (lower priority)

Only relevant if someone without their own Spark wants to use yours. Today's stack is single-tenant by design. To make it safe for shared use:

```
Mac client
  -> Tailscale or CF Tunnel
    -> Caddy / FastAPI shim on Spark :8443
       - auth: X-API-Key per user, or trust CF Access JWT
       - rate-limit per key (e.g. 60/min)
       - structured access log (JSON to journald)
       - proxy to whisper-server :8000 (unchanged)
```

What to add:
- Reverse proxy with auth (Caddy v2 ~20 lines, or FastAPI shim if you want per-user dashboards)
- Per-key access logs (request count, latency, byte size) — do NOT log audio content or transcripts
- Rate limiting (one colleague should not be able to saturate the GPU)
- TLS (Caddy auto-issues; or terminate at Tailscale/CF)
- Eviction story when a key leaks (rotate, revoke)

## Open questions to settle when we revisit

- Tailscale alone, or Tailscale + Cloudflare Tunnel both?
- MagicDNS hostname for Spark — keep `spark-9970` or rename?
- For multi-user path: API keys vs CF Access JWT?
- Log retention — keep in journald with `--vacuum-time=30d`?
- Do we ever want to log transcripts for debugging? Probably no; opt-in only.

## When this work makes sense

- Right now if I'm traveling and want dictation on my laptop -> set up Tailscale first.
- Later, if specific colleagues without their own Spark want access -> add the auth/proxy layer.
- Don't build the multi-user stack speculatively. Single-tenant Tailscale is enough for the personal use case.
