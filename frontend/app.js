(() => {
  'use strict';

  const API_BASE =
    window.GHOSTBUSTER_API_BASE ?? (location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '');
  const DEMO_COORDS = Object.freeze({ lat: 51.8988, lon: -8.4715, label: 'Patrick Street, Cork' });
  const SCORE_MIN = 300;
  const SCORE_MAX = 850;
  const DEMO_STORAGE_KEY = 'ghostbuster.demo';
  const GEOLOCATION_CACHE_TIMEOUT_MS = 1200;
  const GEOLOCATION_TIMEOUT_MS = 6000;
  const GEOLOCATION_MAX_AGE_MS = 30000;
  const MAX_PRECISE_CACHE_ACCURACY_M = 150;
  const MAX_USABLE_LOCATION_ACCURACY_M = 300;
  const NETWORK_LOCATION_TIMEOUT_MS = 4000;

  const TIER = {
    prime: { color: '#22c55e', text: 'text-emerald-400', bg: 'bg-emerald-500/15', name: 'PRIME' },
    near_prime: { color: '#f59e0b', text: 'text-amber-400', bg: 'bg-amber-500/15', name: 'NEAR-PRIME' },
    subprime: { color: '#ef4444', text: 'text-red-400', bg: 'bg-red-500/15', name: 'SUBPRIME' },
  };

  const SCENARIOS = {
    live: null,
    am_peak: { hour: 8, dow: 1 },
    pm_peak: { hour: 17, dow: 3 },
    late: { hour: 1, dow: 5 },
    sunday: { hour: 11, dow: 6 },
  };

  const state = { demo: false, seq: 0 };
  const $ = (id) => document.getElementById(id);
  const hasUsableAccuracy = (coords, maxMeters) =>
    Number.isFinite(coords.accuracy) && coords.accuracy <= maxMeters;

  const esc = (value) =>
    String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const fmtDist = (m) => (m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`);

  function ringSVG({ score, tier, size, stroke, scoreFont, caption }) {
    const view = 160;
    const r = (view - stroke) / 2 - 2;
    const c = 2 * Math.PI * r;
    const frac = Math.min(1, Math.max(0, (score - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)));
    const color = (TIER[tier] || TIER.near_prime).color;
    const textY = (caption ? 74 : 80) + scoreFont * 0.35;
    const captionEl = caption
      ? `<text x="80" y="${textY + 24}" text-anchor="middle" font-size="12" letter-spacing="2" fill="#94a3b8">${esc(caption)}</text>`
      : '';
    return `
      <svg viewBox="0 0 ${view} ${view}" width="${size}" height="${size}" role="img" aria-label="Stop credit score ${score}">
        <circle cx="80" cy="80" r="${r}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="${stroke}" />
        <circle class="ring-progress" cx="80" cy="80" r="${r}" fill="none" stroke="${color}"
          stroke-width="${stroke}" stroke-linecap="round" stroke-dasharray="${c} ${c}" stroke-dashoffset="${c}"
          data-offset="${c * (1 - frac)}" transform="rotate(-90 80 80)"
          style="filter: drop-shadow(0 0 8px ${color}88)" />
        <text x="80" y="${textY}" text-anchor="middle" font-size="${scoreFont}" font-weight="800" fill="#f8fafc">${score}</text>
        ${captionEl}
      </svg>`;
  }

  function animateRings(root) {
    const rings = root.querySelectorAll('.ring-progress');
    requestAnimationFrame(() =>
      requestAnimationFrame(() => rings.forEach((el) => (el.style.strokeDashoffset = el.dataset.offset)))
    );
  }

  function setNotice(html, kind = 'error') {
    const box = $('notice');
    if (!html) {
      box.className = 'mb-4 hidden';
      box.innerHTML = '';
      return;
    }
    const palette =
      kind === 'error'
        ? 'border-red-500/40 bg-red-500/10 text-red-200'
        : 'border-sky-500/40 bg-sky-500/10 text-sky-200';
    box.className = `mb-4 rounded-2xl border px-4 py-3 text-sm ${palette}`;
    box.innerHTML = html;
  }

  function renderLoading() {
    $('score-card').innerHTML = `
      <div class="space-y-4">
        <div class="skeleton h-5 w-2/3"></div>
        <div class="skeleton mx-auto h-48 w-48 !rounded-full"></div>
        <div class="skeleton h-4 w-full"></div>
        <div class="skeleton h-4 w-3/4"></div>
      </div>`;
    $('alternatives').innerHTML = `<div class="space-y-3"><div class="skeleton h-20 w-full"></div><div class="skeleton h-20 w-full"></div></div>`;
    $('context').innerHTML = '';
  }

  function renderSourcePill(source, coords) {
    const pill = $('source-pill');
    if (source === 'demo') {
      pill.className = 'rounded-full bg-amber-500 px-4 py-2 text-xs font-bold text-slate-950';
      pill.textContent = `STAGE DEMO · ${DEMO_COORDS.label}`;
    } else if (source === 'network') {
      pill.className = 'glass rounded-full px-4 py-2 text-xs font-medium text-amber-300';
      pill.textContent = `Approx. network location · ${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}`;
    } else {
      const accuracy = Number.isFinite(coords.accuracy)
        ? ` · ±${Math.round(coords.accuracy)} m`
        : '';
      const quality = Number.isFinite(coords.accuracy) && coords.accuracy > 200 ? ' (low accuracy)' : '';
      pill.className = `glass rounded-full px-4 py-2 text-xs font-medium ${
        quality ? 'text-amber-300' : 'text-emerald-300'
      }`;
      pill.textContent = `Live GPS${quality}${accuracy} · ${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}`;
    }
  }

  function renderResult(d, source, coords) {
    const t = TIER[d.tier] || TIER.near_prime;
    const routes = d.stop.routes.map((r) => `<span class="rounded-md bg-white/10 px-2 py-0.5 text-xs font-semibold">${esc(r)}</span>`).join(' ');
    $('score-card').innerHTML = `
      <div class="fade-in text-center">
        <p class="text-xs font-semibold uppercase tracking-widest text-slate-400">Nearest stop · ${esc(fmtDist(d.distance_m))} away</p>
        <h2 class="mt-1 text-2xl font-extrabold">${esc(d.stop.name)}</h2>
        <p class="text-sm text-slate-400">${esc(d.stop.city)}</p>
        <div class="mt-2 flex flex-wrap justify-center gap-1.5">${routes}</div>
        <div class="mx-auto mt-5 w-fit">${ringSVG({ score: d.score, tier: d.tier, size: 220, stroke: 14, scoreFont: 46, caption: 'STOP CREDIT SCORE' })}</div>
        <div class="mt-1 flex justify-between px-10 text-[10px] font-medium text-slate-500"><span>${SCORE_MIN}</span><span>${SCORE_MAX}</span></div>
        <div class="mt-3 inline-flex items-center gap-2 rounded-full ${t.bg} px-4 py-1.5 text-sm font-bold ${t.text}">
          <span class="h-2 w-2 rounded-full" style="background:${t.color}"></span>${esc(t.name)} · ${esc(d.tier_label)}
        </div>
        <p class="mt-3 text-sm text-slate-300"><span class="font-semibold ${t.text}">${Math.round(d.ghost_probability * 100)}%</span> chance of a ghost bus</p>
        <p class="mt-3 rounded-xl bg-white/5 p-3 text-sm leading-relaxed text-slate-200">${esc(d.advice)}</p>
      </div>`;

    const alt = $('alternatives');
    if (d.alternatives_triggered && d.alternatives.length) {
      alt.innerHTML = `<ul class="space-y-3">${d.alternatives
        .map(
          (a) => `
        <li class="fade-in flex items-center gap-4 rounded-2xl bg-white/5 p-3 ring-1 ring-white/5">
          <div class="shrink-0">${ringSVG({ score: a.score, tier: a.tier, size: 68, stroke: 16, scoreFont: 56 })}</div>
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold">${esc(a.stop.name)}</p>
            <p class="text-xs text-slate-400">${a.walk_minutes} min walk · ${esc(fmtDist(a.distance_m))} · routes ${esc(a.stop.routes.join(', '))}</p>
            <p class="text-xs ${(TIER[a.tier] || TIER.near_prime).text}">${esc(a.tier_label)}</p>
          </div>
          <div class="text-right"><p class="text-lg font-extrabold text-emerald-400">+${a.score_gain}</p><p class="text-[10px] uppercase tracking-wider text-slate-500">points</p></div>
        </li>`
        )
        .join('')}</ul>`;
    } else if (d.alternatives_triggered) {
      alt.innerHTML = `<div class="rounded-2xl bg-white/5 p-4 text-sm text-slate-300">No materially better stop within walking distance. Build in extra time or plan a backup mode.</div>`;
    } else {
      alt.innerHTML = `<div class="rounded-2xl bg-white/5 p-4 text-sm text-slate-300">This stop is not subprime, so no re-routing is needed. Try the <span class="font-semibold">Thu 17:00</span> scenario with <span class="font-semibold">Heavy rain</span> to see alternatives activate.</div>`;
    }

    const c = d.context;
    const chip = (text, cls = 'bg-white/5 text-slate-300') => `<span class="rounded-full px-3 py-1 ${cls}">${text}</span>`;
    $('context').innerHTML = [
      chip(`🕒 ${esc(c.local_time_label)}`),
      chip(`${c.heavy_rain ? '🌧️ Heavy rain' : '☀️ No heavy rain'} · ${esc(c.weather_source)}`, c.heavy_rain ? 'bg-sky-500/15 text-sky-300' : 'bg-white/5 text-slate-300'),
      c.precipitation_mm !== null && c.precipitation_mm !== undefined
        ? chip(`🌦️ ${c.precipitation_mm} mm`)
        : '',
      c.weather_error ? chip(`⚠️ ${esc(c.weather_error)}`, 'bg-amber-500/15 text-amber-300') : '',
      c.simulated ? chip('Simulated time', 'bg-violet-500/15 text-violet-300') : chip('Live time'),
    ].join('');

    renderSourcePill(source, coords);
    animateRings($('score-card'));
    animateRings($('alternatives'));
  }

  function renderError(message) {
    $('score-card').innerHTML = `<div class="py-10 text-center"><p class="text-4xl">⚠️</p><p class="mt-3 font-semibold">Couldn't load a score</p><p class="mt-1 text-sm text-slate-400">${esc(message)}</p></div>`;
    $('alternatives').innerHTML = '';
    $('context').innerHTML = '';
    setNotice(esc(message));
  }

  function renderGeoFailure(message) {
    $('score-card').innerHTML = `
      <div class="py-8 text-center">
        <p class="text-4xl">📍</p>
        <p class="mt-3 font-semibold">Location unavailable</p>
        <p class="mt-1 text-sm text-slate-400">${esc(message)}</p>
        <button type="button" data-action="retry-location" class="mt-5 rounded-xl bg-sky-500 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-sky-400">Try locating again</button>
        <button type="button" data-action="enable-demo" class="mt-5 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-400">Switch to Stage Demo Mode</button>
      </div>`;
    $('alternatives').innerHTML = '';
    $('context').innerHTML = '';
    $('source-pill').className = 'glass rounded-full px-4 py-2 text-xs font-medium text-red-300';
    $('source-pill').textContent = 'No location';
  }

  function renderCoverageFailure(message, coords) {
    $('score-card').innerHTML = `
      <div class="py-8 text-center">
        <p class="text-4xl">🚌</p>
        <p class="mt-3 font-semibold">Live location found</p>
        <p class="mt-1 text-sm text-slate-400">${esc(message)}</p>
        <p class="mt-3 text-xs text-slate-500">GPS: ${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}</p>
        <button type="button" data-action="retry-location" class="mt-5 rounded-xl bg-sky-500 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-sky-400">Refresh location</button>
      </div>`;
    $('alternatives').innerHTML = '';
    $('context').innerHTML = '';
    renderSourcePill('gps', coords);
  }

  function geoMessage(err) {
    if (!err) return 'Unknown location error.';
    if (err.code === 1) return 'Location permission was denied. Allow access in your browser, or use Stage Demo Mode.';
    if (err.code === 2) return 'Your position could not be determined (no signal).';
    if (err.code === 3) return 'Locating timed out.';
    return err.message || 'Unknown location error.';
  }

  function requestPosition(options) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Locating timed out.')), options.timeout);
      const succeed = (position) => {
        clearTimeout(timer);
        resolve({
          lat: position.coords.latitude,
          lon: position.coords.longitude,
          accuracy: Number.isFinite(position.coords.accuracy) ? position.coords.accuracy : null,
        });
      };
      const fail = (error) => {
        clearTimeout(timer);
        reject(new Error(geoMessage(error)));
      };
      navigator.geolocation.getCurrentPosition(
        succeed,
        fail,
        options
      );
    });
  }

  async function getPosition() {
    if (!('geolocation' in navigator)) {
      throw new Error('Geolocation is not supported by this browser.');
    }
    if (location.protocol === 'file:') {
      throw new Error('Open the app at http://127.0.0.1:8000 so your browser can provide a location.');
    }
    if (window.isSecureContext === false && !['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)) {
      throw new Error('Location requires HTTPS, or open the app locally at http://127.0.0.1:8000.');
    }

    const cachedPromise = requestPosition({
      enableHighAccuracy: false,
      timeout: GEOLOCATION_CACHE_TIMEOUT_MS,
      maximumAge: GEOLOCATION_MAX_AGE_MS,
    }).then((coords) => ({ kind: 'cached', coords })).catch((error) => ({ kind: 'error', error }));
    const freshPromise = requestPosition({
      enableHighAccuracy: true,
      timeout: GEOLOCATION_TIMEOUT_MS,
      maximumAge: 0,
    }).then((coords) => ({ kind: 'fresh', coords })).catch((error) => ({ kind: 'error', error }));

    const first = await Promise.race([cachedPromise, freshPromise]);
    if (
      first.kind === 'fresh' &&
      hasUsableAccuracy(first.coords, MAX_USABLE_LOCATION_ACCURACY_M)
    ) {
      return first.coords;
    }
    if (first.kind === 'cached' && hasUsableAccuracy(first.coords, MAX_PRECISE_CACHE_ACCURACY_M)) {
      return first.coords;
    }

    const results = await Promise.all([cachedPromise, freshPromise]);
    const fresh = results.find((result) => result.kind === 'fresh');
    const cached = results.find((result) => result.kind === 'cached');
    if (fresh && hasUsableAccuracy(fresh.coords, MAX_USABLE_LOCATION_ACCURACY_M)) return fresh.coords;
    if (cached && hasUsableAccuracy(cached.coords, MAX_USABLE_LOCATION_ACCURACY_M)) return cached.coords;
    if (fresh || cached) {
      const accuracy = (fresh || cached).coords.accuracy;
      throw new Error(
        `Your browser only provided an approximate location${
          Number.isFinite(accuracy) ? ` (±${Math.round(accuracy)} m)` : ''
        }. ` +
          'Enable precise location services and try again.'
      );
    }
    throw first.error;
  }

  async function getNetworkPosition() {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), NETWORK_LOCATION_TIMEOUT_MS);
    try {
      const response = await fetch('https://ipapi.co/json/', {
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Network location service responded with ${response.status}.`);
      const data = await response.json();
      const lat = Number(data.latitude);
      const lon = Number(data.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
        throw new Error('Network location service returned invalid coordinates.');
      }
      return { lat, lon };
    } finally {
      clearTimeout(timer);
    }
  }

  async function refresh() {
    const seq = ++state.seq;
    setNotice('');
    renderLoading();

    let coords;
    let source;
    if (state.demo) {
      coords = { lat: DEMO_COORDS.lat, lon: DEMO_COORDS.lon, accuracy: 0 };
      source = 'demo';
    } else {
      try {
        coords = await getPosition();
        source = 'gps';
      } catch (geoErr) {
        if (geoErr.message.startsWith('Your browser only provided an approximate location')) {
          if (seq === state.seq) renderGeoFailure(geoErr.message);
          return;
        }
        try {
          coords = await getNetworkPosition();
          source = 'network';
        } catch (networkErr) {
          if (seq === state.seq) {
            renderGeoFailure(`${geoErr.message} Network location was also unavailable.`);
          }
          return;
        }
      }
    }

    try {
      const params = new URLSearchParams({
        lat: coords.lat.toFixed(6),
        lon: coords.lon.toFixed(6),
      });
      if ($('rain-toggle').checked) params.set('heavy_rain', 'true');
      const scenario = SCENARIOS[$('scenario').value];
      if (scenario) {
        params.set('hour', String(scenario.hour));
        params.set('day_of_week', String(scenario.dow));
      }
      const res = await fetch(`${API_BASE}/api/score?${params.toString()}`, { headers: { Accept: 'application/json' } });
      if (!res.ok) {
        let detail = `Server responded with ${res.status}.`;
        try {
          const body = await res.json();
          if (body && typeof body.detail === 'string') detail = body.detail;
        } catch (_) { /* non-JSON error body */ }
        const error = new Error(detail);
        error.status = res.status;
        throw error;
      }
      const data = await res.json();
      if (seq !== state.seq) return;
      renderResult(data, source, coords);
    } catch (err) {
      if (seq !== state.seq) return;
      if (source === 'gps' && err.status === 404) {
        renderCoverageFailure(err.message, coords);
        return;
      }
      const offline = err instanceof TypeError;
      renderError(offline ? 'Cannot reach the GhostBuster API. Is the server running on port 8000?' : err.message);
    }
  }

  function persistDemo(on) {
    try { localStorage.setItem(DEMO_STORAGE_KEY, on ? '1' : '0'); } catch (_) { /* storage unavailable */ }
  }

  function readDemo() {
    try { return localStorage.getItem(DEMO_STORAGE_KEY) === '1'; } catch (_) { return false; }
  }

  function applyDemoUI() {
    const toggle = $('demo-toggle');
    toggle.setAttribute('aria-checked', String(state.demo));
    $('demo-toggle-label').textContent = state.demo ? 'Demo ON' : 'Demo OFF';
    $('demo-banner').classList.toggle('hidden', !state.demo);
    $('demo-panel').classList.toggle('demo-on', state.demo);
  }

  function setDemo(on, { applyPreset = true } = {}) {
    state.demo = on;
    persistDemo(on);
    if (on && applyPreset) {
      $('scenario').value = 'pm_peak';
      $('rain-toggle').checked = true;
    }
    applyDemoUI();
    refresh();
  }

  async function loadHealth() {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (!res.ok) throw new Error('health failed');
      const h = await res.json();
      const auc = h.ml && h.ml.roc_auc ? ` · AUC ${h.ml.roc_auc}` : '';
      const src = h.ml && h.ml.data_source ? ` · ${h.ml.data_source} training data` : '';
      $('footer').textContent = `Engine v${h.ml?.version ?? '?'} · RandomForest (CPU)${auc}${src} · ${h.stop_count} stops indexed`;
    } catch (_) {
      $('footer').textContent = 'Engine status unavailable.';
    }
  }

  function init() {
    document.addEventListener('click', (e) => {
      const target = e.target.closest('[data-action]');
      if (!target) return;
      const action = target.dataset.action;
      if (action === 'toggle-demo') setDemo(!state.demo);
      else if (action === 'enable-demo') setDemo(true);
      else if (action === 'retry-location') refresh();
      else if (action === 'refresh') refresh();
    });
    $('scenario').addEventListener('change', refresh);
    $('rain-toggle').addEventListener('change', refresh);
    document.addEventListener('keydown', (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target && e.target.tagName) || '';
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;
      if (e.key === 'd' || e.key === 'D') setDemo(!state.demo);
    });

    state.demo = readDemo();
    if (state.demo) {
      $('scenario').value = 'pm_peak';
      $('rain-toggle').checked = true;
    }
    applyDemoUI();
    loadHealth();
    refresh();
  }

  init();
})();
