const AeroMap = (function () {
  let map = null;
  let vehicleMarker = null;
  let trailLine = null;
  let trailPoints = [];
  let homeMarker = null;
  let missionLine = null;
  let missionMarkers = [];
  let addModeCallback = null;

  const vehicleIconHtml = `
    <div style="width:26px;height:26px;transform-origin:50% 50%;" id="vehicle-rot">
      <svg viewBox="0 0 24 24" width="26" height="26">
        <polygon points="12,2 20,20 12,15 4,20" fill="#3DB7FF" stroke="#0B211C" stroke-width="0.5"/>
      </svg>
    </div>`;

  function init() {
    map = L.map("map", { zoomControl: true, attributionControl: false }).setView([0, 0], 2);

    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 20,
    }).addTo(map);

    trailLine = L.polyline([], { color: "#D8E84A", weight: 2, opacity: 0.8 }).addTo(map);

    map.on("click", (e) => {
      if (addModeCallback) {
        addModeCallback(e.latlng.lat, e.latlng.lng);
      }
    });
  }

  function updateVehicle(lat, lng, headingDeg) {
    if (!lat || !lng) return;
    const latlng = [lat, lng];

    if (!vehicleMarker) {
      const icon = L.divIcon({ html: vehicleIconHtml, className: "", iconSize: [26, 26], iconAnchor: [13, 13] });
      vehicleMarker = L.marker(latlng, { icon, zIndexOffset: 1000 }).addTo(map);
      map.setView(latlng, 18);
    } else {
      vehicleMarker.setLatLng(latlng);
    }

    const rotEl = document.getElementById("vehicle-rot");
    if (rotEl) rotEl.style.transform = `rotate(${headingDeg}deg)`;

    trailPoints.push(latlng);
    if (trailPoints.length > 800) trailPoints.shift();
    trailLine.setLatLngs(trailPoints);
  }

  function setHome(lat, lng) {
    if (homeMarker) return;
    const icon = L.divIcon({
      html: `<div style="width:22px;height:22px;border-radius:50%;background:#123029;border:2px solid #35E59A;display:flex;align-items:center;justify-content:center;"><i class="fa-solid fa-house" style="color:#35E59A;font-size:11px;"></i></div>`,
      className: "", iconSize: [22, 22], iconAnchor: [11, 11],
    });
    homeMarker = L.marker([lat, lng], { icon }).addTo(map);
  }

  function renderMission(waypoints) {
    if (missionLine) { map.removeLayer(missionLine); missionLine = null; }
    missionMarkers.forEach(m => map.removeLayer(m));
    missionMarkers = [];

    if (!waypoints || waypoints.length === 0) return;

    const latlngs = waypoints.map(wp => [wp.lat, wp.lng]);
    missionLine = L.polyline(latlngs, { color: "#D8E84A", weight: 2, dashArray: "6 4" }).addTo(map);

    waypoints.forEach((wp, idx) => {
      const icon = L.divIcon({
        html: `<div style="width:22px;height:22px;border-radius:50%;background:#123029;border:2px solid #D8E84A;color:#D8E84A;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace;">${idx + 1}</div>`,
        className: "", iconSize: [22, 22], iconAnchor: [11, 11],
      });
      const marker = L.marker([wp.lat, wp.lng], { icon }).addTo(map);
      missionMarkers.push(marker);
    });
  }

  function enableAddMode(callback) { addModeCallback = callback; }
  function disableAddMode() { addModeCallback = null; }

  return { init, updateVehicle, setHome, renderMission, enableAddMode, disableAddMode };
})();
