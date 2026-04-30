// ── CONFIG ───────────────────────────────────────────────────────────
const API_BASE =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:5000"
    : "";

// ╔══════════════════════════════════════════════════════════════════╗
// ║  CHANGE 1 of 3 — Replace Nominatim constants with OLA Maps      ║
// ║  Delete the old NOMINATIM_BASE and NOMINATIM_EMAIL lines,        ║
// ║  paste your key into OLA_API_KEY below.                          ║
// ╚══════════════════════════════════════════════════════════════════╝
const OLA_API_KEY = "7vxcLcSVNnnndP5b5m5SDeJbMjyLdwxb74TMC93i";
const OLA_BASE = "https://api.olamaps.io";

// ── STATE ────────────────────────────────────────────────────────────
let clickPoints = [];
let markers = [];
let pathLayers = [];
let currentMode = "drive";
let searchedLatLng = null;
let searchTimeout = null;
let directionsOpen = true;
let panelCollapsed = false;
let currentTheme = "dark";

// ── THEME ────────────────────────────────────────────────────────────
function toggleTheme() {
  currentTheme = currentTheme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", currentTheme);
  localStorage.setItem("pfp-theme", currentTheme);
  updateTiles();
}

(function initTheme() {
  const saved = localStorage.getItem("pfp-theme") || "dark";
  currentTheme = saved;
  document.documentElement.setAttribute("data-theme", saved);
})();

// ── PANEL COLLAPSE ───────────────────────────────────────────────────
function togglePanel() {
  panelCollapsed = !panelCollapsed;
  document.body.classList.toggle("panel-collapsed", panelCollapsed);
}

// ── MAP SETUP ────────────────────────────────────────────────────────
const map = L.map("map", {
  zoomControl: false,
  attributionControl: false,
}).setView([28.6139, 77.209], 12);

let tileLayer = null;

function updateTiles() {
  if (tileLayer) map.removeLayer(tileLayer);
  const url =
    currentTheme === "dark"
      ? "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"
      : "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png";
  tileLayer = L.tileLayer(url, { maxZoom: 20 }).addTo(map);
}
updateTiles();

L.control.zoom({ position: "bottomright" }).addTo(map);

// ── WEBSOCKET ────────────────────────────────────────────────────────
let socket = null;
function initWebSocket() {
  try {
    socket = io(API_BASE, { transports: ["websocket", "polling"] });
    socket.on("connect", () => {
      document.getElementById("live-dot").classList.add("connected");
      socket.emit("subscribe_conditions", { city: "delhi" });
    });
    socket.on("disconnect", () => {
      document.getElementById("live-dot").classList.remove("connected");
    });
    socket.on("condition_update", (data) => {
      console.log("Condition update:", data);
    });
  } catch (e) {
    console.log("WebSocket offline mode");
  }
}
initWebSocket();

// ── TRANSPORT MODE ───────────────────────────────────────────────────
function setMode(mode, btn) {
  currentMode = mode;
  document
    .querySelectorAll(".mode-btn")
    .forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  const labels = { drive: "A*", walk: "A*", cycle: "A*" };
  document.getElementById("algo-label").textContent = labels[mode] || "A*";
  if (clickPoints.length === 2) computeRoute();
}

// ── SEARCH ───────────────────────────────────────────────────────────
function onSearchInput() {
  const val = document.getElementById("search-input").value;
  document.getElementById("search-clear").style.display = val ? "flex" : "none";
  clearTimeout(searchTimeout);
  if (val.trim().length < 3) {
    hideSuggestions();
    return;
  }
  searchTimeout = setTimeout(() => fetchSuggestions(val.trim()), 400);
}

function onSearchKey(e) {
  if (e.key === "Enter") doSearch();
  if (e.key === "Escape") hideSuggestions();
}

function clearSearch() {
  document.getElementById("search-input").value = "";
  document.getElementById("search-clear").style.display = "none";
  hideSuggestions();
  document.getElementById("set-as-row").style.display = "none";
  searchedLatLng = null;
}

// ╔══════════════════════════════════════════════════════════════════╗
// ║  CHANGE 2 of 3 — fetchSuggestions: Nominatim → OLA autocomplete ║
// ║                                                                  ║
// ║  OLD endpoint : nominatim.openstreetmap.org/search               ║
// ║  NEW endpoint : api.olamaps.io/places/v1/autocomplete            ║
// ║                                                                  ║
// ║  OLA returns data.predictions[] where each item has:             ║
// ║    .description        → full place name string                  ║
// ║    .geometry.location  → { lat, lng }                            ║
// ║                                                                  ║
// ║  We normalize it into { lat, lon, display_name } — the exact     ║
// ║  same shape showSuggestions() already expects, so nothing        ║
// ║  below this function changes.                                    ║
// ╚══════════════════════════════════════════════════════════════════╝
async function fetchSuggestions(query) {
  try {
    const url =
      `${OLA_BASE}/places/v1/autocomplete` +
      `?input=${encodeURIComponent(query)}` +
      `&api_key=${OLA_API_KEY}` +
      `&location=28.6139,77.2090` + // bias toward Delhi center
      `&radius=50000` + // 50 km — covers all of Delhi NCR
      `&strictbounds=false`; // allow slight overflow

    const res = await fetch(url, {
      method: "GET",
      headers: { "X-Request-Id": crypto.randomUUID() },
    });
    const data = await res.json();

    if (!data.predictions || data.status !== "ok") {
      hideSuggestions();
      return;
    }

    // Normalize → same { lat, lon, display_name } shape as old Nominatim results
    const results = data.predictions.map((p) => ({
      lat: p.geometry?.location?.lat ?? 0,
      lon: p.geometry?.location?.lng ?? 0,
      display_name: p.description ?? p.structured_formatting?.main_text ?? "",
    }));

    showSuggestions(results); // unchanged below this point
  } catch (err) {
    console.error("OLA Maps autocomplete error:", err);
  }
}

// ── showSuggestions, hideSuggestions, escapeAttr — UNCHANGED ─────────
function showSuggestions(results) {
  const box = document.getElementById("search-suggestions");
  if (!results.length) {
    hideSuggestions();
    return;
  }
  box.innerHTML = results
    .map(
      (r) => `
    <div class="suggestion-item" onclick="selectSuggestion(${r.lat},${r.lon},'${escapeAttr(r.display_name)}')">
      <div class="sug-name">${r.display_name.split(",")[0]}</div>
      <div class="sug-detail">${r.display_name.split(",").slice(1, 3).join(",").trim()}</div>
    </div>`,
    )
    .join("");
  box.style.display = "block";
}

function hideSuggestions() {
  document.getElementById("search-suggestions").style.display = "none";
}

function escapeAttr(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function selectSuggestion(lat, lon, name) {
  searchedLatLng = [parseFloat(lat), parseFloat(lon)];
  document.getElementById("search-input").value = name.split(",")[0];
  document.getElementById("search-clear").style.display = "flex";
  hideSuggestions();
  document.getElementById("set-as-row").style.display = "flex";
  map.setView(searchedLatLng, 15);
}

// ╔══════════════════════════════════════════════════════════════════╗
// ║  CHANGE 3 of 3 — doSearch: add OLA text search for Enter key    ║
// ║                                                                  ║
// ║  OLD: doSearch() just called fetchSuggestions() directly.        ║
// ║  NEW: If the user presses Enter without picking a dropdown item, ║
// ║       we call OLA's /places/v1/textsearch — it always returns    ║
// ║       full geometry even for free-text queries.                  ║
// ║       If suggestions are already visible, we skip this.          ║
// ╚══════════════════════════════════════════════════════════════════╝
async function doSearch() {
  const query = document.getElementById("search-input").value.trim();
  if (!query) return;

  // Suggestions already open — don't re-query
  if (document.getElementById("search-suggestions").style.display === "block")
    return;

  try {
    const url =
      `${OLA_BASE}/places/v1/textsearch` +
      `?input=${encodeURIComponent(query + " Delhi")}` +
      `&api_key=${OLA_API_KEY}` +
      `&location=28.6139,77.2090` +
      `&radius=50000`;

    const res = await fetch(url, {
      method: "GET",
      headers: { "X-Request-Id": crypto.randomUUID() },
    });
    const data = await res.json();

    if (!data.results?.length) {
      setInstruction("No results found — try a different search");
      return;
    }

    const results = data.results.slice(0, 5).map((r) => ({
      lat: r.geometry?.location?.lat ?? 0,
      lon: r.geometry?.location?.lng ?? 0,
      display_name:
        r.name + (r.formatted_address ? ", " + r.formatted_address : ""),
    }));

    showSuggestions(results);
  } catch (err) {
    console.error("OLA Maps text search error:", err);
    await fetchSuggestions(query); // graceful fallback to autocomplete
  }
}

function setSearchedPoint(type) {
  if (!searchedLatLng) return;
  const [lat, lng] = searchedLatLng;
  placePoint(lat, lng, type);
  document.getElementById("set-as-row").style.display = "none";
  document.getElementById("search-input").value = "";
  document.getElementById("search-clear").style.display = "none";
  searchedLatLng = null;
  if (clickPoints.length === 2) computeRoute();
}

// ── EVERYTHING BELOW IS UNCHANGED ────────────────────────────────────

function useMyLocation() {
  if (!navigator.geolocation) {
    setInstruction("Geolocation not supported");
    return;
  }
  const btn = document.getElementById("geo-btn");
  btn.classList.add("loading");
  btn.textContent = "Locating…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      btn.classList.remove("loading");
      btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> My location`;
      searchedLatLng = [pos.coords.latitude, pos.coords.longitude];
      document.getElementById("set-as-row").style.display = "flex";
      map.setView(searchedLatLng, 15);
      const geoIcon = L.divIcon({
        className: "",
        iconAnchor: [10, 10],
        html: `<div style="width:20px;height:20px;border-radius:50%;background:rgba(16,185,129,0.25);border:2px solid #10b981;animation:pulse 2s ease-in-out infinite"></div>`,
      });
      L.marker(searchedLatLng, { icon: geoIcon }).addTo(map);
    },
    () => {
      btn.classList.remove("loading");
      btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> My location`;
      setInstruction("Location denied — check browser permissions");
    },
    { timeout: 8000, maximumAge: 60000 },
  );
}

function makeMarker(lat, lng, type) {
  const isOrigin = type === "origin";
  const color = isOrigin ? "#06b6d4" : "#a78bfa";
  const glow = isOrigin ? "rgba(6,182,212,0.2)" : "rgba(167,139,250,0.2)";
  const icon = L.divIcon({
    className: "",
    iconAnchor: [18, 18],
    html: `<svg width="36" height="36" viewBox="0 0 36 36">
      <circle cx="18" cy="18" r="15" fill="${glow}" stroke="${color}" stroke-width="1.5"/>
      <circle cx="18" cy="18" r="6" fill="${color}"/>
      <circle cx="18" cy="18" r="2.5" fill="${currentTheme === "dark" ? "#080d14" : "#ffffff"}"/>
    </svg>`,
  });
  return L.marker([lat, lng], { icon }).addTo(map);
}

function drawRoute(coords, mode) {
  const modeColors = { drive: "#3b82f6", walk: "#10b981", cycle: "#f59e0b" };
  const color = modeColors[mode] || "#3b82f6";
  const halo = L.polyline(coords, {
    color,
    weight: 22,
    opacity: 0.05,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(map);
  const glow = L.polyline(coords, {
    color,
    weight: 9,
    opacity: 0.12,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(map);
  const line = L.polyline(coords, {
    color,
    weight: 3,
    opacity: 0.95,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(map);
  pathLayers.push(halo, glow, line);
  return line;
}

function drawSegmentedRoute(segments) {
  const COLOR = { free: "#10b981", moderate: "#f59e0b", heavy: "#ef4444" };
  const WEIGHT = { free: 3, moderate: 4, heavy: 5 };
  let bounds = [];
  segments.forEach((seg) => {
    const color = COLOR[seg.congestion] || "#3b82f6";
    const weight = WEIGHT[seg.congestion] || 3;
    const halo = L.polyline(seg.coords, {
      color,
      weight: weight + 8,
      opacity: 0.08,
      lineCap: "round",
      lineJoin: "round",
    }).addTo(map);
    const line = L.polyline(seg.coords, {
      color,
      weight,
      opacity: 0.9,
      lineCap: "round",
      lineJoin: "round",
    }).addTo(map);
    line.bindTooltip(
      `<span style="font-size:11px;font-weight:500">${seg.congestion.charAt(0).toUpperCase() + seg.congestion.slice(1)} traffic</span>`,
      { sticky: true },
    );
    pathLayers.push(halo, line);
    bounds = bounds.concat(seg.coords);
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [80, 80] });
}

function placePoint(lat, lng, type) {
  if (type === "auto") type = clickPoints.length === 0 ? "origin" : "dest";
  if (type === "origin") {
    if (clickPoints[0]) {
      if (markers[0]) map.removeLayer(markers[0]);
      clickPoints[0] = [lat, lng];
      markers[0] = makeMarker(lat, lng, "origin");
    } else {
      clickPoints.push([lat, lng]);
      markers.push(makeMarker(lat, lng, "origin"));
    }
    updateCoords("origin", lat, lng);
    setProgress(40);
    setStatusDot("active");
    if (clickPoints.length < 2) setInstruction("Now set your destination");
  } else {
    if (clickPoints.length === 0) {
      setInstruction("Set your origin first");
      return;
    }
    if (clickPoints[1] !== undefined) {
      if (markers[1]) map.removeLayer(markers[1]);
      clickPoints[1] = [lat, lng];
      markers[1] = makeMarker(lat, lng, "dest");
    } else {
      clickPoints.push([lat, lng]);
      markers.push(makeMarker(lat, lng, "dest"));
    }
    updateCoords("dest", lat, lng);
    setProgress(70);
    computeRoute();
  }
}

function computeRoute() {
  if (clickPoints.length < 2) return;
  pathLayers.forEach((l) => map.removeLayer(l));
  pathLayers = [];
  setProgress(70);
  setInstruction("Calculating route…");
  setStatusDot("active");

  fetch(`${API_BASE}/find_path`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start: clickPoints[0],
      end: clickPoints[1],
      mode: currentMode,
    }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        setInstruction(`Error: ${data.error}`);
        setProgress(0);
        setStatusDot("");
        return;
      }
      if (data.segments && data.segments.length) {
        drawSegmentedRoute(data.segments);
      } else {
        const line = drawRoute(data.path, data.mode);
        map.fitBounds(line.getBounds(), { padding: [80, 80] });
      }
      document.getElementById("dist").textContent = data.distance;
      document.getElementById("eta").textContent = data.time;
      document.getElementById("exec").textContent = data.execution_time;
      document.getElementById("nodes").textContent =
        data.nodes_visited.toLocaleString();
      document.getElementById("metrics").classList.add("show");
      const cacheBadge = document.getElementById("cache-badge");
      cacheBadge.style.display = data.cache_hit ? "inline-block" : "none";
      renderDirections(data.directions || []);
      setProgress(100);
      setStatusDot("done");
      const modeLabels = {
        drive: "driving",
        walk: "walking",
        cycle: "cycling",
      };
      setInstruction(
        `Route found — ${modeLabels[data.mode] || data.mode} · click map to restart`,
      );
    })
    .catch(() => {
      setInstruction("Server unreachable — is Flask running?");
      setProgress(0);
      setStatusDot("");
    });
}

function renderDirections(directions) {
  const list = document.getElementById("directions-list");
  const panel = document.getElementById("directions");
  if (!directions.length) {
    panel.classList.remove("show");
    return;
  }
  list.innerHTML = directions
    .map((d, i) => {
      const isArrival = i === directions.length - 1;
      return `<div class="dir-step ${isArrival ? "arrive" : ""}">
      <span class="dir-num">${d.step}</span>
      <span class="dir-text">${d.instruction}</span>
    </div>`;
    })
    .join("");
  panel.classList.add("show");
}

function toggleDirections() {
  directionsOpen = !directionsOpen;
  document.getElementById("directions-list").style.display = directionsOpen
    ? "flex"
    : "none";
  document.getElementById("dir-toggle").textContent = directionsOpen
    ? "hide"
    : "show";
}

function setProgress(pct) {
  const el = document.getElementById("progress-fill");
  el.style.width = pct + "%";
  el.parentElement.setAttribute("aria-valuenow", pct);
}
function setInstruction(text) {
  document.getElementById("instruction-text").textContent = text;
}
function setStatusDot(state) {
  const dot = document.getElementById("status-dot");
  dot.className = "status-dot" + (state ? " " + state : "");
}
function updateCoords(type, lat, lng) {
  document.getElementById(`hint-${type}`).style.display = "none";
  document.getElementById(`coords-${type}`).style.display = "block";
  document.getElementById(`coords-${type}`).textContent =
    `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  document.getElementById(`card-${type}`).classList.add("active");
}

function resetMap() {
  clickPoints = [];
  markers.forEach((m) => map.removeLayer(m));
  markers = [];
  pathLayers.forEach((l) => map.removeLayer(l));
  pathLayers = [];
  ["origin", "dest"].forEach((t) => {
    document.getElementById(`hint-${t}`).style.display = "block";
    document.getElementById(`coords-${t}`).style.display = "none";
    document.getElementById(`card-${t}`).classList.remove("active");
  });
  document.getElementById("metrics").classList.remove("show");
  document.getElementById("directions").classList.remove("show");
  document.getElementById("directions-list").innerHTML = "";
  document.getElementById("cache-badge").style.display = "none";
  document.getElementById("set-as-row").style.display = "none";
  document.getElementById("search-input").value = "";
  document.getElementById("search-clear").style.display = "none";
  searchedLatLng = null;
  setProgress(0);
  setStatusDot("");
  setInstruction("Click the map to set your origin");
}

map.on("click", function (e) {
  hideSuggestions();
  const { lat, lng } = e.latlng;
  if (clickPoints.length >= 2) {
    resetMap();
    placePoint(lat, lng, "origin");
    return;
  }
  placePoint(lat, lng, "auto");
});
