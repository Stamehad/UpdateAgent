# Stay Up To Date Agent

A lightweight Python tool that helps you keep up with blogs, YouTube channels, and academic papers by automatically fetching new content, summarizing it with an LLM, and compiling everything into a daily digest.

## Features

- **Blog tracking**: Monitor specific blogs via RSS or custom scraping. New posts are downloaded, parsed, and saved.
- **YouTube tracking**: Subscribe to channel RSS feeds to capture video titles and descriptions without visiting YouTube.
- **bioRxiv integration**: Fetch recent preprints filtered by keywords and include abstracts in the digest.
- **Summarization**: Feed content into an LLM (OpenAI API) to generate concise summaries or abstracts, customizable per source.
- **Digest reports**: Produces both Markdown and HTML digests with summaries, including per‑source statistics (e.g. how many matched vs. shown).
- **Automation**: Can be run manually, via macOS `launchd`, or in CI/cloud to deliver digests automatically.

## Project Structure

```
stay_up_to_date_agent/
├─ src/                 # source code
│  ├─ aggregator/       # logic for collecting posts from sources
│  ├─ agent/            # summarization / LLM router
│  ├─ sources/          # source adapters (blogs, youtube, biorxiv, ...)
│  └─ report/           # rendering of daily digest (md/html)
├─ config.yml           # configuration of sources and preferences
├─ requirements.txt     # Python dependencies
├─ run_daily.sh         # helper script to run inside conda env
├─ data/
│  ├─ state.json        # remembers seen posts
│  ├─ posts/            # raw post markdown files (if enabled)
│  └─ reports/          # generated daily digests
└─ README.md
```

## Installation

1. Clone this repo:
   ```bash
   git clone https://github.com/yourname/stay_up_to_date_agent.git
   cd stay_up_to_date_agent
   ```
2. Create a conda environment:
   ```bash
   conda create -n update_agent python=3.11 -y
   conda activate update_agent
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your OpenAI API key.

## Usage

Run manually:
```bash
python -m src.main --limit 5
```
This fetches new content, summarizes it, and writes digest files to `data/reports/`.

### Automation on macOS

1. Edit `run_daily.sh` to point to your environment.
2. Add a LaunchAgent plist in `~/Library/LaunchAgents/` to run at 9am daily.

### Configuration

All sources are defined in `config.yml`. Example:
```yaml
sources:
  blogs:
    - key: scott_aaronson
      display_name: "Shtetl‑Optimized"
      feed: "https://scottaaronson.blog/?feed=atom"
      enabled: true

  youtube:
    - key: ai_coffee_break
      display_name: "AI Coffee Break with Letitia"
      id: UCobqgqE4i5Kf7wrxRxhToQA
      digest_mode: "title_plus_description"   # or "llm" or "title_only"
      enabled: true

  biorxiv:
    - key: bio_ml
      display_name: "bioRxiv — ML in structure/drug discovery"
      keywords:
        - machine learning
        - protein
        - drug discovery
      days: 2
      max_keep: 5
      digest_mode: "abstract_only"
      enabled: true
```

## Output

Each run generates:
- `data/reports/digest-YYYY-MM-DD.md`
- `data/reports/digest-YYYY-MM-DD.html`

The digest includes a summary section showing per‑source counts and truncation (e.g. *showing 5/5 from 18 matches*).

## Roadmap / Ideas

- [ ] Add arXiv integration with LLM ranking
- [ ] Push digests to iCloud/Notion for iPhone reading
- [ ] Audio digest / podcast mode
- [ ] Twitter/X integration via RSSHub or API

## License

MIT