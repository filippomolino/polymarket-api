#!/usr/bin/env python3
"""
Polymarket Geopolitical Intelligence Agent

Combines Polymarket prediction markets with real-time geopolitical intelligence
(GDELT news, ReliefWeb crises, USGS earthquakes) to surface mispriced markets.
No API keys required for intelligence sources.

Setup:
  1. pip install -r requirements.txt
  2. set GROQ_API_KEY=your_key_here   (Windows)
  3. python agent.py
     or: python agent.py "Which Ukraine-related markets are trending?"
"""

import json
import os
import sys
from datetime import datetime, timedelta

import requests
from openai import OpenAI

# ── Client (Groq via OpenAI-compatible API) ───────────────────────────────────
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
)
MODEL = "llama3-groq-70b-8192-tool-use-preview"

# ── API base URLs ─────────────────────────────────────────────────────────────
GAMMA_URL     = "https://gamma-api.polymarket.com"
CLOB_URL      = "https://clob.polymarket.com"
GDELT_URL     = "https://api.gdeltproject.org/api/v2/doc/doc"
RELIEFWEB_URL = "https://api.reliefweb.int/v1/disasters"
USGS_URL      = "https://earthquake.usgs.gov/fdsnws/event/1/query"


# ── Polymarket tools ──────────────────────────────────────────────────────────

def get_active_markets(limit: int = 50) -> str:
    resp = requests.get(
        f"{GAMMA_URL}/markets",
        params={"active": "true", "closed": "false", "limit": int(limit)},
        timeout=10,
    )
    resp.raise_for_status()
    markets = resp.json()
    slim = [
        {
            "id": m.get("id"),
            "question": m.get("question"),
            "endDate": m.get("endDate"),
            "volume": m.get("volume"),
            "tokens": [t.get("token_id") for t in m.get("tokens", [])],
        }
        for m in markets
    ]
    return json.dumps(slim)


def search_markets(query: str) -> str:
    resp = requests.get(
        f"{GAMMA_URL}/markets",
        params={"active": "true", "closed": "false", "search": query, "limit": 20},
        timeout=10,
    )
    resp.raise_for_status()
    markets = resp.json()
    slim = [
        {
            "id": m.get("id"),
            "question": m.get("question"),
            "endDate": m.get("endDate"),
            "volume": m.get("volume"),
            "tokens": [t.get("token_id") for t in m.get("tokens", [])],
        }
        for m in markets
    ]
    return json.dumps(slim)


def get_order_book(token_id: str) -> str:
    resp = requests.get(f"{CLOB_URL}/book", params={"token_id": token_id}, timeout=10)
    resp.raise_for_status()
    return resp.text


# ── Intelligence tools (no API keys required) ─────────────────────────────────

def search_news(query: str, hours_back: int = 24) -> str:
    """Search recent global news via GDELT Doc API."""
    try:
        resp = requests.get(
            GDELT_URL,
            params={
                "query": query,
                "mode": "artlist",
                "maxrecords": 20,
                "format": "json",
                "timespan": f"{int(hours_back)}h",
                "sort": "datedesc",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        if not articles:
            return json.dumps({"articles": [], "note": "No recent articles found."})
        slim = [
            {
                "title": a.get("title"),
                "domain": a.get("domain"),
                "seendate": a.get("seendate"),
            }
            for a in articles
        ]
        return json.dumps({"articles": slim})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_active_crises() -> str:
    """Get ongoing humanitarian crises from ReliefWeb."""
    try:
        resp = requests.get(
            RELIEFWEB_URL,
            params={
                "appname": "polymarket-agent",
                "limit": 20,
                "status": "current",
                "fields[include][]": ["name", "country", "type", "date", "status"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        crises = [
            {
                "name": item["fields"].get("name"),
                "country": [c.get("name") for c in item["fields"].get("country", [])],
                "type": [t.get("name") for t in item["fields"].get("type", [])],
                "date": item["fields"].get("date", {}).get("created"),
            }
            for item in data.get("data", [])
        ]
        return json.dumps({"crises": crises})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_major_earthquakes(min_magnitude: float = 6.0) -> str:
    """Get recent significant earthquakes from USGS."""
    try:
        start = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        resp = requests.get(
            USGS_URL,
            params={
                "format": "geojson",
                "minmagnitude": min_magnitude,
                "orderby": "time",
                "limit": 10,
                "starttime": start,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        quakes = [
            {
                "place": f["properties"].get("place"),
                "magnitude": f["properties"].get("mag"),
                "time": datetime.utcfromtimestamp(
                    f["properties"]["time"] / 1000
                ).strftime("%Y-%m-%d %H:%M UTC"),
                "tsunami": bool(f["properties"].get("tsunami")),
            }
            for f in data.get("features", [])
        ]
        return json.dumps({"earthquakes": quakes})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "get_active_markets":    lambda args: get_active_markets(),
    "search_markets":        lambda args: search_markets(args.get("query", "")),
    "get_order_book":        lambda args: get_order_book(args.get("token_id", "")),
    "search_news":           lambda args: search_news(args.get("query", ""), int(args.get("hours_back", 24))),
    "get_active_crises":     lambda args: get_active_crises(),
    "get_major_earthquakes": lambda args: get_major_earthquakes(args.get("min_magnitude", 6.0)),
}

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_active_markets",
            "description": "Get active prediction markets from Polymarket.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_markets",
            "description": "Search Polymarket markets by keyword (e.g. 'Ukraine', 'tariff', 'election').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword or phrase to search for."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_book",
            "description": "Get the current order book (bids/asks) for a specific Polymarket token.",
            "parameters": {
                "type": "object",
                "properties": {
                    "token_id": {"type": "string", "description": "Token ID from get_active_markets."}
                },
                "required": ["token_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": (
                "Search recent global news articles via GDELT (no API key required). "
                "Use targeted queries like 'Ukraine ceasefire negotiations', 'China Taiwan strait', "
                "'US tariffs China trade war'. Returns article titles from the last N hours."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific search query related to a market topic.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_crises",
            "description": "Get list of ongoing humanitarian crises and disasters from ReliefWeb (no API key required).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_major_earthquakes",
            "description": "Get recent significant earthquakes (magnitude 6+) from USGS (no API key required).",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_magnitude": {
                        "type": "number",
                        "description": "Minimum magnitude threshold (default 6.0).",
                    },
                },
            },
        },
    },
]

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a geopolitical market intelligence analyst specializing in prediction markets.

Your workflow:
1. Call get_active_markets() to see what markets exist on Polymarket
2. Call get_active_crises() to get the current list of ongoing global crises
3. For each geopolitically relevant market, call search_news(query) with a specific query to find recent events
4. Assess whether the news shifts the probability of YES resolution up or down
5. Output a ranked list of actionable opportunities

CRITICAL RULES:
- Call search_news ONE TIME per query with a single string argument — never pass an array or batch multiple queries into one call
- Every insight must cite a specific article title or crisis name you received from tool calls
- Do not use general world knowledge — only data returned by tools counts as evidence
- If search_news returns no articles for a query, skip that market
- Only include markets where you found concrete recent news

For each opportunity output:
- Market question
- Evidence (quote the actual article title or crisis name from tool results)
- Directional view: BULLISH on YES / BEARISH on YES
- Confidence: High / Medium / Low
- One-sentence rationale

Prioritize markets with high volume and near-term end dates."""


# ── Agentic loop ──────────────────────────────────────────────────────────────

def run_agent(prompt: str) -> None:
    print(f"\n{'─'*60}")
    print("  Polymarket Geopolitical Intelligence Agent")
    print(f"{'─'*60}\n")
    print(f"Query: {prompt}\n")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
        )

        message = response.choices[0].message

        if message.content:
            print(message.content)

        if not message.tool_calls:
            break

        messages.append(message)
        for call in message.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            print(f"  → {name}({json.dumps(args) if args else ''})")

            try:
                result = TOOL_FUNCTIONS[name](args)
            except Exception as e:
                result = json.dumps({"error": str(e)})

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })


if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not set.")
        print("Get a free key at https://console.groq.com then:")
        print("  set GROQ_API_KEY=your_key_here")
        sys.exit(1)

    default = (
        "Analyze current geopolitical events and identify Polymarket prediction markets "
        "that may be mispriced or trending. Focus on the most actionable opportunities."
    )
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else default
    run_agent(query)
