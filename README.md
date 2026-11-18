# WEBSPIDER — The Internet Explorer Engine

A free, open-source crawler for discovering and organizing publicly accessible web pages.

## Current features

- Same-origin crawling (the crawler stays on the starting website).
- Reads and follows the site's `robots.txt` rules.
- Configurable limit of 1–50 pages and depth of 0–3.
- One request at a time with a one-second pause between page requests.
- Extracts page title, meta description, a short text preview and discovered links.\n- Performs passive checks for HTTPS and selected security headers; findings are indicators, not proof of exploitable vulnerabilities.\n- Searches published fact-check reviews through Google Fact Check Tools when an API key is configured; it never labels a claim false based only on writing style.
- Live dashboard updates through API polling.
- CSV export after a crawl.
- Blocks localhost, private, reserved and non-public IP destinations, including redirects to another origin.
- Limits downloaded response bodies to 2 MB per request.
- Stops safely when robots.txt cannot be verified or returns an access/rate-limit/server error.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

## Publicar a interface no GitHub Pages

O repositório inclui o workflow `.github/workflows/pages.yml`, que publica automaticamente a interface estática em cada atualização da branch `main`.

Endereço esperado: https://annasb-oss.github.io/WEBSPIDER---THE-INTERNET-EXPLORER-ENGINE-/

**Limitação importante:** GitHub Pages hospeda somente HTML, CSS e JavaScript. O crawler, a auditoria passiva e a consulta de checagens precisam do backend Python no Render. A interface agora permite conectar a URL do backend; sem esse serviço, as funções ficam indisponíveis e não simulam resultados.

Depois do primeiro push do workflow, se necessário, abra **Settings → Pages** no GitHub e escolha **GitHub Actions** em Build and deployment. Acompanhe a publicação em **Actions → Deploy WEBSPIDER to GitHub Pages**.

## Deploy gratuito do backend no Render (necessário para ativar o crawler no site)

The repository includes a `render.yaml` Blueprint for a free Python web service.

1. Create a free account at [Render](https://render.com/).
2. In the Render Dashboard, choose **New → Blueprint**.
3. Connect GitHub and select `annasb-oss/WEBSPIDER---THE-INTERNET-EXPLORER-ENGINE-`.
4. Render detects `render.yaml`. Review the service and choose the **Free** plan.
5. Click **Apply** and wait for the first deploy to finish.
6. Open the generated `onrender.com` address and test `/api/health`.\n7. Copy the service URL and paste it into **Conexão segura com o motor WEBSPIDER** on the GitHub Pages site, then click **Conectar**.\n8. To enable claim-review search, create a free API key in Google Cloud, enable Fact Check Tools API, then add it in Render under **Environment** as `GOOGLE_FACTCHECK_API_KEY`. Never put this key in frontend files or commit it to GitHub. See [Google Fact Check API setup](https://developers.google.com/fact-check/tools/api/).

Every new commit on `main` triggers a deployment. GitHub Actions also runs the Python unit tests on pushes and pull requests.

### Free hosting limitations

Render's free web services sleep after 15 minutes without traffic and can take about a minute to wake up. Their filesystem is temporary, and the WEBSPIDER job history is stored in process memory. A restart clears active jobs and results. This setup is suitable for a demonstration; reliable multi-user operation, persistent history, queues and always-on availability require additional infrastructure and may incur costs.

## How to use

1. Enter a public website URL (for example, your own website or a site that permits crawling).
2. Choose the page and depth limits.
3. Start the crawl and watch the metrics and event log update.
4. Download the CSV report when the run finishes.

## Responsible-use limits

WEBSPIDER is intentionally conservative: it only follows links on the starting origin, honors robots.txt, applies a delay between requests, and does not bypass logins, paywalls, rate limits or other access controls. Use it only on websites you own or are authorized to crawl, and check each site's terms and applicable law. Robots.txt is a crawler preference protocol, not legal permission.

The crawler runs inside the API process. Active jobs and results are held in memory and are cleared when the service restarts or sleeps. The free hosting configuration is intended for a portfolio/demo, not production or sensitive workloads. Only one crawl can run at a time.

## Structure

```text
backend/       API and crawler engine
frontend/      Web interface
exports/       Reserved for local reports
tests/         Automated tests
```

## Roadmap

- [x] API health endpoint
- [x] URL validation and crawl configuration
- [x] robots.txt-aware same-origin crawler
- [x] Live execution metrics
- [x] CSV report export
- [ ] JSON and TXT report exports
- [x] Initial automated URL-validation tests
- [ ] Expanded integration tests and persistent job storage

## License

MIT. See [LICENSE](LICENSE).


## Fact-check e auditoria passiva

- A checagem consulta avaliações publicadas via Google Fact Check Tools API. Sem `GOOGLE_FACTCHECK_API_KEY`, a API devolve estado "Não verificado" e um link para o Fact Check Explorer; ela não inventa um veredito.
- Resultado ausente não significa que uma afirmação seja verdadeira. Sempre confira o texto, a data, o contexto e a organização que publicou a checagem.
- A auditoria do crawler observa apenas sinais passivos (HTTPS e alguns cabeçalhos HTTP, além de formulários com destino HTTP). Não executa exploração de falhas, não tenta login, não injeta payloads e não substitui um pentest profissional.
- O crawler é limitado a páginas públicas do mesmo domínio de origem, respeita robots.txt, limita páginas/tamanho de resposta e aplica intervalo entre requisições. Use apenas sites que você possui ou tem autorização para analisar.
- O serviço gratuito do Render pode dormir após inatividade e perder execuções em memória; não é adequado para operação crítica ou disponibilidade garantida.
