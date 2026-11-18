"""Responsible, same-origin web crawler used by WEBSPIDER."""
from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "WEBSPIDER/0.2 (+https://github.com/annasb-oss)"
MAX_RESPONSE_BYTES = 2_000_000
REQUEST_TIMEOUT = 12.0


class CrawlError(ValueError):
    pass


def normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrawlError("Informe uma URL pública iniciada por http:// ou https://.")
    if parsed.username or parsed.password:
        raise CrawlError("URLs com credenciais não são aceitas.")
    if parsed.port and not (1 <= parsed.port <= 65535):
        raise CrawlError("Porta inválida.")
    clean = parsed._replace(fragment="", path=parsed.path or "/")
    return clean.geturl()


async def ensure_public_host(url: str) -> None:
    host = urlparse(url).hostname
    if not host:
        raise CrawlError("Host inválido.")
    try:
        ip = ipaddress.ip_address(host)
        addresses = [ip]
    except ValueError:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo, host, None, type=socket.SOCK_STREAM
            )
            addresses = [ipaddress.ip_address(record[4][0]) for record in records]
        except (OSError, ValueError):
            raise CrawlError("Não foi possível resolver o domínio informado.")
    if not addresses or any(not address.is_global for address in addresses):
        raise CrawlError("Por segurança, o WEBSPIDER só acessa hosts com IP público.")


def same_origin(first: str, second: str) -> bool:
    a, b = urlparse(first), urlparse(second)
    return (a.scheme, a.hostname, a.port or (443 if a.scheme == "https" else 80)) == (
        b.scheme, b.hostname, b.port or (443 if b.scheme == "https" else 80)
    )


async def safe_get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """Fetch one same-origin URL while enforcing a hard response-body limit."""
    current = url
    for _ in range(6):
        await ensure_public_host(current)
        async with client.stream("GET", current, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    return httpx.Response(
                        response.status_code, headers=response.headers,
                        request=response.request, content=b"",
                    )
                next_url = normalize_url(urljoin(current, location))
                if not same_origin(url, next_url):
                    raise CrawlError("Redirecionamento para outro domínio bloqueado.")
                current = next_url
                continue

            body = bytearray()
            async for chunk in response.aiter_bytes():
                remaining = MAX_RESPONSE_BYTES + 1 - len(body)
                if remaining <= 0:
                    break
                body.extend(chunk[:remaining])
                if len(body) > MAX_RESPONSE_BYTES:
                    break
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=bytes(body[:MAX_RESPONSE_BYTES]),
                request=response.request,
            )
    raise CrawlError("Muitos redirecionamentos.")


@dataclass
class CrawlJob:
    id: str
    start_url: str
    max_pages: int
    max_depth: int
    status: str = "queued"
    discovered: int = 1
    visited: int = 0
    analyzed: int = 0
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    events: list[dict] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)
    error: str | None = None

    def log(self, message: str, level: str = "info") -> None:
        self.events.append({"time": time.time(), "message": message, "level": level})
        self.events = self.events[-250:]

    def snapshot(self) -> dict:
        elapsed_end = self.finished_at or time.monotonic()
        return {
            "id": self.id, "start_url": self.start_url, "status": self.status,
            "discovered": self.discovered, "visited": self.visited,
            "analyzed": self.analyzed, "elapsed": round(elapsed_end - self.started_at, 1),
            "events": self.events, "pages": self.pages, "error": self.error,
        }


async def run_crawl(job: CrawlJob, jobs: dict[str, CrawlJob]) -> None:
    queue = deque([(job.start_url, 0)])
    seen = {job.start_url}
    robots = RobotFileParser()
    parsed_start = urlparse(job.start_url)
    robots_url = f"{parsed_start.scheme}://{parsed_start.netloc}/robots.txt"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    job.status = "running"
    job.log(f"Exploração iniciada em {job.start_url}")

    try:
        await ensure_public_host(job.start_url)
        async with httpx.AsyncClient(
            headers=headers, timeout=REQUEST_TIMEOUT, limits=httpx.Limits(max_connections=2)
        ) as client:
            try:
                robots_response = await safe_get(client, robots_url)
            except (httpx.HTTPError, CrawlError) as exc:
                raise CrawlError(
                    f"Não foi possível verificar robots.txt; a exploração foi interrompida por segurança: {exc}"
                ) from exc

            if robots_response.status_code == 200:
                robots.parse(robots_response.text.splitlines())
                job.log("Diretivas robots.txt carregadas.")
            elif 400 <= robots_response.status_code < 500 and robots_response.status_code not in {401, 403, 429}:
                robots.parse([])
                job.log(
                    f"robots.txt respondeu HTTP {robots_response.status_code}; nenhuma regra publicada.",
                    "warning",
                )
            else:
                raise CrawlError(
                    f"robots.txt respondeu HTTP {robots_response.status_code}; exploração bloqueada por segurança."
                )

            while queue and job.visited < job.max_pages:
                url, depth = queue.popleft()
                if not robots.can_fetch(USER_AGENT, url):
                    job.log(f"Bloqueada por robots.txt: {url}", "warning")
                    continue
                job.visited += 1
                try:
                    response = await safe_get(client, url)
                    if response.status_code != 200:
                        job.log(f"HTTP {response.status_code}: {url}", "warning")
                        await asyncio.sleep(1.0)
                        continue
                    content_type = response.headers.get("content-type", "").lower()
                    if "text/html" not in content_type:
                        job.log(f"Conteúdo ignorado (não HTML): {url}", "warning")
                        await asyncio.sleep(1.0)
                        continue
                    body = response.content[:MAX_RESPONSE_BYTES]
                    soup = BeautifulSoup(body, "html.parser")
                    for element in soup(["script", "style", "noscript", "svg"]):
                        element.decompose()
                    title = soup.title.get_text(" ", strip=True) if soup.title else "(sem título)"
                    description_tag = soup.find("meta", attrs={"name": "description"})
                    description = description_tag.get("content", "").strip() if description_tag else ""
                    text_content = " ".join(soup.get_text(" ", strip=True).split())
                    links = set()
                    if depth < job.max_depth:
                        for anchor in soup.find_all("a", href=True):
                            try:
                                target = normalize_url(urljoin(url, anchor["href"]))
                            except (CrawlError, ValueError):
                                continue
                            if same_origin(job.start_url, target) and target not in seen:
                                seen.add(target)
                                links.add(target)
                    job.discovered += len(links)
                    queue.extend((link, depth + 1) for link in sorted(links))
                    job.analyzed += 1
                    security_issues = []
                    response_headers = {key.lower(): value for key, value in response.headers.items()}
                    if urlparse(url).scheme != "https":
                        security_issues.append({"severity": "high", "code": "HTTPS_MISSING", "title": "Página sem HTTPS", "detail": "A URL analisada usa HTTP; dados em trânsito podem ficar expostos."})
                    if "content-security-policy" not in response_headers:
                        security_issues.append({"severity": "medium", "code": "CSP_MISSING", "title": "CSP não observada", "detail": "A resposta não enviou Content-Security-Policy. Isso reduz uma camada de defesa contra conteúdo injetado."})
                    if "x-content-type-options" not in response_headers:
                        security_issues.append({"severity": "low", "code": "NOSNIFF_MISSING", "title": "X-Content-Type-Options ausente", "detail": "O cabeçalho nosniff não foi observado."})
                    if "referrer-policy" not in response_headers:
                        security_issues.append({"severity": "low", "code": "REFERRER_POLICY_MISSING", "title": "Referrer-Policy ausente", "detail": "A resposta não definiu explicitamente uma política de Referer."})
                    if urlparse(url).scheme == "https" and "strict-transport-security" not in response_headers:
                        security_issues.append({"severity": "low", "code": "HSTS_MISSING", "title": "HSTS não observado", "detail": "A resposta HTTPS não enviou Strict-Transport-Security."})
                    for form in soup.find_all("form", action=True):
                        action_url = urljoin(url, form.get("action", ""))
                        if urlparse(action_url).scheme == "http":
                            security_issues.append({"severity": "medium", "code": "INSECURE_FORM_ACTION", "title": "Formulário envia para HTTP", "detail": "Foi observado um formulário cujo destino usa HTTP."})
                            break
                    job.pages.append({
                        "url": url, "title": title[:300], "description": description[:500],
                        "text_preview": text_content[:500], "depth": depth,
                        "links_found": len(links), "status_code": response.status_code, "security_issues": security_issues,
                    })
                    job.log(f"Analisada: {title[:100]} — {url}")
                except (httpx.HTTPError, CrawlError, UnicodeError) as exc:
                    job.log(f"Falha ao processar {url}: {str(exc)[:180]}", "warning")
                await asyncio.sleep(1.0)

        job.status = "completed"
        job.log("Exploração concluída.")
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.log(f"Execução interrompida: {exc}", "error")
    finally:
        job.finished_at = time.monotonic()
