"""Hardened outbound fetch for **caller-supplied** URLs (the "Verify Anywhere" surface).

`POST /api/check` lets an anonymous buyer paste a marketplace listing or image link and have
the server fetch it. That is a classic Server-Side Request Forgery (SSRF) surface: without
controls, `http://169.254.169.254/…` reads cloud metadata, `http://10.0.0.1/…` probes the
internal network, and `file://…`/`gopher://…` reach non-HTTP services. This module is the
single choke point that makes fetching an untrusted URL safe(r), and it is deliberately NOT
`app.generation._fetch_bytes` — that helper is for our own trusted B2 presigns and follows
redirects with no IP validation.

Controls applied to every hop:
  * scheme allow-list — http/https only (no file/ftp/gopher/data);
  * port allow-list — 80/443/scheme-default only (odd ports are a hallmark of internal probes);
  * DNS resolution up front, with **every** resolved A/AAAA address checked against a block-list
    of private / loopback / link-local (incl. the 169.254.169.254 metadata address) / CGNAT /
    reserved / multicast / unspecified ranges, for IPv4 and IPv4-mapped IPv6 alike;
  * redirects followed **manually**, capped, with the destination re-validated on every hop
    (a 302 to `http://127.0.0.1` is the oldest SSRF-via-redirect trick);
  * a streamed **size cap** and a short **timeout**, so a slow-loris or a multi-GB body can't
    tie up the worker.

**Residual limit, stated honestly** (this project does not overclaim its guarantees): a
determined DNS-rebinding attacker could return a public IP to the validation `getaddrinfo`
here and a private IP to httpx's own resolution microseconds later. The window is narrowed by
resolving immediately before the request and by the short timeout, but it is not zero. Fully
closing it means pinning the socket to the validated IP while preserving SNI/cert validation
(a custom transport); that is the documented next step, not something to pretend is already
done. The load-bearing controls above stop the overwhelming majority of SSRF, including all
the static-target attacks (metadata, literal private IPs, non-HTTP schemes).
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_PORTS = {80, 443, None}
_MAX_REDIRECTS = 2
_MAX_HTML_BYTES = 2 * 1024 * 1024  # only ever parse the HEAD-ish top of a listing page


class FetchError(Exception):
    """A caller-safe reason a URL could not be fetched. The message is shown to the user, so
    it must never leak internal detail beyond what the caller already supplied."""


@dataclass
class Fetched:
    content: bytes
    content_type: str
    final_url: str

    @property
    def is_image(self) -> bool:
        return self.content_type.split(";", 1)[0].strip().lower().startswith("image/")

    @property
    def is_html(self) -> bool:
        return self.content_type.split(";", 1)[0].strip().lower() in {
            "text/html",
            "application/xhtml+xml",
        }


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for any address a public fetch must never reach."""
    # IPv4-mapped IPv6 (::ffff:10.0.0.1) must be judged on the embedded v4 address.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local       # 169.254.0.0/16 — the cloud-metadata range
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True
    # CGNAT 100.64.0.0/10 is not flagged is_private by the stdlib but is just as off-limits.
    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"):
        return True
    return False


def _validate_host(host: str) -> None:
    """Resolve `host` and raise FetchError unless every resolved address is public.

    Validating *all* returned addresses (not just the first) matters: a name that resolves to
    one public and one private address must be rejected, or the private one is reachable.
    """
    if not host:
        raise FetchError("The link has no host.")
    # A bare IP literal in the URL is validated directly (no DNS needed).
    try:
        _reject_if_blocked(ipaddress.ip_address(host))
        return
    except ValueError:
        pass  # not a literal IP — resolve it below

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise FetchError(f"Couldn't resolve “{host}”.") from None
    if not infos:
        raise FetchError(f"Couldn't resolve “{host}”.")
    for info in infos:
        _reject_if_blocked(ipaddress.ip_address(info[4][0]))


def _reject_if_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if _ip_is_blocked(ip):
        raise FetchError("That link points to a private or internal address and can't be fetched.")


def _validate_url(url: str) -> tuple[str, str]:
    """Return (scheme, host) after checking scheme, port and host reachability."""
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise FetchError("Only http and https links can be checked.")
    if parts.port is not None and parts.port not in _ALLOWED_PORTS:
        raise FetchError("Only standard web ports (80/443) can be checked.")
    host = parts.hostname or ""
    _validate_host(host)
    return scheme, host


def fetch_url(url: str, *, timeout: int, max_bytes: int) -> Fetched:
    """Fetch a caller-supplied URL through every SSRF control, following redirects manually.

    Returns the raw body (capped at `max_bytes`) plus its content type and the final URL. The
    caller decides what to do with it — an image goes to the verifier, an HTML page goes to
    `extract_image_urls`.
    """
    current = url
    with httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        headers={"User-Agent": "OriginShot-VerifyAnywhere/1.0 (+https://originshot.vercel.app)"},
    ) as client:
        for _hop in range(_MAX_REDIRECTS + 1):
            _validate_url(current)  # re-validated on EVERY hop, including post-redirect
            try:
                with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("The link redirected without a destination.")
                        current = urljoin(current, location)
                        continue
                    if resp.status_code >= 400:
                        raise FetchError(f"The link returned HTTP {resp.status_code}.")
                    content_type = resp.headers.get("content-type", "application/octet-stream")
                    body = bytearray()
                    for chunk in resp.iter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise FetchError("That file is too large to check.")
                    return Fetched(bytes(body), content_type, str(resp.url))
            except httpx.HTTPError as exc:
                raise FetchError(f"Couldn't reach that link ({type(exc).__name__}).") from exc
    raise FetchError("The link redirected too many times.")


class _ImageCollector(HTMLParser):
    """Pull candidate product-image URLs out of a listing page: og:image first (marketplaces
    set it to the primary photo), then the first few <img src>. Order is preserved and later
    de-duplicated so og:image is tried first."""

    def __init__(self) -> None:
        super().__init__()
        self.og_images: list[str] = []
        self.img_srcs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("property", "").lower() in {"og:image", "og:image:url"}:
            if a.get("content"):
                self.og_images.append(a["content"])
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            if src and not src.startswith("data:"):
                self.img_srcs.append(src)


def extract_image_urls(html: bytes, base_url: str, limit: int) -> list[str]:
    """Absolute, de-duplicated candidate image URLs from a listing page, og:image first."""
    parser = _ImageCollector()
    try:
        parser.feed(html[:_MAX_HTML_BYTES].decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 — a malformed page yields no candidates, never a crash
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in [*parser.og_images, *parser.img_srcs]:
        absolute = urljoin(base_url, raw.strip())
        if absolute in seen:
            continue
        seen.add(absolute)
        # Cheap pre-filter: only keep links whose scheme is web. Full validation happens when
        # each is actually fetched, so a poisoned src can't smuggle a private target through.
        if urlsplit(absolute).scheme in _ALLOWED_SCHEMES:
            out.append(absolute)
        if len(out) >= limit:
            break
    return out
