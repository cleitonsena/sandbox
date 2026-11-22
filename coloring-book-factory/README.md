# Coloring Book Factory

A small, mostly autonomous pipeline that researches, draws, reviews and packages adult coloring books, with a human approving every step that costs money or goes public.

It produced its first book, **Cozy Little Corners** (Toffee Tabby collection): 50 bold and easy pages, a print-on-demand paperback kit, a printable PDF and a free 5-page sample.

- Printable book: https://cleitonsenaa.gumroad.com/l/cozy-coloring-book-printable
- Free sample: https://cleitonsenaa.gumroad.com/l/free-cozy-coloring-pages

> Source-available, **not open source**. Free for personal and noncommercial use under the PolyForm Noncommercial License 1.0.0. For commercial use, or to have something like this built for you, see [Commercial use and collaboration](#commercial-use-and-collaboration).

## What it does

One queue, one loop. A launchd job runs `bin/fabrica.py` every 30 minutes on a spare MacBook Air. Each task in the queue moves forward until it either finishes or reaches a **human gate**, then it waits.

```
benchmark  ->  brief  -> [gate: brief]  ->  pages  -> [gate: failed pages]
   ->  interior PDF  ->  cover  ->  listing copy  ->  whole-book review
   ->  archive  ->  upload kit  ->  retro  ->  Drive + spreadsheet  -> [gate: human upload]  ->  done
```

| Step | What happens | Code |
|---|---|---|
| Benchmark | Pulls competitor coloring books (price, rating, reviews, sales rank) and proposes a price below the median that still pays back the production cost | `fabrica.py` (`benchmark`, `preco_abaixo`), `mercado_amazon*.py` |
| Brief | An agent writes the page list and the style prompt | `fabrica.py` |
| Pages | Each page is generated, auto-checked (margins, grey, ink coverage) and judged by a reviewer agent that looks at the image; failures are redrawn up to 3 times, then go to a human queue. Approved pages are upscaled to 300 dpi line art | `linha.py`, `gerar_imagem.py` |
| Interior and cover | Print-ready PDFs that follow the print-on-demand spec (trim, bleed, spine width per page count, safe zones) | `montar.py`, `capa_final.py` |
| Whole-book review | A reviewer agent sees every page, the cover and the listing at once and sends weak pages back, once | `fabrica.py` |
| Kit | Upload kit, printable Letter PDF, free sample, listing copy | `imprimivel.py`, `fabrica.py` |
| Retro | Cost per approved page, first-pass approval rate, lessons that feed the next brief | `fabrica.py` (`retro`, `metricas`) |
| Reporting | Uploads files to Google Drive and rebuilds a one-column-per-book spreadsheet (costs, price, net per sale, payback) | `fabrica.py` (`drive_e_planilha`), `planilha.py`, `gsheets.py` |
| Marketplace draft | Creates an Etsy listing **draft** through the Etsy Open API v3; it has no call that publishes | `etsy_rascunho.py` |

`experiments/` holds the throwaway scripts used to choose the cover design and typography (proof sheets).

## Rules the bots never break

These are enforced in code and in the agent prompts:

1. Never create accounts, pay, publish or contact anyone. Those are human actions.
2. Never read, write or ask for passwords or keys. Keys live in files outside the repo (`chmod 600`) or the OS keychain and are never printed.
3. Never browse or scrape the marketplace directly. Market data comes from a third-party data provider.
4. Never invent a number. Every figure has a source link or is labelled as an estimate.
5. Hard spend caps: USD 2 per book and USD 10 per month without asking.

## Numbers from the first book

Measured on Cozy Little Corners, November 2026: image generation about USD 0.02 per page and USD 0.06 per cover, market data about USD 0.006 per competitor book. The language-model agents run on a flat subscription, so they add no per-call cost.

## Stack

- Python 3 standard library plus Pillow
- OpenAI Images API (`gpt-image-2`) for pages and cover art
- Codex CLI in read-only mode for the brief, reviewer and copy agents, with JSON-schema outputs
- Apify actors for marketplace data
- rclone + Google Sheets API for Drive and the reporting sheet
- Etsy Open API v3 (OAuth 2.0 with PKCE) for listing drafts
- macOS launchd for scheduling

Code comments and agent prompts are in Portuguese.

## Running it

This is a working personal setup, not a packaged tool. Paths assume `~/livros` (books and `bin/`) and `~/empresa` (queue, decisions, costs, `config.json`).

1. `pip install pillow`, install the Codex CLI and rclone.
2. Put your keys where the scripts expect them (see each script's docstring): `~/.openai-imagens`, `~/.apify-pessoal`, an rclone remote named `pessoal`.
3. Copy `examples/livro-modelo.json` into `~/livros/<book>/livro.json` and add a task to `~/empresa/fila/`, for example `{"tipo": "livro", "pasta": "~/livros/<book>"}`.
4. Run `python3 bin/fabrica.py` once, or load `launchd/com.example.fabrica.plist` (replace `YOU` with your user).
5. Approve gates by writing `aprovacoes.json` in the book folder.

## Commercial use and collaboration

The license allows personal use, study, hobby projects and use by noncommercial organizations. Any commercial use needs a separate paid license.

If you want to use this commercially, collaborate, or have a similar pipeline built for your business, reach out:

- LinkedIn: https://www.linkedin.com/in/cleiton-sena/
- GitHub: https://github.com/cleitonsena
- DEV: https://dev.to/cleitonsena
- X: https://x.com/cleitonsenaes
- Instagram: https://www.instagram.com/cleitonsenaes/

## License

[PolyForm Noncommercial License 1.0.0](LICENSE). Required Notice: Copyright 2026 Cleiton Sena (https://github.com/cleitonsena)
