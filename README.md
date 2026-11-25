# Breathe-Better
### Urban Air Quality Assistant

Breathe-Better is a lightweight, responsive web application that retrieves real-time air-quality and meteorological dispersion data for any city and presents it through CPCB AQI measurements, pollutant breakdowns, multi-standard comparisons, age-specific health recommendations, atmospheric dispersion metrics, and multi-city batch comparisons.

The application is designed to make environmental data easier to interpret while providing full transparency about scales, grid resolution, data sources, update times, and cache status — all without external frontend frameworks or API keys.

---

## 1. Features

- **Location-based monitoring:** Search for any city or location via autocomplete (`Open-Meteo Geocoding API`) to retrieve real-time air-quality and dispersion data.
- **CPCB AQI calculation:** Computes the India National Air Quality Index using official CPCB sub-index breakpoints and linear interpolation across six criteria pollutants (`PM2.5`, `PM10`, `NO₂`, `O₃`, `CO`, `SO₂`).
- **Age-specific & Kids guidance:** Interactive sensitivity profile pills (`Overall`, `Kids 0–4`, `Kids 5–12`, `Teens 13–17`, `Seniors 60+`, `Asthmatic`) saved locally in browser `localStorage`, paired with a dedicated **Kids & School Guidance** card. Enforces a zero-mask safety policy for ages `0–4 yrs` (suffocation risk; strictly indoor clean-air guidance) and triggers amber health advisories at Moderate AQI (`101–200`) for sensitive profiles while reserving red danger alerts strictly for `> 200`.
- **Atmospheric Dispersion (Ventilation Index):** Fetches wind speed (`m/s`), wind direction, and boundary layer height (`m`) in parallel from Open-Meteo's Weather Forecast API to calculate the Ventilation Coefficient (`m²/s`) and classify stagnation (`High Trapping Risk`, `Moderate Dispersion`, `Good Dispersion`). Degrades gracefully (`ventilation: null`) if forecast data is unavailable.
- **3-way AQI standard comparator:** Compares **CPCB India** (`0–500`), **US EPA** (`0–500+`), and **EU EEA** (`0–100+`) scores side-by-side for the same measurement, explaining why different weather apps report different numbers.
- **Multi-city batch compare (`Compare Cities` tab):** Compares 2–4 cities in one Open-Meteo batch API call, lets users search and add (`+`) or remove (`×`) custom cities directly from the top search dropdown, Overview card, or the dedicated search bar inside the Compare Cities tab, offers one-click wide-spaced metro presets (`Delhi · Jaipur · Mumbai`), and warns when locations share the same ~45 km CAMS grid cell.
- **Historical trends & transparency:** Native SVG 24-hour `PM2.5` trend chart, live timestamps, cached-response indicator, and recent search chips.

## 2. Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla ES6+ JavaScript |
| Backend | Python, Flask, `concurrent.futures` (`ThreadPoolExecutor`), `OrderedDict` TTL cache |
| Air-quality data | Open-Meteo Air Quality API |
| Atmospheric dispersion | Open-Meteo Weather Forecast API |
| Location search | Open-Meteo Geocoding API |
| HTTP client | Requests / HTTPX (Python 3.15 async option) |
| Data visualization | Native inline SVG and CSS |
| Client-side storage | Browser `localStorage` |
| Testing | Pytest + pytest-cov |
| Code quality | Ruff |

**External API credentials:** No API key is required for any configured Open-Meteo endpoint.

## 3. Quick Start

### Prerequisites

- Python 3.14 or later for the synchronous configuration.
- Git (optional, for cloning the repository).
- An internet connection for live external API requests.

### Python 3.14 — Standard Configuration

```bash
git clone <repository-url>
cd Breathe-Better

python3 -m pip install -r requirements-py314.txt
python3 app.py
```

### Python 3.15 — Asynchronous Configuration

```bash
git clone <repository-url>
cd Breathe-Better

python3.15 -m pip install -r requirements-py315.txt
python3 app.py
```

Open the following address in your browser:

```text
http://127.0.0.1:5000
```

### Dependency Configuration

| Requirements file | Python version | HTTP client | Configuration |
|---|---|---|---|
| `requirements-py314.txt` | 3.14+ | Requests | Synchronous |
| `requirements-py315.txt` | 3.15+ | HTTPX | Asynchronous, HTTP/2 |
| `requirements.txt` | 3.14+ | Requests | Default configuration |

## 4. Project Architecture

The application follows a lightweight, modular client-server architecture:

```text
                      User (Browser)
                    HTML / CSS / JS
                           |
                           v
                      Flask Server (app.py)
               +-----------+-----------+
               |                       |
               v                       v
            api.py                   aqi.py
               |                       |
   +-----------+-----------+           +--> CPCB Sub-Index Engine
   |           |           |           +--> Age & Kids Guidance
   v           v           v           +--> Ventilation Coefficient
Geocoding  Air Quality  Forecast       +--> 3-Standard Comparator
  API          API      (Wind/PBL)
               |                       |
               +-----------+-----------+
                           |
                           v
             JSON Response + Strict CSP
```

### Core Components

| Module | Responsibility |
|---|---|
| `app.py` | Flask routes (`/`, `/api/geocode`, `/api/air-quality`, `/api/compare`), parallel `ThreadPoolExecutor` fetch orchestration, bounded `OrderedDict` TTL cache (200 entries / 600 s), input validation, and strict security headers |
| `api.py` | Open-Meteo HTTP clients for geocoding, single-city air quality (`past_days=1` + `us_aqi` / `european_aqi`), forecast ventilation (`wind_speed_unit=ms`, `timeout=4s`), and 2–4 city batch queries with CO `µg/m³ → mg/m³` conversion |
| `aqi.py` | Pure-Python CPCB sub-index calculator, category mapper, overall recommendations, 6-band × 6-tier age/kids guidance, Ventilation Coefficient interpreter, and 3-way AQI standard comparator |
| `templates/index.html` | Semantic WCAG 2.2 AA SPA shell with Overview and Compare Cities tabs, search autocompletes, dispersion/comparator cards, profile pills, Kids card, and inline SVG trend chart |
| `static/style.css` | Mobile-first dark-themed responsive stylesheet, AQI color tokens, amber/red advisory styles, and reduced-motion support |
| `static/app.js` | Strict ES6+ controller for autocomplete + compare (`+` / `×`) toggles, `AbortController`, `localStorage` persistence (`bb_age_profile`, `bb_pinned_cities`, `bb_recent_cities`), DOM/SVG rendering, and keyboard navigation |

## 5. Project Structure

```text
Breathe-Better/
├── app.py
├── api.py
├── aqi.py
├── Procfile
├── requirements.txt
├── requirements-py314.txt
├── requirements-py315.txt
├── README.md
├── LICENSE
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── app.js
└── tests/
    ├── test_aqi.py
    ├── test_api.py
    └── test_app.py
```

## 6. Air Quality & Dispersion Methodology

### CPCB National AQI (India)

Breathe-Better calculates sub-indices using official CPCB breakpoints across six pollutants (`PM2.5`, `PM10`, `NO₂`, `O₃`, `CO` in `mg/m³`, `SO₂`), taking the maximum valid sub-index as the overall AQI:

| AQI range | Category | General Guidance |
|---|---|---|
| 0–50 | Good | Normal outdoor activities |
| 51–100 | Satisfactory | Generally safe; mild discomfort possible for very sensitive individuals |
| 101–200 | Moderate | Sensitive groups (ages 0–4, 5–12, seniors 60+, asthmatics) see amber advisory |
| 201–300 | Poor | Reduce prolonged outdoor exposure; red alert banner displayed |
| 301–400 | Very Poor | Avoid prolonged outdoor activities |
| 401–500 | Severe | Minimize all outdoor exposure and follow official guidance |

### Multi-Standard Comparator

Alongside CPCB India (`0–500`), `/api/air-quality` retrieves Open-Meteo's `us_aqi` (**US EPA**, `0–500+`) and `european_aqi` (**EU EEA**, `0–100+`) in the same request so users can understand why international weather apps display different scores for identical air quality.

### Atmospheric Ventilation Coefficient

`Ventilation Coefficient (m²/s) = Wind Speed (m/s) × Planetary Boundary Layer Height (m)`:
- `< 3000 m²/s`: **High Trapping Risk** (pollutants accumulate near ground level)
- `3000–5999 m²/s`: **Moderate Dispersion**
- `>= 6000 m²/s`: **Good Dispersion**

## 7. Data Sources

| Service | Purpose | Documentation |
|---|---|---|
| Open-Meteo Air Quality API | Pollutant concentrations, 24h PM2.5 series, US EPA & EU EEA indices | [API Documentation](https://open-meteo.com/en/docs/air-quality-api) |
| Open-Meteo Weather Forecast API | Surface wind speed (`m/s`), wind direction, boundary layer height (`m`) | [API Documentation](https://open-meteo.com/en/docs) |
| Open-Meteo Geocoding API | City search and coordinates | [API Documentation](https://open-meteo.com/en/docs/geocoding-api) |

Open-Meteo CAMS global atmospheric model data has a ~0.4° (~45 km) spatial resolution outside European regional domains. When two compared coordinates snap to the same model grid cell (`grid_lat`, `grid_lon`), `/api/compare` sets `shared_grid_warning: true` and surfaces an explanatory banner.

## 8. Testing and Code Quality

The project uses Pytest for automated unit, integration, and Flask route testing, plus Ruff for linting.

```bash
# Run complete test suite with coverage
.venv/bin/python -m pytest tests/ -v --cov=aqi --cov=api --cov=app --cov-report=term-missing

# Run individual test modules
.venv/bin/python -m pytest tests/test_aqi.py -v
.venv/bin/python -m pytest tests/test_api.py -v
.venv/bin/python -m pytest tests/test_app.py -v

# Run static checks
.venv/bin/ruff check .
```

All API integration and Flask client tests run offline using `unittest.mock` so suites stay fast and deterministic.

## 9. Security Considerations

- Strict `Content-Security-Policy` (`default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`) with zero external script, font, style, or tile origins.
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Permissions-Policy`.
- Regex, type, length (`[:100]`), and coordinate-range validation before outbound API calls.
- Bounded in-process `OrderedDict` cache (200-entry limit) preventing unbounded memory growth.
- Dynamic DOM text rendered safely via text nodes / HTML escaping; health sensitivity profiles and pinned comparison cities stay client-side in `localStorage` with zero server-side tracking.

## 10. Responsive Design & Size Constraint

| Viewport width | Layout |
|---|---|
| 320–767 px | Single-column dashboard, horizontally scrollable comparison table |
| 768–1023 px | Three-column pollutant, ventilation, and comparator grids |
| 1024 px and above | Expanded desktop layout and chart sizing |

Designed to remain strictly below the **10 MB** submission limit:

```bash
du -sh --exclude=__pycache__ --exclude='*.pyc' --exclude=.venv --exclude=.git .
```

## 11. Health Information Disclaimer

Health recommendations provided by Breathe-Better are for general informational purposes only and do not constitute medical advice, diagnosis, or treatment. Consult a qualified healthcare professional for individual medical concerns.

---

**Breathe-Better**
Urban Air Quality Assistant
Data services: [Open-Meteo](https://open-meteo.com/) · Methodology: Central Pollution Control Board (CPCB), India National AQI.
