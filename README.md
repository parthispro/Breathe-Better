# Breathe-Better
### Urban Air Quality Assistant

Breathe-Better is a lightweight, responsive web application that retrieves air-quality data for a selected location and presents it through AQI measurements, pollutant breakdowns, health recommendations, and historical trends.

The application is designed to make environmental data easier to interpret while providing transparency about data sources, update times, and availability.

---

## 1. Features

- **Location-based monitoring:** Search for a city or location to retrieve its air-quality information.
- **AQI calculation:** Calculate the India National Air Quality Index using CPCB methodology.
- **Pollutant analysis:** Display individual pollutant measurements and their corresponding sub-indices.
- **Health recommendations:** Present precautionary guidance based on the AQI category.
- **Historical trends:** Visualize available PM2.5 measurements over time.
- **Data transparency:** Display data sources, update timestamps, and cache status.
- **Responsive interface:** Support desktop, tablet, and mobile screen sizes.

## 2. Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python, Flask |
| Air-quality data | Open-Meteo Air Quality API |
| Location search | Open-Meteo Geocoding API |
| HTTP client | Requests / HTTPX |
| Data visualization | Native SVG and CSS |
| Client-side storage | Browser LocalStorage |
| Testing | Pytest |
| Code quality | Ruff |

**External API credentials:** No API key is required for the configured Open-Meteo endpoints.

## 3. Quick Start

### Prerequisites

- Python 3.14 or later for the synchronous configuration.
- Git (optional, for cloning the repository).
- An internet connection for external API requests.

### Python 3.14 — Standard Configuration

```bash
git clone <repository-url>
cd Breathe-Better

pip install -r requirements-py314.txt
python3 app.py
```

### Python 3.15 — Asynchronous Configuration

```bash
git clone <repository-url>
cd Breathe-Better

pip install -r requirements-py315.txt
python3 app.py
```

Open the following address in your browser:

```text
http://localhost:5000
```

### Dependency Configuration

| Requirements file | Python version | HTTP client | Configuration |
|---|---|---|---|
| `requirements-py314.txt` | 3.14+ | Requests | Synchronous |
| `requirements-py315.txt` | 3.15+ | HTTPX | Asynchronous, HTTP/2 |
| `requirements.txt` | 3.14+ | Requests | Default configuration |

The requirements files provide alternative dependency configurations for the application.

## 4. Project Architecture

The application follows a modular client-server architecture.

```text
                 User
                  |
                  v
          Web Application
          HTML / CSS / JS
                  |
                  v
             Flask Server
                  |
          +-------+-------+
          |               |
          v               v
       api.py           aqi.py
          |               |
          v               v
     Open-Meteo       AQI Calculation
       APIs           & Recommendations
          |               |
          +-------+-------+
                  |
                  v
          Processed AQI Data
                  |
                  v
          Frontend Rendering
```

### Core Components

| Module | Responsibility |
|---|---|
| `app.py` | Flask application, HTTP routes, caching, and response security headers |
| `api.py` | External API communication, location search, and air-quality data retrieval |
| `aqi.py` | AQI sub-index calculations, category classification, and recommendations |
| `templates/index.html` | Application interface structure |
| `static/style.css` | Responsive styling and AQI-related visual elements |
| `static/app.js` | API requests, interface rendering, autocomplete, and LocalStorage handling |

## 5. Project Structure

```text
Breathe-Better/
│
├── app.py
├── api.py
├── aqi.py
│
├── requirements.txt
├── requirements-py314.txt
├── requirements-py315.txt
│
├── templates/
│   └── index.html
│
├── static/
│   ├── style.css
│   └── app.js
│
└── tests/
    ├── test_aqi.py
    └── test_api.py
```

## 6. Air Quality Index Methodology

Breathe-Better implements the India National Air Quality Index methodology published by the Central Pollution Control Board (CPCB).

The application processes supported pollutant measurements and calculates their respective sub-indices using the configured CPCB breakpoint ranges.

### Supported Pollutants

| Pollutant | Measurement unit | Description |
|---|---|---|
| PM2.5 | µg/m³ | Fine particulate matter |
| PM10 | µg/m³ | Coarse particulate matter |
| NO₂ | µg/m³ | Nitrogen dioxide |
| O₃ | µg/m³ | Ozone |
| CO | mg/m³ | Carbon monoxide |
| SO₂ | µg/m³ | Sulphur dioxide |

### AQI Categories

| AQI range | Category |
|---|---|
| 0–50 | Good |
| 51–100 | Satisfactory |
| 101–200 | Moderate |
| 201–300 | Poor |
| 301–400 | Very Poor |
| 401–500 | Severe |

The overall AQI is determined using the highest valid pollutant sub-index, subject to the applicable CPCB calculation and data-availability requirements.

**Note:** Correct AQI calculation depends on pollutant-specific breakpoints, averaging periods, units, and data validity. The presence of a pollutant measurement alone does not establish that a valid sub-index can be calculated.

## 7. Data Sources

The application uses Open-Meteo for external environmental and geographical data.

| Service | Purpose | Documentation |
|---|---|---|
| Open-Meteo Air Quality API | Pollutant measurements and air-quality data | [API Documentation](https://open-meteo.com/en/docs/air-quality-api) |
| Open-Meteo Geocoding API | Location search and geographical coordinates | [API Documentation](https://open-meteo.com/en/docs/geocoding-api) |

Both configured services can be used without an API key.

Data availability, timestamps, and whether measurements are modelled or station-observed must be interpreted according to the underlying provider's documentation. Open-Meteo data should not automatically be represented as direct CPCB monitoring-station observations.

## 8. Testing and Code Quality

The project uses Pytest for automated testing and Ruff for static code-quality checks.

### Run the complete test suite

```bash
python3 -m pytest tests/ -v \
    --cov=aqi \
    --cov=api \
    --cov-report=term-missing
```

### Run AQI calculation tests

```bash
python3 -m pytest tests/test_aqi.py -v
```

### Run API tests

```bash
python3 -m pytest tests/test_api.py -v
```

API integration tests use mocks to validate client behaviour without requiring external network requests.

### Run static checks

```bash
python3 -m ruff check .
```

The testing strategy covers:

- AQI calculations and category classification.
- Pollutant sub-index calculations.
- API response handling.
- Missing and invalid data.
- Error handling and external API failures.

## 9. Security Considerations

The application incorporates the following security measures:

- Content Security Policy (CSP) response header.
- Input validation before external API requests.
- Input length restrictions and format validation.
- `X-Frame-Options: DENY`.
- `X-Content-Type-Options: nosniff`.
- `Referrer-Policy: no-referrer`.
- Safe rendering of dynamic frontend content using DOM text nodes.
- No API credentials embedded in application source code.

These controls are intended to reduce common web application security risks. Their effectiveness should be verified through implementation review and testing.

## 10. Responsive Design

The frontend uses a responsive layout to support different device sizes.

| Viewport width | Layout |
|---|---|
| 320–767 px | Single-column layout |
| 768–1023 px | Two- or three-column pollutant grid |
| 1024 px and above | Expanded pollutant grid and chart layout |

The interface is designed with mobile usability, readable information hierarchy, and accessible interactions in mind.

## 11. Performance and Deployment Constraints

The application is designed to minimize unnecessary dependencies and keep its runtime footprint small.

Performance considerations include:

- Lightweight frontend implementation without a large JavaScript framework.
- Server-side caching with a configured TTL.
- Efficient external API requests.
- Minimal client-side dependencies.
- Native SVG-based data visualization.

Performance targets should be evaluated using actual measurements under documented network and hardware conditions.

### Submission Size

The project has a submission archive limit of 10 MB.

Recommended internal target: less than 7 MB.

Check the project directory size:

```bash
du -sh \
    --exclude=__pycache__ \
    --exclude='*.pyc' \
    --exclude=.venv .
```

Exclude virtual environments, generated caches, and other unnecessary development files from the submission archive.

## 12. Health Information Disclaimer

Health recommendations provided by Breathe-Better are intended for general informational purposes only.

They do not constitute medical advice, diagnosis, or treatment recommendations. Users should consult qualified healthcare professionals for individual medical concerns.

---

**Breathe-Better**  
Urban Air Quality Assistant

Data services: [Open-Meteo](https://open-meteo.com/)  
AQI methodology reference: Central Pollution Control Board (CPCB), India National AQI.
