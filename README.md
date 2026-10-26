# 🚀 Groww Review Pulse Agent & Telemetry Dashboard

An autonomous review intelligence pipeline and modern telemetry dashboard built for fintech product and engineering teams. The agent continuously ingests Google Play Store reviews for **Groww**, runs multi-tiered LLM classification (sentiment, categorization, urgency), compiles weekly executive pulse digests, dispatches email alerts via Gmail API, and renders an interactive web dashboard.

---

## ✨ Features

- **Automated Review Ingestion**: Google Play Store scraper with deduplication, incremental sync, and robust error handling.
- **AI-Powered Review Classification**:
  - **L1 / L2 Categories**: Ingests and routes issues across *KYC/Onboarding*, *Trading & Orders*, *Payments & UPI*, *Mutual Funds*, *Customer Support*, and *App Performance & Stability*.
  - **Sentiment & Urgency Scoring**: Granular sentiment scoring (-1.0 to +1.0) and urgency levels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
  - **Fast LLM Inference**: Powered by Groq (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`).
- **Weekly Executive Pulse**: Automatically synthesized executive summaries highlighting key metrics, top emerging issues, feature praise, and critical bugs.
- **Glassmorphic Web Dashboard**:
  - **Executive Pulse**: High-level KPIs, sentiment distributions, and prioritized risk items.
  - **Longitudinal Trend Analytics**: Weekly telemetry charts tracking ratings, volume, and sentiment trends from 2026-W20 to current.
  - **Review Explorer**: Interactive filter by rating, search keyword, and review urgency.
  - **Pipeline Dispatcher**: On-demand scraping, classification, and test email delivery directly from the UI.
- **Gmail Notification Service**: Automated HTML email delivery to stakeholders using Google OAuth2 credentials.
- **Production-Ready Deployment**: Configured for Docker and 1-click deployment to [Railway](https://railway.app/).

---

## 🏗️ Architecture

```
                                  +------------------------+
                                  |   Google Play Store    |
                                  +-----------+------------+
                                              |
                                              v
+------------------+              +-----------+------------+
|  Cron / Pipeline | -----------> |   Scraper & Ingestion  |
+------------------+              +-----------+------------+
                                              |
                                              v
+------------------+              +-----------+------------+
|  Groq LLM Engine | <----------> |  Review Classification |
+------------------+              +-----------+------------+
                                              |
                                              v
+------------------+              +-----------+------------+
|  Gmail API / SES | <----------- | Weekly Pulse Synthesis |
+------------------+              +-----------+------------+
                                              |
                                              v
                                  +-----------+------------+
                                  | FastAPI Telemetry Hub  |
                                  +-----------+------------+
                                              |
                                              v
                                  +------------------------+
                                  | Glassmorphic Dashboard |
                                  +------------------------+
```

---

## 📁 Project Structure

```
aiagent/
├── data/                       # Telemetry datasets & pulse archives
│   ├── raw/                    # Scraped Play Store reviews
│   ├── cleaned/                # Deduplicated & sanitized records
│   ├── classified/             # L1/L2 classified & sentiment scored reviews
│   ├── enriched/               # Processed datasets
│   ├── pulses/                 # Weekly JSON/Markdown/HTML pulse reports
│   └── run_log.json            # Pipeline run logs
├── src/
│   ├── pipeline/               # Core pipeline stages (scraper, classifier, pulse generator)
│   ├── services/               # LLM clients (Groq), email service, auth
│   ├── config/                 # Pydantic settings & environment configuration
│   └── web/                    # FastAPI backend & static frontend assets
│       ├── app.py              # Dashboard API routes & static mount
│       ├── static/             # HTML, CSS, JS dashboard frontend
├── tests/                      # Automated test suite (99 pytest tests)
├── Dockerfile                  # Container definition for production
├── railway.toml                # Railway deployment configuration
├── Procfile                    # Process definition
├── run_web.py                  # Web application entrypoint
├── main.py                     # Pipeline CLI entrypoint
├── requirements.txt            # Python dependencies
└── docs/                       # Project documentation
    ├── architecture.md         # System design & pipeline architecture
    ├── deployment-plan.md      # Comprehensive deployment guide
    ├── implementation.md       # Multi-phase implementation specs
    ├── problemstatement.md     # Requirements & problem statement
    └── design.md               # Dashboard UI design system
```

---

## 🛠️ Quickstart

### 1. Prerequisites
- Python 3.11+
- Groq API Key (free tier available at [console.groq.com](https://console.groq.com))
- Google OAuth credentials (optional, only required for automated Gmail delivery)

### 2. Installation
```bash
git clone https://github.com/Shashikiran-R/groww-pulse-mail-agent.git
cd groww-pulse-mail-agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the sample environment file and configure your keys:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
GROQ_API_KEY=your_groq_api_key_here
PORT=8080
LOG_LEVEL=INFO
```

### 4. Running the Web Dashboard
```bash
python run_web.py --port 8080 --reload
```
Open [http://localhost:8080](http://localhost:8080) in your browser.

### 5. Running the Pipeline via CLI
```bash
# Scrape latest reviews
python main.py scrape

# Run review classification & sentiment scoring
python main.py classify

# Synthesize weekly executive pulse
python main.py pulse

# Run the complete end-to-end pipeline
python main.py full-run
```

---

## 🧪 Testing

The repository includes a comprehensive automated test suite with 99 passing tests:

```bash
pytest -v
```

---

## 🚢 Deployment

### Deploying to Railway

1. Push your repository to GitHub.
2. Log in to [Railway](https://railway.app/) and click **New Project** > **Deploy from GitHub repo**.
3. Select `groww-pulse-mail-agent`.
4. Railway will automatically detect the `Dockerfile` and `railway.toml`.
5. Under **Variables**, add:
   - `GROQ_API_KEY` = your Groq API key
   - (Optional) Google OAuth credentials for automated email delivery.
6. Click **Deploy**. Your dashboard will be live at `https://<your-railway-app>.up.railway.app`.

For persistent volume mounting or advanced configuration, see [deployment-plan.md](docs/deployment-plan.md).

---

## 📄 License

MIT License.
