'use strict';

const CFG = {
  debounceMs:  300,
  maxRecent:   5,
  maxPinned:   4,
  KEY_RECENT:  'bb_recent_cities',
  KEY_LAST:    'bb_last_result',
  KEY_PROFILE: 'bb_age_profile',
  KEY_PINNED:  'bb_pinned_cities',
  OLD_RECENT:  'bs_recent_cities',
  OLD_LAST:    'bs_last_result',
};

const COMPARE_PRESETS = [
  { name: 'Delhi, India',  lat: 28.652,  lon: 77.2315 },
  { name: 'Jaipur, India', lat: 26.9124, lon: 75.7873 },
  { name: 'Mumbai, India', lat: 19.076,  lon: 72.8777 },
];

const ICON_PLUS =
  '<svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">' +
  '<path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';

const ICON_REMOVE =
  '<svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">' +
  '<path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';

const SENSITIVE_PROFILES = new Set(['kids_0_4', 'kids_5_12', 'seniors', 'asthmatic']);

const PROFILE_TO_GUIDANCE_KEY = {
  overall:   'overall',
  kids_0_4:  'infants_toddlers',
  kids_5_12: 'kids_school',
  teens:     'teens',
  seniors:   'seniors',
  asthmatic: 'asthmatic',
};

const PROFILE_LABELS = {
  overall:   'Overall Population',
  kids_0_4:  'Infants & Toddlers (0–4 yrs)',
  kids_5_12: 'School-Age Kids (5–12 yrs)',
  teens:     'Teens & Sports (13–17 yrs)',
  seniors:   'Seniors (60+ yrs)',
  asthmatic: 'Asthmatic & Respiratory',
};

const $ = id => document.getElementById(id);

const DOM = {
  input:              $('city-input'),
  searchBtn:          $('search-btn'),
  suggestions:        $('suggestions-list'),
  liveRegion:         $('live-region'),
  errorPanel:         $('error-panel'),
  errorMsg:           $('error-msg'),
  btnRetry:           $('btn-retry'),
  skeleton:           $('skeleton'),
  results:            $('results'),
  emptyState:         $('empty-state'),
  btnOpenCompare:     $('btn-open-compare'),
  recentCities:       $('recent-cities'),
  recentList:         $('recent-list'),
  tabOverview:        $('tab-overview'),
  tabCompare:         $('tab-compare'),
  overviewPanel:      $('overview-panel'),
  comparePanel:       $('compare-panel'),
  alertBanner:        $('aqi-alert-banner'),
  alertTitle:         $('alert-title'),
  alertDesc:          $('alert-desc'),
  cityName:           $('aqi-heading'),
  aqiTime:            $('aqi-time'),
  cacheBadge:         $('cache-badge'),
  btnPinCity:         $('btn-pin-city'),
  aqiGauge:           $('aqi-gauge'),
  aqiNumber:          $('aqi-number'),
  aqiLabel:           $('aqi-label'),
  dominant:           $('dominant-pollutant'),
  pollutantsGrid:     $('pollutants-grid'),
  ventSection:        $('ventilation-section'),
  ventTier:           $('vent-tier'),
  ventVc:             $('vent-vc'),
  ventWind:           $('vent-wind'),
  ventPbl:            $('vent-pbl'),
  compSection:        $('comparator-section'),
  compCpcbScore:      $('comp-cpcb-score'),
  compCpcbCat:        $('comp-cpcb-cat'),
  compCpcbScale:      $('comp-cpcb-scale'),
  compCpcbDot:        $('comp-cpcb-dot'),
  compUsScore:        $('comp-us-score'),
  compUsCat:          $('comp-us-cat'),
  compUsScale:        $('comp-us-scale'),
  compUsDot:          $('comp-us-dot'),
  compEuScore:        $('comp-eu-score'),
  compEuCat:          $('comp-eu-cat'),
  compEuScale:        $('comp-eu-scale'),
  compEuDot:          $('comp-eu-dot'),
  compNote:           $('comp-note'),
  profileBar:         $('profile-bar'),
  profilePills:       Array.from(document.querySelectorAll('.profile-pill')),
  recHeadline:        $('rec-headline'),
  recDetail:          $('rec-detail'),
  recPrecautions:     $('rec-precautions'),
  kidsTiers:          $('kids-tiers'),
  chartSection:       $('chart-section'),
  chartLine:          $('chart-line'),
  chartArea:          $('chart-area'),
  yScaleTop:          $('y-scale-top'),
  yScaleMid:          $('y-scale-mid'),
  yScaleBot:          $('y-scale-bot'),
  labelStart:         $('chart-label-start'),
  labelMid:           $('chart-label-mid'),
  labelEnd:           $('chart-label-end'),
  btnPresetCompare:   $('btn-preset-compare'),
  btnClearPins:       $('btn-clear-pins'),
  compareInput:       $('compare-city-input'),
  compareAddBtn:      $('compare-add-btn'),
  compareSuggestions: $('compare-suggestions'),
  compareSubtitle:    $('compare-subtitle'),
  sharedGridNotice:   $('shared-grid-warning'),
  compareStatus:      $('compare-status'),
  compareTbody:       $('compare-tbody'),
};

let _abort        = null;
let _lastLocation = null;
let _lastData     = null;
let _compareDirty = true;

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function announce(msg) {
  DOM.liveRegion.textContent = '';
  setTimeout(() => { DOM.liveRegion.textContent = msg; }, 60);
}

function esc(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(String(str ?? '')));
  return d.innerHTML;
}

function sameCoord(a, b) {
  return Math.abs(Number(a.lat) - Number(b.lat)) < 0.01 &&
         Math.abs(Number(a.lon) - Number(b.lon)) < 0.01;
}

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
    } catch { /* storage full */ }
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
  getProfile() {
    try {
      const p = localStorage.getItem(CFG.KEY_PROFILE) || 'overall';
      return PROFILE_TO_GUIDANCE_KEY[p] ? p : 'overall';
    } catch {
      return 'overall';
    }
  },
  setProfile(profile) {
    try {
      localStorage.setItem(CFG.KEY_PROFILE, profile);
    } catch { /* ignore */ }
  },
  hasCustomCompare() {
    try {
      return localStorage.getItem(CFG.KEY_PINNED) !== null;
    } catch {
      return false;
    }
  },
  getPinned() {
    try {
      const raw = JSON.parse(localStorage.getItem(CFG.KEY_PINNED) || '[]');
      return Array.isArray(raw) ? raw.slice(0, CFG.maxPinned) : [];
    } catch {
      return [];
    }
  },
  savePinned(list) {
    try {
      localStorage.setItem(CFG.KEY_PINNED, JSON.stringify(list.slice(0, CFG.maxPinned)));
    } catch { /* ignore */ }
  },
  getActiveCompare(currentData) {
    if (this.hasCustomCompare()) {
      return this.getPinned();
    }
    const list = [];
    if (currentData && currentData.lat != null && currentData.lon != null) {
      list.push({ name: currentData.city || 'Current', lat: currentData.lat, lon: currentData.lon });
    }
    for (const preset of COMPARE_PRESETS) {
      if (list.length >= 3) break;
      if (!list.some(c => sameCoord(c, preset))) {
        list.push(preset);
      }
    }
    return list.slice(0, CFG.maxPinned);
  },
  addCompareCity(loc, currentData) {
    const list = [...this.getActiveCompare(currentData)];
    if (list.some(c => sameCoord(c, loc))) {
      return { ok: true, already: true, list };
    }
    if (list.length >= CFG.maxPinned) {
      return { ok: false, reason: 'max', list };
    }
    list.push(loc);
    this.savePinned(list);
    return { ok: true, already: false, list };
  },
  removeCompareCity(lat, lon, currentData) {
    const list = this.getActiveCompare(currentData).filter(c => !sameCoord(c, { lat, lon }));
    this.savePinned(list);
    return list;
  },
  setPresetsCompare() {
    this.savePinned(COMPARE_PRESETS);
  },
  clearPinned() {
    this.savePinned([]);
  },
};

function isInCompare(lat, lon) {
  return Store.getActiveCompare(_lastData).some(c => sameCoord(c, { lat, lon }));
}

function updateCompareTabLabel() {
  const count = Store.getActiveCompare(_lastData).length;
  DOM.tabCompare.textContent = count > 0 ? `Compare Cities (${count})` : 'Compare Cities';
}

function showSkeleton() {
  DOM.skeleton.hidden    = false;
  DOM.results.hidden     = true;
  DOM.errorPanel.hidden  = true;
  DOM.emptyState.hidden  = true;
  DOM.alertBanner.hidden = true;
  DOM.alertBanner.style.display = 'none';
}

function showResults() {
  DOM.skeleton.hidden   = true;
  DOM.results.hidden    = false;
  DOM.errorPanel.hidden = true;
  DOM.emptyState.hidden = true;
}

function showError(msg) {
  DOM.skeleton.hidden    = true;
  DOM.results.hidden     = true;
  DOM.errorPanel.hidden  = false;
  DOM.emptyState.hidden  = true;
  DOM.alertBanner.hidden = true;
  DOM.alertBanner.style.display = 'none';
  DOM.errorMsg.textContent = msg;
  announce('Error: ' + msg);
}

function showEmpty() {
  DOM.skeleton.hidden    = true;
  DOM.results.hidden     = true;
  DOM.errorPanel.hidden  = true;
  DOM.emptyState.hidden  = false;
  DOM.alertBanner.hidden = true;
  DOM.alertBanner.style.display = 'none';
  renderRecentCities();
}

function closeSuggestions(listEl = DOM.suggestions, inputEl = DOM.input) {
  listEl.hidden    = true;
  listEl.innerHTML = '';
  inputEl.setAttribute('aria-expanded', 'false');
}

function applyCompareToggle(loc) {
  const inList = isInCompare(loc.latitude, loc.longitude);
  const cityObj = { name: loc.label, lat: loc.latitude, lon: loc.longitude };

  if (inList) {
    Store.removeCompareCity(loc.latitude, loc.longitude, _lastData);
    _compareDirty = true;
    announce(`Removed ${loc.label} from comparison.`);
  } else {
    const res = Store.addCompareCity(cityObj, _lastData);
    if (!res.ok && res.reason === 'max') {
      const msg = `Comparison limit is ${CFG.maxPinned} cities. Remove a city first to add ${loc.label}.`;
      announce(msg);
      if (!DOM.comparePanel.hidden) {
        DOM.compareStatus.hidden      = false;
        DOM.compareStatus.textContent = msg;
      }
      return false;
    }
    _compareDirty = true;
    announce(`Added ${loc.label} to comparison.`);
  }

  updateCompareTabLabel();
  if (_lastData) updatePinButton(_lastData);
  if (!DOM.comparePanel.hidden) {
    loadCompare();
  }
  return true;
}

async function fetchSuggestions(query, listEl, inputEl, mode) {
  if (query.length < 2) { closeSuggestions(listEl, inputEl); return; }
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
    if (!res.ok) { closeSuggestions(listEl, inputEl); return; }
    const list = await res.json();
    if (!Array.isArray(list) || !list.length) { closeSuggestions(listEl, inputEl); return; }
    renderSuggestions(list, listEl, inputEl, mode);
  } catch { closeSuggestions(listEl, inputEl); }
}

function renderSuggestions(list, listEl, inputEl, mode) {
  listEl.innerHTML = '';
  list.forEach((loc, i) => {
    const label = [loc.name, loc.admin1, loc.country].filter(Boolean).join(', ');
    const li = document.createElement('li');
    li.setAttribute('role', 'none');
    li.className = 'suggestion-item';

    const pickBtn = document.createElement('button');
    pickBtn.type = 'button';
    pickBtn.setAttribute('role', 'option');
    pickBtn.id = `${mode}-sug-${i}`;
    pickBtn.className = 'suggestion-pick-btn';
    pickBtn.textContent = label;

    const cmpBtn = document.createElement('button');
    cmpBtn.type = 'button';
    cmpBtn.className = 'suggestion-compare-btn';

    const syncCmpBtn = () => {
      const added = isInCompare(loc.latitude, loc.longitude);
      cmpBtn.classList.toggle('in-compare', added);
      cmpBtn.innerHTML = added ? ICON_REMOVE : ICON_PLUS;
      const actionText = added ? `Remove ${label} from comparison` : `Add ${label} to comparison`;
      cmpBtn.setAttribute('aria-label', actionText);
      cmpBtn.setAttribute('title', actionText);
    };
    syncCmpBtn();

    const pickPrimary = () => {
      closeSuggestions(listEl, inputEl);
      if (mode === 'compare') {
        inputEl.value = '';
        if (!isInCompare(loc.latitude, loc.longitude)) {
          applyCompareToggle({ ...loc, label });
        }
      } else {
        inputEl.value = label;
        loadAirQuality(loc.latitude, loc.longitude, label);
      }
    };

    pickBtn.addEventListener('click', pickPrimary);
    cmpBtn.addEventListener('click', e => {
      e.stopPropagation();
      applyCompareToggle({ ...loc, label });
      syncCmpBtn();
    });

    const handleKeyNav = (e, currentBtn) => {
      if (e.key === 'Escape') {
        closeSuggestions(listEl, inputEl);
        inputEl.focus();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const nextRow = li.nextElementSibling;
        if (nextRow) nextRow.querySelector('.suggestion-pick-btn')?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prevRow = li.previousElementSibling;
        if (prevRow) prevRow.querySelector('.suggestion-pick-btn')?.focus();
        else inputEl.focus();
      } else if (e.key === 'ArrowRight' && currentBtn === pickBtn) {
        e.preventDefault();
        cmpBtn.focus();
      } else if (e.key === 'ArrowLeft' && currentBtn === cmpBtn) {
        e.preventDefault();
        pickBtn.focus();
      }
    };

    pickBtn.addEventListener('keydown', e => handleKeyNav(e, pickBtn));
    cmpBtn.addEventListener('keydown',  e => handleKeyNav(e, cmpBtn));

    li.appendChild(pickBtn);
    li.appendChild(cmpBtn);
    listEl.appendChild(li);
  });

  listEl.hidden = false;
  inputEl.setAttribute('aria-expanded', 'true');
}

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

const POLLUTANT_META = {
  pm2_5: { label: 'PM2.5', unit: 'µg/m³', desc: 'Fine particulate matter'  },
  pm10:  { label: 'PM10',  unit: 'µg/m³', desc: 'Coarse particulate matter' },
  no2:   { label: 'NO₂',   unit: 'µg/m³', desc: 'Nitrogen dioxide'          },
  o3:    { label: 'O₃',    unit: 'µg/m³', desc: 'Ground-level ozone'        },
  co:    { label: 'CO',    unit: 'mg/m³', desc: 'Carbon monoxide'           },
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
  _lastData = data;
  _compareDirty = true;
  const profile = Store.getProfile();
  syncProfileUI(profile);
  updateCompareTabLabel();
  renderAQIAlert(data.aqi, profile);
  renderAQICard(data);
  renderPollutants(data.current, data.aqi?.sub_indices || {});
  renderVentilation(data.ventilation);
  renderComparator(data.comparison);
  renderRecommendation(data, profile);
  renderKidsSection(data.age_guidance, profile);
  renderChart(data.hourly);
  switchTab('overview', false);
  showResults();
}

function renderAQIAlert(aqi, profile) {
  const aqiVal = aqi?.aqi;
  if (aqiVal != null && aqiVal > 200) {
    DOM.alertBanner.hidden = false;
    DOM.alertBanner.style.display = 'flex';
    DOM.alertBanner.classList.remove('amber-advisory');
    if (aqiVal > 400) {
      DOM.alertTitle.textContent = 'Emergency Alert: Severe Air Quality';
      DOM.alertDesc.textContent  = 'Extreme pollution levels. Avoid all outdoor activities and remain indoors with filtration.';
    } else if (aqiVal > 300) {
      DOM.alertTitle.textContent = 'Health Warning: Very Poor Air Quality';
      DOM.alertDesc.textContent  = 'Hazardous pollution conditions. Avoid prolonged outdoor exertion indoors where possible.';
    } else {
      DOM.alertTitle.textContent = 'Health Alert: Poor Air Quality';
      DOM.alertDesc.textContent  = 'Unhealthy air. Reduce outdoor exposure; sensitive groups should remain indoors.';
    }
  } else if (aqiVal != null && aqiVal >= 101 && SENSITIVE_PROFILES.has(profile)) {
    DOM.alertBanner.hidden = false;
    DOM.alertBanner.style.display = 'flex';
    DOM.alertBanner.classList.add('amber-advisory');
    const label = PROFILE_LABELS[profile] || 'Sensitive group';
    DOM.alertTitle.textContent = `Sensitive Group Advisory: Moderate AQI (${aqiVal})`;
    DOM.alertDesc.textContent  = `${label}: Limit prolonged outdoor exertion and shift intense activity indoors.`;
  } else {
    DOM.alertBanner.hidden = true;
    DOM.alertBanner.style.display = 'none';
    DOM.alertBanner.classList.remove('amber-advisory');
  }
}

function updatePinButton(data) {
  if (!data || data.lat == null || data.lon == null) return;
  const added = isInCompare(data.lat, data.lon);
  DOM.btnPinCity.innerHTML = added
    ? `${ICON_REMOVE}<span>Remove from Compare</span>`
    : `${ICON_PLUS}<span>Add to Compare</span>`;
  DOM.btnPinCity.classList.toggle('is-pinned', added);
  DOM.btnPinCity.setAttribute('aria-pressed', added ? 'true' : 'false');
}

function renderAQICard(data) {
  const { city, aqi, timestamp, cached } = data;

  DOM.cityName.textContent = city || 'Unknown';
  DOM.cacheBadge.hidden    = !cached;
  updatePinButton(data);

  if (timestamp) {
    try {
      const dt = new Date(timestamp);
      DOM.aqiTime.textContent = dt.toLocaleString([], {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      });
      DOM.aqiTime.setAttribute('datetime', dt.toISOString());
    } catch {
      DOM.aqiTime.textContent = timestamp;
    }
  }

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

function renderVentilation(vent) {
  if (!vent) {
    DOM.ventSection.hidden = true;
    return;
  }
  DOM.ventSection.hidden = false;
  DOM.ventVc.textContent   = `${vent.ventilation_coeff} m²/s`;
  DOM.ventWind.textContent = `${vent.wind_speed_ms} m/s (${vent.wind_direction_compass})`;
  DOM.ventPbl.textContent  = `${vent.boundary_layer_height_m} m`;
  DOM.ventTier.textContent = vent.dispersion_tier;

  DOM.ventTier.className = 'vent-tier-pill';
  if (vent.ventilation_coeff < 3000)      DOM.ventTier.classList.add('tier-high');
  else if (vent.ventilation_coeff < 6000) DOM.ventTier.classList.add('tier-mod');
  else                                    DOM.ventTier.classList.add('tier-good');
}

function renderComparator(comparison) {
  if (!comparison) {
    DOM.compSection.hidden = true;
    return;
  }
  DOM.compSection.hidden = false;

  const setSlot = (slot, scoreEl, catEl, scaleEl, dotEl) => {
    scoreEl.textContent = slot?.score != null ? slot.score : '—';
    catEl.textContent   = slot?.category || 'Data unavailable';
    scaleEl.textContent = `Scale ${slot?.scale || '—'}`;
    dotEl.style.background = slot?.color || '#64748b';
  };

  setSlot(comparison.cpcb,   DOM.compCpcbScore, DOM.compCpcbCat, DOM.compCpcbScale, DOM.compCpcbDot);
  setSlot(comparison.us_epa, DOM.compUsScore,   DOM.compUsCat,   DOM.compUsScale,   DOM.compUsDot);
  setSlot(comparison.eu_eea, DOM.compEuScore,   DOM.compEuCat,   DOM.compEuScale,   DOM.compEuDot);
  DOM.compNote.textContent = comparison.note || '';
}

function syncProfileUI(profile) {
  DOM.profilePills.forEach(btn => {
    const active = btn.dataset.profile === profile;
    btn.setAttribute('aria-checked', active ? 'true' : 'false');
    btn.setAttribute('tabindex', active ? '0' : '-1');
  });
}

function renderRecommendation(data, profile) {
  const rec = data?.recommendation;
  if (!rec) return;

  const key      = PROFILE_TO_GUIDANCE_KEY[profile] || 'overall';
  const guidance = data?.age_guidance?.[key];
  const steps    = Array.isArray(guidance) && guidance.length ? guidance : (rec.precautions || []);

  DOM.recHeadline.textContent = profile === 'overall'
    ? (rec.headline || 'Health Guidance')
    : `${rec.headline || 'Health Guidance'} (${PROFILE_LABELS[profile] || profile})`;
  DOM.recDetail.textContent = rec.detail || '';
  DOM.recPrecautions.innerHTML = steps.map(p => `<li>${esc(p)}</li>`).join('');
}

function renderKidsSection(ageGuidance, activeProfile) {
  DOM.kidsTiers.innerHTML = '';
  const tiers = [
    { key: 'infants_toddlers', profile: 'kids_0_4',  title: 'Infants & Toddlers (0–4 yrs)' },
    { key: 'kids_school',      profile: 'kids_5_12', title: 'School-Age Kids (5–12 yrs)'   },
    { key: 'teens',            profile: 'teens',     title: 'Teens & Sports (13–17 yrs)'   },
  ];

  tiers.forEach(tier => {
    const items = ageGuidance?.[tier.key] || [];
    const row = document.createElement('div');
    row.className = 'kids-tier-row' + (activeProfile === tier.profile ? ' active-tier' : '');

    const listHtml = items.length
      ? items.map(item => `<li>${esc(item)}</li>`).join('')
      : '<li>No age-specific guidance available.</li>';

    row.innerHTML =
      `<h5 class="kids-tier-title">${esc(tier.title)}</h5>` +
      `<ul class="kids-list">${listHtml}</ul>`;

    DOM.kidsTiers.appendChild(row);
  });
}

function renderChart(hourly) {
  const times  = hourly?.time  || [];
  const values = hourly?.pm2_5 || [];

  const pairs = times
    .map((t, i) => [t, values[i]])
    .filter(([, v]) => v != null);

  if (pairs.length < 2) {
    DOM.chartSection.hidden = true;
    return;
  }
  DOM.chartSection.hidden = false;

  const vals = pairs.map(([, v]) => v);
  let minV   = Math.floor(Math.min(...vals));
  let maxV   = Math.ceil(Math.max(...vals));
  if (minV < 0) minV = 0;
  if (maxV <= minV) maxV = minV + 10;

  const midV = Math.round((maxV + minV) / 2);

  DOM.yScaleTop.textContent = `${maxV}`;
  DOM.yScaleMid.textContent = `${midV}`;
  DOM.yScaleBot.textContent = `${minV}`;

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

  const areaPath =
    `M${X_START.toFixed(1)},${Y_BOT} ` +
    ptStr.split(' ').map(p => `L${p}`).join(' ') +
    ` L${X_END.toFixed(1)},${Y_BOT} Z`;
  DOM.chartArea.setAttribute('d', areaPath);

  DOM.labelStart.textContent = fmtTime(pairs[0][0]);
  DOM.labelMid.textContent   = fmtTime(pairs[Math.floor(pairs.length / 2)][0]);
  DOM.labelEnd.textContent   = fmtTime(pairs[pairs.length - 1][0]);
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch { return iso || ''; }
}

function appendCompareRow(rowData) {
  const tr = document.createElement('tr');
  const cpcbAqi = rowData.aqi?.aqi != null ? rowData.aqi.aqi : '—';
  const cat     = rowData.aqi?.category || (rowData.pending ? 'Pending 2nd city' : 'Unknown');
  const usAqi   = rowData.comparison?.us_epa?.score != null ? rowData.comparison.us_epa.score : '—';
  const euAqi   = rowData.comparison?.eu_eea?.score != null ? rowData.comparison.eu_eea.score : '—';
  const pm25    = rowData.current?.pm2_5 != null ? `${rowData.current.pm2_5.toFixed(1)} µg/m³` : '—';
  const pm10    = rowData.current?.pm10  != null ? `${rowData.current.pm10.toFixed(1)} µg/m³`  : '—';
  const name    = rowData.city || rowData.name || 'City';

  tr.innerHTML =
    `<td>${esc(name)}</td>` +
    `<td><span class="compare-aqi-score">${esc(cpcbAqi)}</span></td>` +
    `<td>${esc(cat)}</td>` +
    `<td>${esc(usAqi)} / ${esc(euAqi)}</td>` +
    `<td>${esc(pm25)}</td>` +
    `<td>${esc(pm10)}</td>` +
    `<td><button type="button" class="compare-remove-btn" data-lat="${esc(rowData.lat)}" data-lon="${esc(rowData.lon)}" aria-label="Remove ${esc(name)} from comparison" title="Remove ${esc(name)}">${ICON_REMOVE}</button></td>`;

  tr.querySelector('.compare-remove-btn').addEventListener('click', () => {
    Store.removeCompareCity(Number(rowData.lat), Number(rowData.lon), _lastData);
    _compareDirty = true;
    updateCompareTabLabel();
    if (_lastData) updatePinButton(_lastData);
    loadCompare();
  });

  DOM.compareTbody.appendChild(tr);
}

async function loadCompare() {
  const targets = Store.getActiveCompare(_lastData);
  updateCompareTabLabel();
  DOM.sharedGridNotice.hidden = true;
  DOM.compareTbody.innerHTML  = '';

  if (targets.length === 0) {
    DOM.compareStatus.hidden      = false;
    DOM.compareStatus.textContent = 'No cities selected. Search above to add 2–4 cities or load Delhi · Jaipur · Mumbai.';
    DOM.compareSubtitle.textContent = '0 of 4 cities selected.';
    return;
  }

  if (targets.length === 1) {
    DOM.compareStatus.hidden      = false;
    DOM.compareStatus.textContent = '1 city selected. Search above to add at least 1 more city for live comparison.';
    DOM.compareSubtitle.textContent = '1 of 4 cities selected.';
    appendCompareRow({ ...targets[0], pending: true });
    return;
  }

  const coordsParam = targets.map(c => `${c.lat},${c.lon}`).join(';');
  const citiesParam = targets.map(c => c.name).join('|');

  DOM.compareStatus.hidden      = false;
  DOM.compareStatus.textContent = 'Loading multi-city comparison…';

  try {
    const url =
      `/api/compare` +
      `?coords=${encodeURIComponent(coordsParam)}` +
      `&cities=${encodeURIComponent(citiesParam)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Compare request failed (${res.status})`);
    }
    const data = await res.json();
    _compareDirty = false;
    DOM.compareStatus.hidden = true;
    renderCompareTable(data);
  } catch (err) {
    DOM.compareStatus.hidden      = false;
    DOM.compareStatus.textContent = err.message || 'Could not load city comparison.';
  }
}

function renderCompareTable(data) {
  const rows = data?.cities || [];
  DOM.sharedGridNotice.hidden = !data?.shared_grid_warning;
  DOM.compareSubtitle.textContent = `Comparing ${rows.length} of ${CFG.maxPinned} cities. Search above to add or click any remove icon.`;

  DOM.compareTbody.innerHTML = '';
  rows.forEach(item => appendCompareRow(item));
}

function switchTab(tab, shouldFetchCompare = true) {
  const isCompare = tab === 'compare';
  if (!isCompare && !_lastData) {
    showEmpty();
    return;
  }
  DOM.tabOverview.setAttribute('aria-selected', isCompare ? 'false' : 'true');
  DOM.tabCompare.setAttribute('aria-selected',  isCompare ? 'true'  : 'false');
  DOM.overviewPanel.hidden = isCompare;
  DOM.comparePanel.hidden  = !isCompare;

  if (isCompare && shouldFetchCompare && _compareDirty) {
    loadCompare();
  }
}

function selectProfile(profile) {
  if (!PROFILE_TO_GUIDANCE_KEY[profile]) return;
  Store.setProfile(profile);
  syncProfileUI(profile);
  if (_lastData) {
    renderAQIAlert(_lastData.aqi, profile);
    renderRecommendation(_lastData, profile);
    renderKidsSection(_lastData.age_guidance, profile);
    announce(`Switched guidance profile to ${PROFILE_LABELS[profile] || profile}.`);
  }
}

function renderRecentCities() {
  const recent = Store.getRecent();
  if (!recent.length) { DOM.recentCities.hidden = true; return; }
  DOM.recentCities.hidden  = false;
  DOM.recentList.innerHTML = '';

  recent.forEach(loc => {
    const btn = document.createElement('button');
    btn.className   = 'recent-city-btn';
    btn.textContent = loc.name;
    btn.setAttribute('aria-label', `Search again for ${loc.name}`);
    btn.addEventListener('click', () => {
      DOM.input.value = loc.name;
      loadAirQuality(loc.lat, loc.lon, loc.name);
    });
    DOM.recentList.appendChild(btn);
  });
}

async function fetchAndSelectFirst(query, mode = 'main') {
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
    if (!res.ok) {
      if (mode === 'compare') {
        DOM.compareStatus.hidden      = false;
        DOM.compareStatus.textContent = 'Could not reach the search service. Please try again.';
      } else {
        showError('Could not reach the search service. Please try again.');
      }
      return;
    }
    const list = await res.json();
    if (!Array.isArray(list) || !list.length) {
      if (mode === 'compare') {
        DOM.compareStatus.hidden      = false;
        DOM.compareStatus.textContent = `No results found for "${query}".`;
      } else {
        showError(`No results found for "${query}". Try a different spelling or city name.`);
      }
      return;
    }
    const loc   = list[0];
    const label = [loc.name, loc.admin1, loc.country].filter(Boolean).join(', ');
    if (mode === 'compare') {
      DOM.compareInput.value = '';
      if (!isInCompare(loc.latitude, loc.longitude)) {
        applyCompareToggle({ ...loc, label });
      }
    } else {
      DOM.input.value = label;
      loadAirQuality(loc.latitude, loc.longitude, label);
    }
  } catch {
    if (mode === 'compare') {
      DOM.compareStatus.hidden      = false;
      DOM.compareStatus.textContent = 'Could not search for cities. Please check your connection.';
    } else {
      showError('Could not search for cities. Please check your connection.');
    }
  }
}

const debouncedMainSuggest    = debounce(q => fetchSuggestions(q, DOM.suggestions,        DOM.input,        'main'),    CFG.debounceMs);
const debouncedCompareSuggest = debounce(q => fetchSuggestions(q, DOM.compareSuggestions, DOM.compareInput, 'compare'), CFG.debounceMs);

DOM.input.addEventListener('input', () => {
  const q = DOM.input.value.trim();
  if (q.length >= 2) debouncedMainSuggest(q);
  else closeSuggestions(DOM.suggestions, DOM.input);
});

DOM.input.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    closeSuggestions(DOM.suggestions, DOM.input);
    const q = DOM.input.value.trim();
    if (q) fetchAndSelectFirst(q, 'main');
  }
  if (e.key === 'ArrowDown') {
    const first = DOM.suggestions.querySelector('.suggestion-pick-btn');
    if (first) { e.preventDefault(); first.focus(); }
  }
  if (e.key === 'Escape') closeSuggestions(DOM.suggestions, DOM.input);
});

DOM.searchBtn.addEventListener('click', () => {
  const q = DOM.input.value.trim();
  closeSuggestions(DOM.suggestions, DOM.input);
  if (q) fetchAndSelectFirst(q, 'main');
});

DOM.compareInput.addEventListener('input', () => {
  const q = DOM.compareInput.value.trim();
  if (q.length >= 2) debouncedCompareSuggest(q);
  else closeSuggestions(DOM.compareSuggestions, DOM.compareInput);
});

DOM.compareInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    closeSuggestions(DOM.compareSuggestions, DOM.compareInput);
    const q = DOM.compareInput.value.trim();
    if (q) fetchAndSelectFirst(q, 'compare');
  }
  if (e.key === 'ArrowDown') {
    const first = DOM.compareSuggestions.querySelector('.suggestion-pick-btn');
    if (first) { e.preventDefault(); first.focus(); }
  }
  if (e.key === 'Escape') closeSuggestions(DOM.compareSuggestions, DOM.compareInput);
});

DOM.compareAddBtn.addEventListener('click', () => {
  const q = DOM.compareInput.value.trim();
  closeSuggestions(DOM.compareSuggestions, DOM.compareInput);
  if (q) fetchAndSelectFirst(q, 'compare');
});

DOM.btnRetry.addEventListener('click', () => {
  if (_lastLocation) {
    loadAirQuality(_lastLocation.lat, _lastLocation.lon, _lastLocation.cityName);
  } else {
    showEmpty();
  }
});

DOM.btnOpenCompare.addEventListener('click', () => {
  showResults();
  _compareDirty = true;
  switchTab('compare');
});

DOM.tabOverview.addEventListener('click', () => switchTab('overview'));
DOM.tabCompare.addEventListener('click',  () => switchTab('compare'));

[DOM.tabOverview, DOM.tabCompare].forEach((tabEl, idx, tabs) => {
  tabEl.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      const next = tabs[(idx + 1) % tabs.length];
      next.focus();
      switchTab(next === DOM.tabCompare ? 'compare' : 'overview');
    }
  });
});

DOM.profilePills.forEach((pill, idx) => {
  pill.addEventListener('click', () => selectProfile(pill.dataset.profile));
  pill.addEventListener('keydown', e => {
    let nextIdx = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextIdx = (idx + 1) % DOM.profilePills.length;
    if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   nextIdx = (idx - 1 + DOM.profilePills.length) % DOM.profilePills.length;
    if (nextIdx !== null) {
      e.preventDefault();
      const nextPill = DOM.profilePills[nextIdx];
      nextPill.focus();
      selectProfile(nextPill.dataset.profile);
    }
  });
});

DOM.btnPinCity.addEventListener('click', () => {
  if (!_lastData || _lastData.lat == null || _lastData.lon == null) return;
  applyCompareToggle({
    label:     _lastData.city || 'Unknown',
    latitude:  _lastData.lat,
    longitude: _lastData.lon,
  });
});

DOM.btnPresetCompare.addEventListener('click', () => {
  Store.setPresetsCompare();
  _compareDirty = true;
  if (_lastData) updatePinButton(_lastData);
  loadCompare();
});

DOM.btnClearPins.addEventListener('click', () => {
  Store.clearPinned();
  _compareDirty = true;
  if (_lastData) updatePinButton(_lastData);
  loadCompare();
});

document.addEventListener('click', e => {
  if (!DOM.suggestions.contains(e.target) && e.target !== DOM.input) {
    closeSuggestions(DOM.suggestions, DOM.input);
  }
  if (!DOM.compareSuggestions.contains(e.target) && e.target !== DOM.compareInput) {
    closeSuggestions(DOM.compareSuggestions, DOM.compareInput);
  }
});

function init() {
  showEmpty();
  syncProfileUI(Store.getProfile());
  updateCompareTabLabel();
  const last = Store.getLast();
  if (last?.city) DOM.input.value = last.city;
}

init();
