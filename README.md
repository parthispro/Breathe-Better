# 🌬️ Breathe-Better — Urban Air Quality Assistant

A lightweight, responsive web application that transforms real-time air quality data into understandable insights and actionable health recommendations.

---

## ⚡ Quick Start

### Python 3.14 — Kali Linux / Current

```bash
cd Breathe-Better
pip install -r requirements-py314.txt
python3 app.py
```

### Python 3.15 — Faster (async httpx + HTTP/2)

```bash
pip install -r requirements-py315.txt
python3 app.py
```

Open **http://localhost:5000** in your browser.

---

## 📦 Requirements

| File | Python | HTTP Client | Use |
|------|--------|-------------|-----|
| `requirements-py314.txt` | 3.14+ ✅ Kali | `requests` (sync) | Default |
| `requirements-py315.txt` | 3.15+ 🚀 | `httpx` (async + HTTP/2) | Faster I/O |
| `requirements.txt`       | 3.14+ | Same as py314 | Generic alias |

**No API keys required** — uses [Open-Meteo](https://open-meteo.com/) (free, open data).

---

## 🧪 Testing

```bash
# All tests with coverage report
python3 -m pytest tests/ -v --cov=aqi --cov=api --cov-report=term-missing

# AQI unit tests only
python3 -m pytest tests/test_aqi.py -v

# API integration tests only (uses mocks — no network required)
python3 -m pytest tests/test_api.py -v

# Lint
python3 -m ruff check .
```

---

## 📁 Project Structure

```
Breathe-Better/
├── app.py                  ← Flask server, routes, TTL cache, security headers
├── api.py                  ← Open-Meteo API client (geocoding + air quality)
├── aqi.py                  ← CPCB India AQI sub-index engine + recommendations
│
├── requirements-py314.txt  ← Python 3.14 (Kali-compatible, sync requests)
├── requirements-py315.txt  ← Python 3.15 (async httpx + HTTP/2)
├── requirements.txt        ← Default alias → py314
│
├── templates/
│   └── index.html          ← Semantic HTML5 SPA shell
│
├── static/
│   ├── style.css           ← Mobile-first responsive CSS, AQI colour tokens
│   └── app.js              ← Vanilla JS: fetch, render, autocomplete, localStorage
│
└── tests/
    ├── test_aqi.py         ← 30+ unit tests for AQI engine
    └── test_api.py         ← Mock integration tests for API client
```

---

## 🌐 AQI Standard

Uses **CPCB (Central Pollution Control Board) India National Air Quality Index** methodology with official breakpoints for:

| Pollutant | Unit | Description |
|-----------|------|-------------|
| PM2.5 | µg/m³ | Fine particulate matter |
| PM10  | µg/m³ | Coarse particulate matter |
| NO₂   | µg/m³ | Nitrogen dioxide |
| O₃    | µg/m³ | Ozone |
| CO    | mg/m³ | Carbon monoxide |
| SO₂   | µg/m³ | Sulphur dioxide |

| AQI Range | Category | Colour |
|-----------|----------|--------|
| 0–50 | Good | 🟢 |
| 51–100 | Satisfactory | 🟡 |
| 101–200 | Moderate | 🟡 |
| 201–300 | Poor | 🟠 |
| 301–400 | Very Poor | 🔴 |
| 401–500 | Severe | 🟣 |

> ⚠️ Health recommendations are **informational only** and do not constitute medical advice.

---

## 🔒 Security

- Content Security Policy header on all responses
- Input validation (strip, length-cap, regex check) before API calls
- No API credentials stored in code or committed to version control
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
- XSS prevention: all user-visible dynamic content escaped via `createTextNode`

---

## 📐 Responsive Breakpoints

| Width | Layout |
|-------|--------|
| 320–767 px | Single-column, touch-friendly |
| 768–1023 px | Two/three-column pollutant grid |
| 1024 px+ | Six-column pollutant grid + expanded chart |

---

## 📏 Submission Size Check

```bash
# Check current size (excludes venv, caches, pyc files)
du -sh --exclude=__pycache__ --exclude='*.pyc' --exclude=.venv .
```

Target: **< 10 MB** (submission constraint). Recommended internal target: **< 7 MB**.

---

## 🗺️ Data Sources

- **Air quality:** [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- **Geocoding:** [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- Both are free, open, and require no API key.
