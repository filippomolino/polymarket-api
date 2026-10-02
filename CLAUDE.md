# Polymarket Geopolitical Trading Agent System

## Project Goal

Build a multi-agent AI system that **makes money trading on Polymarket** by combining:
- Real-time geopolitical and economic intelligence (WorldMonitor)
- Prediction market data (Polymarket)
- Collaborative specialized agents that reason, decide, and execute trades

The system should anticipate market sentiment shifts before they are priced in, identify mispriced markets, and execute trades autonomously.

---

## Current State

Single agent (`agent.py`) that:
- Fetches active Polymarket markets via the Gamma API
- Fetches geopolitical intelligence from WorldMonitor's local REST API
- Uses LLaMA 3.3 70B on Groq (free) to cross-reference events → markets
- Outputs ranked market opportunities with directional views

---

## Target Architecture: Multi-Agent System

Three specialized agents that collaborate in a pipeline:

```
WorldMonitor ──► [Agent 1: Geopolitical Analyst]
                        │
                        ▼ structured intelligence brief
               [Agent 2: Investment Strategist]
                        │
                        ▼ ranked trade recommendations
               [Agent 3: Trader]
                        │
                        ▼
               Polymarket CLOB API (execute trades)
```

### Agent 1 — Geopolitical Analyst
- **Input:** Raw WorldMonitor feeds (conflict, unrest, military, sanctions, trade, macro)
- **Job:** Summarize what is happening in the world, assess severity, identify which countries/topics are most active
- **Output:** Structured intelligence brief (JSON) — list of significant events with severity scores

### Agent 2 — Investment Strategist
- **Input:** Intelligence brief from Agent 1 + active Polymarket markets
- **Job:** Map events to markets, assess probability shifts, rank opportunities by expected value
- **Output:** Trade recommendations (JSON) — market ID, direction (YES/NO), confidence, rationale

### Agent 3 — Trader
- **Input:** Trade recommendations from Agent 2
- **Job:** Check order books, size positions, execute trades via Polymarket CLOB API
- **Output:** Executed trades, portfolio state, P&L tracking
- **Constraints:** Risk limits, max position size, stop-loss rules

---

## API Reference

### Polymarket
| Endpoint | URL | Notes |
|----------|-----|-------|
| Active markets | `https://gamma-api.polymarket.com/markets?active=true&closed=false` | Public, no auth |
| Search markets | `https://gamma-api.polymarket.com/markets?search=<query>` | Public |
| Order book | `https://clob.polymarket.com/book?token_id=<id>` | Public |
| Execute trade | `https://clob.polymarket.com` | **Requires wallet + API key** |

Trading on Polymarket requires:
1. A crypto wallet (MetaMask or similar)
2. USDC on Polygon network (the collateral currency)
3. Polymarket API key (from app.polymarket.com → Settings → API)
4. Signing transactions with the wallet private key

### WorldMonitor (local dev server)
Run with: `cd worldmonitor && npm run dev` → available at `http://localhost:3000`

| Endpoint | Path | Key params |
|----------|------|------------|
| Conflict events | `/api/conflict/v1/list-acled-events` | `country`, `start`, `end`, `page_size` |
| Unrest events | `/api/unrest/v1/list-unrest-events` | `country`, `start`, `end`, `min_severity` |
| Military posture | `/api/military/v1/get-theater-posture` | `theater` (indo-pacific/european/middle-east) |
| Sanctions | `/api/sanctions/v1/list-sanctions-pressure` | none |
| Trade restrictions | `/api/trade/v1/get-trade-restrictions` | `countries` |
| Macro signals | `/api/economic/v1/get-macro-signals` | none |

All WorldMonitor endpoints return JSON. Timestamps are Unix epoch milliseconds.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | LLaMA 3.3 70B via Groq (free tier) |
| LLM SDK | `openai` Python package (Groq is OpenAI-compatible) |
| Geopolitical data | WorldMonitor (self-hosted, Node.js) |
| Market data | Polymarket Gamma API + CLOB API |
| Language | Python 3.x |
| Environment | venv at `./venv` |

---

## Environment Setup

```bash
# Activate venv (always do this first)
venv\Scripts\activate

# Required env vars
set GROQ_API_KEY=...          # Free at console.groq.com

# Future: when trading is enabled
set POLYMARKET_API_KEY=...    # From app.polymarket.com
set WALLET_PRIVATE_KEY=...    # Handle with extreme care
```

---

## File Structure

```
polymarket-api/
├── agent.py              # Current: single agent (geopolitical analyst + strategist combined)
├── requirements.txt      # Python dependencies
├── CLAUDE.md             # This file
├── polymarket_tracker.py # Original simple API wrapper (reference)
├── venv/                 # Python virtual environment
└── postman/              # Original Postman collection (reference only)
```

**Planned structure for multi-agent system:**
```
polymarket-api/
├── agents/
│   ├── geopolitical.py   # Agent 1: WorldMonitor → intelligence brief
│   ├── strategist.py     # Agent 2: intelligence + markets → trade recommendations
│   └── trader.py         # Agent 3: recommendations → executed trades
├── tools/
│   ├── polymarket.py     # All Polymarket API calls
│   └── worldmonitor.py   # All WorldMonitor API calls
├── orchestrator.py       # Runs the full pipeline, wires agents together
├── config.py             # Risk limits, model selection, API URLs
└── portfolio.py          # Track positions, P&L, risk exposure
```

---

## Roadmap

### Phase 1 — Intelligence (current)
- [x] Single agent reads WorldMonitor + Polymarket and surfaces opportunities
- [ ] Improve output format (structured JSON not just text)
- [ ] Add scheduling (run every N minutes automatically)

### Phase 2 — Multi-agent split
- [ ] Split into 3 specialized agents with defined input/output contracts
- [ ] Agent 1 outputs structured JSON brief
- [ ] Agent 2 consumes brief, outputs ranked trade list
- [ ] Agents run sequentially via `orchestrator.py`

### Phase 3 — Trading execution
- [ ] Set up Polymarket API credentials (wallet + CLOB key)
- [ ] Agent 3 reads order books, sizes positions
- [ ] Execute trades via CLOB API (sign with wallet)
- [ ] Add risk controls: max position size, stop-loss, daily loss limit

### Phase 4 — Autonomy + learning
- [ ] Run on a schedule (cron or loop)
- [ ] Log all trades and outcomes
- [ ] Feed resolved market outcomes back to improve agent reasoning
- [ ] Portfolio dashboard

---

## Key Risks & Constraints

- **Polymarket trading requires real money (USDC)** — always test with small amounts first
- **Prediction markets are zero-sum** — you are trading against informed humans and bots
- **WorldMonitor API may not always be available** — all WorldMonitor tools handle offline gracefully
- **LLM reasoning is not infallible** — always review agent outputs before enabling auto-trading
- **Groq free tier has rate limits** — may need to throttle requests or upgrade for production

---

## How to Run

```bash
# Start WorldMonitor (separate terminal)
cd worldmonitor
npm run dev

# Run the agent (this terminal)
venv\Scripts\activate
set GROQ_API_KEY=your_key
python agent.py
python agent.py "Which Middle East markets are trending right now?"
```
