'use strict';

/* ============================================================
   Breathe-Better — app.js
   Vanilla JS · ES6+ · No external dependencies
   ============================================================ */

// ── Config ──────────────────────────────────────────────────
const CFG = {
  debounceMs:     300,
  maxRecent:      5,
  KEY_RECENT:     'bb_recent_cities',
  KEY_LAST:       'bb_last_result',
  OLD_RECENT:     'bs_recent_cities',
  OLD_LAST:       'bs_last_result',
};

// ── DOM helpers ─────────────────────────────────────────────
const $  = id  => document.getElementById(id);

const DOM = {
  input:          $('city-input'),
  searchBtn:      $('search-btn'),
  suggestions:    $('suggestions-list'),
  liveRegion:     $('live-region'),
  errorPanel:     $('error-panel'),
  errorMsg:       $('error-msg'),
  btnRetry:       $('btn-retry'),
  skeleton:       $('skeleton'),
  results:        $('results'),
  emptyState:     $('empty-state'),
  recentCities:   $('recent-cities'),
  recentList:     $('recent-list'),
  // Alerts
  alertBanner:    $('aqi-alert-banner'),
  alertTitle:     $('alert-title'),
  alertDesc:      $('alert-desc'),
  // AQI card
  cityName:       $('aqi-heading'),
  aqiTime:        $('aqi-time'),
  cacheBadge:     $('cache-badge'),
  aqiGauge:       $('aqi-gauge'),
  aqiNumber:      $('aqi-number'),
  aqiLabel:       $('aqi-label'),
  dominant:       $('dominant-pollutant'),
  // Pollutants
  pollutantsGrid: $('pollutants-grid'),
  // Recommendation
  recIcon:        $('rec-icon'),
  recHeadline:    $('rec-headline'),
  recDetail:      $('rec-detail'),
  recPrecautions: $('rec-precautions'),
  // Chart with Vertical Scale
  chartSection:   $('chart-section'),
  chartLine:      $('chart-line'),
  chartArea:      $('chart-area'),
  yScaleTop:      $('y-scale-top'),
  yScaleMid:      $('y-scale-mid'),
  yScaleBot:      $('y-scale-bot'),
  labelStart:     $('chart-label-start'),
  labelMid:       $('chart-label-mid'),
  labelEnd:       $('chart-label-end'),
};

// ── State ───────────────────────────────────────────────────
let _abort        = null;   // AbortController for in-flight fetch
let _lastLocation = null;   // { lat, lon, cityName } for Retry

// ── Utilities ───────────────────────────────────────────────
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/** Screen-reader live announcement (small delay so region resets). */
function announce(msg) {
  DOM.liveRegion.textContent = '';
  setTimeout(() => { DOM.liveRegion.textContent = msg; }, 60);
}

/** Safe HTML escape — never use innerHTML with user input directly. */
function esc(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(String(str ?? '')));
  return d.innerHTML;
}

// ── Storage ─────────────────────────────────────────────────
const Store = {
  getRecent() {
    try {
      const saved = localStorage.getItem(CFG.KEY_RECENT) || localStorage.getItem(CFG.OLD_RECENT);
      return JSON.parse(saved || '[]');
    } catch {
      return [];
    }
  },
  addRecent(loc) {
    const list = this.getRecent()
      .filter(r => !(r.name === loc.name && r.lat === loc.lat));
    list.unshift(loc);
    try {
      localStorage.setItem(CFG.KEY_RECENT, JSON.stringify(list.slice(0, CFG.maxRecent)));
    } catch { /* storage full — ignore */ }
  },
  getLast() {
    try {
      const saved = localStorage.getItem(CFG.KEY_LAST) || localStorage.getItem(CFG.OLD_LAST);
      return JSON.parse(saved || 'null');
    } catch {
      return null;
    }
  },
  setLast(data) {
    try {
      localStorage.setItem(CFG.KEY_LAST, JSON.stringify(data));
    } catch { /* ignore */ }
  },
};

// ── UI state helpers ────────────────────────────────────────
function showSkeleton() {
  DOM.skeleton.hidden   = false;
  DOM.results.hidden    = true;
  DOM.errorPanel.hidden = true;
  DOM.emptyState.hidden = true;
}

function showResults() {
  DOM.skeleton.hidden   = true;
  DOM.results.hidden    = false;
  DOM.errorPanel.hidden = true;
  DOM.emptyState.hidden = true;
}

function showError(msg) {
  DOM.skeleton.hidden   = true;
  DOM.results.hidden    = true;
  DOM.errorPanel.hidden = false;
  DOM.emptyState.hidden = true;
  DOM.errorMsg.textContent = msg;
  announce('Error: ' + msg);
}

function showEmpty() {
  DOM.skeleton.hidden   = true;
  DOM.results.hidden    = true;
  DOM.errorPanel.hidden = true;
  DOM.emptyState.hidden = false;
  renderRecentCities();
}

// ── Autocomplete ─────────────────────────────────────────────
function closeSuggestions() {
  DOM.suggestions.hidden = true;
  DOM.suggestions.innerHTML = '';
  DOM.input.setAttribute('aria-expanded', 'false');
}

async function fetchSuggestions(query) {
  if (query.length < 2) { closeSuggestions(); return; }
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
    if (!res.ok) { closeSuggestions(); return; }
    const list = await res.json();
    if (!Array.isArray(list) || !list.length) { closeSuggestions(); return; }
    renderSuggestions(list);
  } catch { closeSuggestions(); }
}

function renderSuggestions(list) {
  DOM.suggestions.innerHTML = '';
  list.forEach((loc, i) => {
    const li = document.createElement('li');
    li.setAttribute('role', 'option');
    li.id = `sug-${i}`;
    li.className = 'suggestion-item';
    li.setAttribute('tabindex', '0');
    const label = [loc.name, loc.admin1, loc.country].filter(Boolean).join(', ');
    li.textContent = label;

    const pick = () => {
      DOM.input.value = label;
      closeSuggestions();
      loadAirQuality(loc.latitude, loc.longitude, label);
    };

    li.addEventListener('click', pick);
    li.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); }
      if (e.key === 'Escape')     { closeSuggestions(); DOM.input.focus(); }
      if (e.key === 'ArrowDown')  { const n = li.nextElementSibling;     if (n) n.focus(); }
      if (e.key === 'ArrowUp')    { const p = li.previousElementSibling; if (p) p.focus(); else DOM.input.focus(); }
    });
    DOM.suggestions.appendChild(li);
  });
  DOM.suggestions.hidden = false;
  DOM.input.setAttribute('aria-expanded', 'true');
}

// ── Air Quality fetch ────────────────────────────────────────
async function loadAirQuality(lat, lon, cityName) {
  if (_abort) _abort.abort();
  _abort = new AbortController();
  _lastLocation = { lat, lon, cityName };

  showSkeleton();
  announce(`Loading air quality data for ${cityName}…`);

  try {
    const url =
      `/api/air-quality` +
      `?lat=${encodeURIComponent(lat)}` +
      `&lon=${encodeURIComponent(lon)}` +
      `&city=${encodeURIComponent(cityName)}`;

    const res = await fetch(url, { signal: _abort.signal });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error (${res.status})`);
    }

    const data = await res.json();
    Store.addRecent({ name: cityName, lat, lon });
    Store.setLast(data);
    renderResults(data);
    announce(
      `Loaded. AQI for ${cityName}: ${data.aqi?.aqi ?? 'N/A'} — ${data.aqi?.category ?? 'Unknown'}.`
    );
  } catch (err) {
    if (err.name === 'AbortError') return;
    showError(err.message || 'Could not load air quality data. Check your connection and try again.');
  }
}

// ── Render helpers ───────────────────────────────────────────
const POLLUTANT_META = {
  pm2_5: { label: 'PM2.5', unit: 'µg/m³', desc: 'Fine particulate matter'  },
  pm10:  { label: 'PM10',  unit: 'µg/m³', desc: 'Coarse particulate matter' },
  no2:   { label: 'NO₂',   unit: 'µg/m³', desc: 'Nitrogen dioxide'          },
  o3:    { label: 'O₃',    unit: 'µg/m³', desc: 'Ground-level ozone'        },
  co:    { label: 'CO',    unit: 'mg/m³',  desc: 'Carbon monoxide'           },
  so2:   { label: 'SO₂',   unit: 'µg/m³', desc: 'Sulphur dioxide'           },
};

function getSubIndexCategoryClass(si) {
  if (si == null) return '';
  if (si <= 50)  return 'si-good';
  if (si <= 100) return 'si-satisfactory';
  if (si <= 200) return 'si-moderate';
  if (si <= 300) return 'si-poor';
  if (si <= 400) return 'si-very-poor';
  return 'si-severe';
}

function renderResults(data) {
  renderAQIAlert(data.aqi);
  renderAQICard(data);
  renderPollutants(data.current, data.aqi?.sub_indices || {});
  renderRecommendation(data.recommendation);
  renderChart(data.hourly);
  showResults();
}

function renderAQIAlert(aqi) {
  const aqiVal = aqi?.aqi;
  // Reserve red alert banner strictly for unhealthy values: Poor (201+), Very Poor (301+), Severe (401+)
  if (aqiVal != null && aqiVal > 200) {
    DOM.alertBanner.hidden = false;
    if (aqiVal > 400) {
      DOM.alertTitle.textContent = 'Emergency Alert: Severe Air Quality';
      DOM.alertDesc.textContent  = 'Extreme pollution levels. Avoid all outdoor activities and remain indoors with filtration.';
    } else if (aqiVal > 300) {
      DOM.alertTitle.textContent = 'Health Warning: Very Poor Air Quality';
      DOM.alertDesc.textContent  = 'Hazardous pollution conditions. Avoid prolonged outdoor exertion and wear N95 protection.';
    } else {
      DOM.alertTitle.textContent = 'Health Advisory: Poor Air Quality';
      DOM.alertDesc.textContent  = 'Unhealthy air for sensitive individuals. Consider reducing prolonged outdoor activities.';
    }
  } else {
    DOM.alertBanner.hidden = true;
  }
}

function renderAQICard(data) {
  const { city, aqi, timestamp, cached } = data;

  DOM.cityName.textContent = city || 'Unknown';
  DOM.cacheBadge.hidden = !cached;

  // Prominent timestamp formatting
  if (timestamp) {
    try {
      const dt = new Date(timestamp);
      DOM.aqiTime.textContent = dt.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      DOM.aqiTime.setAttribute('datetime', dt.toISOString());
    } catch {
      DOM.aqiTime.textContent = timestamp;
    }
  }

  // Set AQI indicator (reduced glow, crisp prominent circular badge)
  if (aqi?.aqi != null) {
    DOM.aqiNumber.textContent = aqi.aqi;
    DOM.aqiLabel.textContent  = aqi.category;
    DOM.aqiGauge.style.setProperty('--aqi-color', aqi.color || '#64748b');
    DOM.aqiGauge.setAttribute('aria-label', `AQI ${aqi.aqi} – ${aqi.category}`);
  } else {
    DOM.aqiNumber.textContent = 'N/A';
    DOM.aqiLabel.textContent  = 'Unknown';
    DOM.aqiGauge.style.setProperty('--aqi-color', '#64748b');
    DOM.aqiGauge.setAttribute('aria-label', 'AQI data unavailable');
  }

  const dp = aqi?.dominant_pollutant;
  DOM.dominant.textContent = dp ? (POLLUTANT_META[dp]?.label || dp) : 'N/A';
}

function renderPollutants(current, subIndices) {
  DOM.pollutantsGrid.innerHTML = '';
  Object.entries(POLLUTANT_META).forEach(([key, meta]) => {
    const val = current?.[key];
    const si  = subIndices?.[key];
    const displayVal = val != null
      ? (key === 'co' ? val.toFixed(2) : val.toFixed(1))
      : '—';

    const card = document.createElement('div');
    card.className = 'pollutant-card';
    card.setAttribute('role', 'listitem');
    card.setAttribute('aria-label',
      `${meta.label}: ${val != null ? displayVal + ' ' + meta.unit : 'data unavailable'}`);

    const siClass = getSubIndexCategoryClass(si);
    const siBadge = si != null
      ? `<span class="pollutant-si-badge ${siClass}">Sub-Index: ${Math.round(si)}</span>`
      : `<span class="pollutant-si-badge">SI: —</span>`;

    card.innerHTML =
      `<div class="pollutant-card-top">` +
        `<span class="pollutant-name">${esc(meta.label)}</span>` +
        siBadge +
      `</div>` +
      `<div class="pollutant-desc">${esc(meta.desc)}</div>` +
      `<div class="pollutant-val-row">` +
        `<span class="pollutant-value">${esc(displayVal)}</span>` +
        `<span class="pollutant-unit">${esc(meta.unit)}</span>` +
      `</div>`;

    DOM.pollutantsGrid.appendChild(card);
  });
}

function renderRecommendation(rec) {
  if (!rec) return;
  DOM.recIcon.textContent     = rec.icon     || 'ℹ️';
  DOM.recHeadline.textContent = rec.headline || 'Health Guidance';
  DOM.recDetail.textContent   = rec.detail   || '';
  DOM.recPrecautions.innerHTML = (rec.precautions || [])
    .map(p => `<li>${esc(p)}</li>`).join('');
}

function renderChart(hourly) {
  const times  = hourly?.time   || [];
  const values = hourly?.pm2_5  || [];

  // Pair times with values, drop null/undefined
  const pairs = times
    .map((t, i) => [t, values[i]])
    .filter(([, v]) => v != null);

  if (pairs.length < 2) {
    DOM.chartSection.hidden = true;
    return;
  }
  DOM.chartSection.hidden = false;

  const vals  = pairs.map(([, v]) => v);
  let minV    = Math.floor(Math.min(...vals));
  let maxV    = Math.ceil(Math.max(...vals));
  if (minV < 0) minV = 0;
  if (maxV <= minV) maxV = minV + 10;

  const midV = Math.round((maxV + minV) / 2);

  // Set vertical scale Y-axis labels with clear units
  DOM.yScaleTop.textContent = `${maxV}`;
  DOM.yScaleMid.textContent = `${midV}`;
  DOM.yScaleBot.textContent = `${minV}`;

  // SVG dimensions: viewBox 0 0 500 160
  // Chart plotting range: X: 68 to 490, Y: 20 (top) to 140 (bottom)
  const X_START = 68;
  const X_END   = 490;
  const Y_TOP   = 20;
  const Y_BOT   = 140;

  const toX = i => X_START + (i / (pairs.length - 1)) * (X_END - X_START);
  const toY = v => Y_BOT - ((v - minV) / (maxV - minV)) * (Y_BOT - Y_TOP);

  const ptStr = pairs
    .map(([, v], i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`)
    .join(' ');

  DOM.chartLine.setAttribute('points', ptStr);

  // Area fill: bottom-left → curve points → bottom-right → close
  const areaPath =
    `M${X_START.toFixed(1)},${Y_BOT} ` +
    ptStr.split(' ').map(p => `L${p}`).join(' ') +
    ` L${X_END.toFixed(1)},${Y_BOT} Z`;
  DOM.chartArea.setAttribute('d', areaPath);

  // Horizontal time labels
  DOM.labelStart.textContent = fmtTime(pairs[0][0]);
  DOM.labelMid.textContent   = fmtTime(pairs[Math.floor(pairs.length / 2)][0]);
  DOM.labelEnd.textContent   = fmtTime(pairs[pairs.length - 1][0]);
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch { return iso || ''; }
}

// ── Recent cities ────────────────────────────────────────────
function renderRecentCities() {
  const recent = Store.getRecent();
  if (!recent.length) { DOM.recentCities.hidden = true; return; }
  DOM.recentCities.hidden = false;
  DOM.recentList.innerHTML = '';

  recent.forEach(loc => {
    const btn = document.createElement('button');
    btn.className = 'recent-city-btn';
    btn.textContent = loc.name;
    btn.setAttribute('aria-label', `Search again for ${loc.name}`);
    btn.addEventListener('click', () => {
      DOM.input.value = loc.name;
      loadAirQuality(loc.lat, loc.lon, loc.name);
    });
    DOM.recentList.appendChild(btn);
  });
}

// ── Search helpers ───────────────────────────────────────────
async function fetchAndSelectFirst(query) {
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
    if (!res.ok) {
      showError('Could not reach the search service. Please try again.');
      return;
    }
    const list = await res.json();
    if (!Array.isArray(list) || !list.length) {
      showError(`No results found for "${query}". Try a different spelling or city name.`);
      return;
    }
    const loc   = list[0];
    const label = [loc.name, loc.admin1, loc.country].filter(Boolean).join(', ');
    DOM.input.value = label;
    loadAirQuality(loc.latitude, loc.longitude, label);
  } catch {
    showError('Could not search for cities. Please check your connection.');
  }
}

// ── Event listeners ──────────────────────────────────────────
const debouncedSuggest = debounce(q => fetchSuggestions(q), CFG.debounceMs);

DOM.input.addEventListener('input', () => {
  const q = DOM.input.value.trim();
  if (q.length >= 2) debouncedSuggest(q);
  else closeSuggestions();
});

DOM.input.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    closeSuggestions();
    const q = DOM.input.value.trim();
    if (q) fetchAndSelectFirst(q);
  }
  if (e.key === 'ArrowDown') {
    const first = DOM.suggestions.querySelector('.suggestion-item');
    if (first) { e.preventDefault(); first.focus(); }
  }
  if (e.key === 'Escape') closeSuggestions();
});

DOM.searchBtn.addEventListener('click', () => {
  const q = DOM.input.value.trim();
  closeSuggestions();
  if (q) fetchAndSelectFirst(q);
});

DOM.btnRetry.addEventListener('click', () => {
  if (_lastLocation) {
    loadAirQuality(_lastLocation.lat, _lastLocation.lon, _lastLocation.cityName);
  } else {
    showEmpty();
  }
});

// Close suggestions when clicking outside
document.addEventListener('click', e => {
  if (!DOM.suggestions.contains(e.target) && e.target !== DOM.input) {
    closeSuggestions();
  }
});

// ── Initialise ───────────────────────────────────────────────
function init() {
  showEmpty();
  // Restore last viewed city query if present
  const last = Store.getLast();
  if (last?.city) {
    DOM.input.value = last.city;
  }
}

init();
