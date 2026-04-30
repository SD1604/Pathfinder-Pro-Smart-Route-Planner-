// ────────────────────────────────────────────────────────────────────────
// CONFIGURATION
// ────────────────────────────────────────────────────────────────────────

// WHY: Dynamic API base means the same HTML file works locally AND deployed.
// On localhost → talks to Flask at port 5000
// On any other host → uses same-origin (works on Render, Railway, etc.)
const API_BASE =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:5000"
    : "";

// Nominatim: free OSM geocoder, no API key required.
// We add email param as courtesy to OSM — required by their usage policy.
const NOMINATIM_BASE = "https://nominatim.openstreetmap.org";
const NOMINATIM_EMAIL = "sushantduggal24@gmail.com"; // change to yours

// ────────────────────────────────────────────────────────────────────────
// STATE
// ────────────────────────────────────────────────────────────────────────
let clickPoints = []; // [[lat,lng], [lat,lng]] — origin and dest
let markers = []; // Leaflet marker objects on the map
let pathLayers = []; // Leaflet polyline objects for the route
let currentMode = "drive"; // selected transport mode
let searchedLatLng = null; // result from Nominatim search or geolocation
let searchTimeout = null; // debounce timer for search input
let directionsOpen = true; // toggle state for directions panel

// ────────────────────────────────────────────────────────────────────────
// MAP SETUP
// ────────────────────────────────────────────────────────────────────────
const map = L.map("map", {
  zoomControl: false,
  attributionControl: false,
}).setView([28.6139, 77.209], 12);

L.tileLayer(
  "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
  { maxZoom: 20 },
).addTo(map);

L.control.zoom({ position: "bottomright" }).addTo(map);

// ────────────────────────────────────────────────────────────────────────
// WEBSOCKET — Foundation for live condition updates (waterlogging, markets)
// WHY: When we add real-time data, the server will push condition changes
// here without the user refreshing. For now it just shows the connection.
// ────────────────────────────────────────────────────────────────────────
let socket = null;

function initWebSocket() {
  try {
    socket = io(API_BASE, { transports: ["websocket", "polling"] });

    socket.on("connect", () => {
      document.getElementById("live-dot").classList.add("connected");
      // Subscribe to live condition updates for the Delhi area
      socket.emit("subscribe_conditions", { city: "delhi" });
    });

    socket.on("disconnect", () => {
      document.getElementById("live-dot").classList.remove("connected");
    });

    socket.on("status", (data) => {
      console.log("Server:", data.message);
    });

    // Future: server will push waterlogging/market alerts here
    socket.on("condition_update", (data) => {
      console.log("Condition update received:", data);
      // TODO: update edge overlay on map when waterlogging system is added
    });
  } catch (e) {
    console.log("WebSocket not available — offline mode");
  }
}

initWebSocket();

// ────────────────────────────────────────────────────────────────────────
// TRANSPORT MODE
// ────────────────────────────────────────────────────────────────────────
function setMode(mode, btn) {
  currentMode = mode;
  document
    .querySelectorAll(".mode-btn")
    .forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  // If both points are set, recompute the route with the new mode
  if (clickPoints.length === 2) {
    computeRoute();
  }
}

// ────────────────────────────────────────────────────────────────────────
// NOMINATIM SEARCH
// WHY: Users type place names, not lat/lon. Nominatim converts text to
// coordinates for free. We debounce the input to avoid hammering the API
// on every keystroke — waits 400ms after the user stops typing.
// ────────────────────────────────────────────────────────────────────────
function onSearchInput() {
  clearTimeout(searchTimeout);
  const query = document.getElementById("search-input").value.trim();
  if (query.length < 3) {
    hideSuggestions();
    return;
  }
  searchTimeout = setTimeout(() => fetchSuggestions(query), 400);
}

function onSearchKey(e) {
  if (e.key === "Enter") doSearch();
  if (e.key === "Escape") hideSuggestions();
}

async function fetchSuggestions(query) {
  try {
    // Bias results to Delhi bounding box so "Nehru Place" returns Delhi, not elsewhere
    const url =
      `${NOMINATIM_BASE}/search?q=${encodeURIComponent(query + ", Delhi")}` +
      `&format=json&limit=5&email=${NOMINATIM_EMAIL}` +
      `&viewbox=76.8,28.4,77.4,28.9&bounded=1`;

    const res = await fetch(url, {
      headers: { "Accept-Language": "en" },
    });
    const data = await res.json();
    showSuggestions(data);
  } catch (err) {
    console.error("Nominatim error:", err);
  }
}

function showSuggestions(results) {
  const box = document.getElementById("search-suggestions");
  if (!results.length) {
    hideSuggestions();
    return;
  }

  box.innerHTML = results
    .map(
      (r) => `
    <div class="suggestion-item"
      onclick="selectSuggestion(${r.lat}, ${r.lon}, '${escapeAttr(r.display_name)}')">
      <div class="sug-name">${r.display_name.split(",")[0]}</div>
      <div class="sug-detail">${r.display_name.split(",").slice(1, 3).join(",").trim()}</div>
    </div>
  `,
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
  hideSuggestions();
  // Show the "set as origin / destination" buttons
  document.getElementById("set-as-row").style.display = "flex";
  // Pan map to the searched location
  map.setView(searchedLatLng, 15);
}

async function doSearch() {
  const query = document.getElementById("search-input").value.trim();
  if (!query) return;
  await fetchSuggestions(query);
}

// WHY: User may want to set searched location as origin OR destination.
// We don't assume — we ask them explicitly with two buttons.
function setSearchedPoint(type) {
  if (!searchedLatLng) return;
  const [lat, lng] = searchedLatLng;

  // Place it as if the user clicked the map at that point
  placePoint(lat, lng, type);

  // Clean up search UI
  document.getElementById("set-as-row").style.display = "none";
  document.getElementById("search-input").value = "";
  searchedLatLng = null;

  // If both points are now set, compute route
  if (clickPoints.length === 2) computeRoute();
}

// ────────────────────────────────────────────────────────────────────────
// GEOLOCATION
// WHY: "Use my location" is the most-used feature in any nav app.
// navigator.geolocation is built into every browser, no library needed.
// We show a loading state while the GPS resolves.
// ────────────────────────────────────────────────────────────────────────
function useMyLocation() {
  if (!navigator.geolocation) {
    setInstruction("Geolocation not supported by your browser");
    return;
  }

  const btn = document.getElementById("geo-btn");
  btn.classList.add("loading");
  btn.textContent = "Locating…";

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      btn.classList.remove("loading");
      btn.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke-linecap="round"/>
        </svg>
        Use my location`;

      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;

      // Store as searched point so user can assign it to origin or dest
      searchedLatLng = [lat, lng];
      document.getElementById("set-as-row").style.display = "flex";
      map.setView([lat, lng], 15);

      // Add a pulsing blue dot for current location
      const geoIcon = L.divIcon({
        className: "",
        iconAnchor: [10, 10],
        html: `<div style="
          width:20px;height:20px;border-radius:50%;
          background:rgba(52,211,153,0.3);
          border:2px solid #34d399;
          animation:pulse-dot 2s ease-in-out infinite;
        "></div>`,
      });
      L.marker([lat, lng], { icon: geoIcon }).addTo(map);
    },
    (err) => {
      btn.classList.remove("loading");
      btn.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke-linecap="round"/>
        </svg>
        Use my location`;
      setInstruction("Location access denied — check browser permissions");
    },
    { timeout: 8000, maximumAge: 60000 },
  );
}

// ────────────────────────────────────────────────────────────────────────
// MARKERS & ROUTE DRAWING
// ────────────────────────────────────────────────────────────────────────
function makeMarker(lat, lng, type) {
  const isOrigin = type === "origin";
  const color = isOrigin ? "#22d3ee" : "#818cf8";
  const outer = isOrigin ? "rgba(34,211,238,0.18)" : "rgba(129,140,248,0.18)";
  const icon = L.divIcon({
    className: "",
    iconAnchor: [18, 18],
    html: `<svg width="36" height="36" viewBox="0 0 36 36">
      <circle cx="18" cy="18" r="16" fill="${outer}" stroke="${color}" stroke-width="1"/>
      <circle cx="18" cy="18" r="6"  fill="${color}"/>
      <circle cx="18" cy="18" r="3"  fill="#060c18"/>
    </svg>`,
  });
  return L.marker([lat, lng], { icon }).addTo(map);
}

function drawRoute(coords, mode) {
  // Route color varies by mode — visual clarity at a glance
  const colors = { drive: "#22d3ee", walk: "#34d399", cycle: "#fbbf24" };
  const color = colors[mode] || "#22d3ee";

  const halo = L.polyline(coords, {
    color,
    weight: 20,
    opacity: 0.04,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(map);
  const glow = L.polyline(coords, {
    color,
    weight: 8,
    opacity: 0.12,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(map);
  const line = L.polyline(coords, {
    color,
    weight: 2.5,
    opacity: 1,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(map);
  const dash = L.polyline(coords, {
    color: "#ffffff",
    weight: 1,
    opacity: 0.12,
    dashArray: "6 10",
    lineCap: "round",
  }).addTo(map);

  pathLayers.push(halo, glow, line, dash);
  return line;
}

// ────────────────────────────────────────────────────────────────────────
// PLACE POINT  — shared logic used by click, search, and geolocation
// ────────────────────────────────────────────────────────────────────────
function placePoint(lat, lng, type) {
  // type can be 'origin' or 'dest' — or 'auto' meaning next available slot
  if (type === "auto") {
    type = clickPoints.length === 0 ? "origin" : "dest";
  }

  if (type === "origin") {
    // Replace existing origin if already set
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
    if (clickPoints.length < 2) setInstruction("Now set your destination");
  } else {
    // dest
    if (clickPoints.length === 0) {
      // Need origin first
      setInstruction("Please set your origin first");
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

// ────────────────────────────────────────────────────────────────────────
// ROUTE COMPUTATION
// ────────────────────────────────────────────────────────────────────────
function computeRoute() {
  if (clickPoints.length < 2) return;

  // Clear old route lines (not markers)
  pathLayers.forEach((l) => map.removeLayer(l));
  pathLayers = [];

  setProgress(70);
  setInstruction("Calculating route…");

  fetch(`${API_BASE}/find_path`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start: clickPoints[0],
      end: clickPoints[1],
      mode: currentMode, // WHY: tells backend which speed model to use
    }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        setInstruction(`Error: ${data.error}`);
        setProgress(0);
        return;
      }

      // Draw route — color matches mode
      const line = drawRoute(data.path, data.mode);
      map.fitBounds(line.getBounds(), { padding: [80, 80] });

      // Update metrics
      document.getElementById("dist").textContent = data.distance;
      document.getElementById("eta").textContent = data.time;
      document.getElementById("exec").textContent = data.execution_time;
      document.getElementById("nodes").textContent =
        data.nodes_visited.toLocaleString();
      document.getElementById("metrics").classList.add("show");

      // Cache badge — show if result came from cache
      const cacheBadge = document.getElementById("cache-badge");
      cacheBadge.style.display = data.cache_hit ? "inline-flex" : "none";

      // Render turn-by-turn directions
      renderDirections(data.directions || []);

      setProgress(100);
      setInstruction(
        `Route found (${data.mode_label}) — click map to start over`,
      );
    })
    .catch(() => {
      setInstruction("Could not reach server. Is Flask running?");
      setProgress(0);
    });
}

// ────────────────────────────────────────────────────────────────────────
// DIRECTIONS PANEL
// WHY: Turn-by-turn instructions extracted from OSM road names on the
// backend. We render them as a numbered list with the last step styled
// as the arrival step.
// ────────────────────────────────────────────────────────────────────────
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
  const list = document.getElementById("directions-list");
  const toggle = document.getElementById("dir-toggle");
  list.style.display = directionsOpen ? "flex" : "none";
  toggle.textContent = directionsOpen ? "hide" : "show";
}

// ────────────────────────────────────────────────────────────────────────
// UI HELPERS
// ────────────────────────────────────────────────────────────────────────
function setProgress(pct) {
  document.getElementById("progress-fill").style.width = pct + "%";
}

function setInstruction(text) {
  document.getElementById("instruction-text").textContent = text;
}

function updateCoords(type, lat, lng) {
  document.getElementById(`hint-${type}`).style.display = "none";
  document.getElementById(`coords-${type}`).style.display = "block";
  document.getElementById(`coords-${type}`).textContent =
    `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  document.getElementById(`card-${type}`).classList.add("active");
}

// ────────────────────────────────────────────────────────────────────────
// RESET
// ────────────────────────────────────────────────────────────────────────
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
  searchedLatLng = null;

  setProgress(0);
  setInstruction("Click the map to set your origin point");
}

// ────────────────────────────────────────────────────────────────────────
// MAP CLICK — original click-to-place still works alongside search
// ────────────────────────────────────────────────────────────────────────
map.on("click", function (e) {
  // Close search dropdown if open
  hideSuggestions();

  const { lat, lng } = e.latlng;

  if (clickPoints.length >= 2) {
    // Both points already set — reset and start fresh with origin
    resetMap();
    placePoint(lat, lng, "origin");
    return;
  }

  placePoint(lat, lng, "auto");
});
