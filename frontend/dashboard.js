const API_BASE = "";

const state = {
  home: null,
  armedSince: null,
  maxAlt: 0,
  prevPos: null,
  distanceTotal: 0,
  lastMode: null,
  lastArmed: null,
  lastFailsafe: false,
  mission: [],
  addWpMode: false,
  cachedParams: {},
  editedParams: {},
  activeConsoleTab: "events",
  autoscroll: true,
  consoleLogs: { events: [], mavlink: [], commands: [], warnings: [] },
  lastPollTime: null,
};

function haversineMeters(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = (d) => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function fmt(v, decimals, unit) {
  if (v === undefined || v === null || Number.isNaN(v)) return "--";
  return v.toFixed(decimals) + (unit || "");
}

function logLine(tab, level, message) {
  const time = new Date().toISOString().substr(11, 8);
  state.consoleLogs[tab].push({ time, level, message });
  if (state.consoleLogs[tab].length > 300) state.consoleLogs[tab].shift();
  if (state.activeConsoleTab === tab) renderConsole();
}

function renderConsole() {
  const body = document.getElementById("console-body");
  const lines = state.consoleLogs[state.activeConsoleTab];
  body.innerHTML = lines.map(l => `
    <div class="console-line ${l.level === 'WARN' ? 'warn' : l.level === 'ERROR' ? 'error' : ''}">
      <span class="time">${l.time}</span><span class="level">${l.level}</span><span class="msg">${l.message}</span>
    </div>`).join("");
  if (state.autoscroll) body.scrollTop = body.scrollHeight;
}

async function apiGet(path) {
  const res = await fetch(API_BASE + path);
  return res.json();
}
async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}
async function apiDelete(path) {
  const res = await fetch(API_BASE + path, { method: "DELETE" });
  return res.json();
}

function setText(id, text) { const e = document.getElementById(id); if (e) e.textContent = text; }
function setClass(id, cls) { const e = document.getElementById(id); if (e) e.className = "value " + cls; }

function updateTopbar(t) {
  const dot = document.getElementById("dot-connection");
  if (t.connected) {
    dot.className = "dot ok";
    setText("stat-connection", "Connected");
    document.getElementById("stat-connection").prepend(dot);
    setClass("stat-connection", "ok");
  } else {
    dot.className = "dot off";
    setText("stat-connection", "Disconnected");
    document.getElementById("stat-connection").prepend(dot);
    setClass("stat-connection", "danger");
  }

  setText("stat-mode", t.flight_mode || "--");
  setText("stat-armed", t.armed ? "ARMED" : "DISARMED");
  setClass("stat-armed", t.armed ? "danger" : "ok");

  setText("stat-battery", fmt(t.battery_voltage, 1, "V") + " " + (t.battery_percentage >= 0 ? t.battery_percentage + "%" : "--"));
  setClass("stat-battery", t.battery_percentage >= 0 && t.battery_percentage < 20 ? "danger" : "ok");

  setText("stat-gps", (t.gps_fix_type >= 3 ? "3D FIX" : t.gps_fix_type === 2 ? "2D FIX" : "NO FIX") + " " + t.gps_satellites + " SAT");
  setClass("stat-gps", t.gps_fix_type >= 3 ? "ok" : "warn");

  setText("stat-time", new Date().toISOString().substr(11, 8) + " UTC");
}

function updateLeftPanel(t) {
  setText("tel-roll", fmt(t.roll, 1, "\u00B0"));
  setText("tel-pitch", fmt(t.pitch, 1, "\u00B0"));
  setText("tel-yaw", fmt(t.yaw, 1, "\u00B0"));
  setText("tel-alt-tape", fmt(t.relative_alt, 1));

  setText("sys-gps", (t.gps_fix_type >= 3 ? "3D FIX" : t.gps_fix_type === 2 ? "2D FIX" : "NO FIX") + " (" + t.gps_satellites + ")");
  setClass("sys-gps", t.gps_fix_type >= 3 ? "ok" : "warn");

  // ekf_ok / compass_ok are null when the vehicle hasn't reported that sensor
  // as present (shown as N/A), or true/false once SYS_STATUS has arrived.
  if (t.ekf_ok === null || t.ekf_ok === undefined) {
    setText("sys-ekf", "N/A");
    setClass("sys-ekf", "muted");
  } else {
    setText("sys-ekf", t.ekf_ok ? "OK" : "FAIL");
    setClass("sys-ekf", t.ekf_ok ? "ok" : "danger");
  }

  if (t.compass_ok === null || t.compass_ok === undefined) {
    setText("sys-compass", "N/A");
    setClass("sys-compass", "muted");
  } else {
    setText("sys-compass", t.compass_ok ? "OK" : "FAIL");
    setClass("sys-compass", t.compass_ok ? "ok" : "danger");
  }

  if (t.rc_rssi === null || t.rc_rssi === undefined) {
    setText("sys-rc", "N/A");
    setClass("sys-rc", "muted");
  } else {
    const pct = Math.round((t.rc_rssi / 254) * 100);
    setText("sys-rc", `OK (${pct}%)`);
    setClass("sys-rc", pct < 30 ? "warn" : "ok");
  }

  setText("sys-heartbeat", t.connected ? "OK" : "LOST");
  setClass("sys-heartbeat", t.connected ? "ok" : "danger");

  setText("sys-failsafe", t.failsafe_triggered ? t.failsafe_reason : "NONE");
  setClass("sys-failsafe", t.failsafe_triggered ? "danger" : "ok");

  setText("tel-alt", fmt(t.relative_alt, 1, " m"));
  setText("tel-gspeed", fmt(t.groundspeed, 1, " m/s"));
  setText("tel-aspeed", fmt(t.airspeed, 1, " m/s"));
  setText("tel-vspeed", fmt(t.climb_rate, 1, " m/s"));
  setText("tel-voltage", fmt(t.battery_voltage, 1, " V"));
  setText("tel-battpct", (t.battery_percentage >= 0 ? t.battery_percentage : "--") + " %");
  setText("tel-current", t.battery_current >= 0 ? fmt(t.battery_current, 1, " A") : "--");
  setText("tel-heading", fmt(t.heading, 0, "\u00B0"));

  if (t.relative_alt > state.maxAlt) state.maxAlt = t.relative_alt;
  setText("tel-maxalt", fmt(state.maxAlt, 1, " m"));

  if (t.armed && state.armedSince === null) state.armedSince = Date.now();
  if (!t.armed) state.armedSince = null;
  if (state.armedSince) {
    const secs = Math.floor((Date.now() - state.armedSince) / 1000);
    const mm = String(Math.floor(secs / 60)).padStart(2, "0");
    const ss = String(secs % 60).padStart(2, "0");
    setText("tel-flighttime", `${mm}:${ss}`);
  } else {
    setText("tel-flighttime", "00:00");
  }

  if (t.connected && t.gps_fix_type >= 2 && t.latitude !== 0) {
    if (!state.home) {
      state.home = { lat: t.latitude, lng: t.longitude };
      AeroMap.setHome(t.latitude, t.longitude);
    }
    if (state.prevPos) {
      const d = haversineMeters(state.prevPos.lat, state.prevPos.lng, t.latitude, t.longitude);
      if (d > 0.3) state.distanceTotal += d;
    }
    state.prevPos = { lat: t.latitude, lng: t.longitude };

    const homeDist = haversineMeters(state.home.lat, state.home.lng, t.latitude, t.longitude);
    setText("tel-homedist", fmt(homeDist, 0, " m"));
  }
  setText("tel-distance", fmt(state.distanceTotal, 0, " m"));
}

function updateCenterPanel(t) {
  setText("strip-lat", fmt(t.latitude, 6));
  setText("strip-lon", fmt(t.longitude, 6));
  setText("strip-alt", fmt(t.relative_alt, 1, " m"));
  setText("strip-hdg", fmt(t.heading, 0, "\u00B0"));
  setText("strip-gspeed", fmt(t.groundspeed, 1, " m/s"));
  setText("strip-aspeed", fmt(t.airspeed, 1, " m/s"));

  if (t.latitude !== 0 || t.longitude !== 0) {
    AeroMap.updateVehicle(t.latitude, t.longitude, t.heading);
  }
}

function checkStateTransitions(t) {
  if (state.lastMode !== null && t.flight_mode !== state.lastMode) {
    logLine("events", "INFO", `Mode changed to ${t.flight_mode}`);
  }
  state.lastMode = t.flight_mode;

  if (state.lastArmed !== null && t.armed !== state.lastArmed) {
    logLine("events", "INFO", t.armed ? "Vehicle armed" : "Vehicle disarmed");
  }
  state.lastArmed = t.armed;

  if (t.failsafe_triggered && !state.lastFailsafe) {
    logLine("warnings", "WARN", t.failsafe_reason);
  } else if (!t.failsafe_triggered && state.lastFailsafe) {
    logLine("warnings", "INFO", "Failsafe cleared");
  }
  state.lastFailsafe = t.failsafe_triggered;
}

async function pollTelemetry() {
  try {
    const t = await apiGet("/api/telemetry");
    const now = Date.now();
    if (state.lastPollTime) {
      const rate = 1000 / (now - state.lastPollTime);
      document.getElementById("footer-rate").textContent = rate.toFixed(1) + " Hz";
    }
    state.lastPollTime = now;

    updateTopbar(t);
    updateLeftPanel(t);
    updateCenterPanel(t);
    checkStateTransitions(t);
    AeroPFD.update(t.roll, t.pitch, t.yaw, t.climb_rate);

    document.getElementById("footer-status").textContent = "Connected and receiving telemetry";
    document.getElementById("footer-status").className = "ok";
    document.getElementById("footer-backend").textContent = "Running";
    document.getElementById("footer-backend").className = "ok";
  } catch (e) {
    document.getElementById("footer-status").textContent = "Backend unreachable";
    document.getElementById("footer-status").className = "danger";
    document.getElementById("footer-backend").textContent = "Unreachable";
    document.getElementById("footer-backend").className = "danger";
  }
}

async function sendCommand(path, body, label, tab = "commands") {
  logLine(tab, "INFO", `Sending: ${label}...`);
  try {
    const res = await apiPost(path, body);
    if (res.success) {
      logLine(tab, "INFO", `${label}: ${res.message}`);
    } else {
      logLine(tab, "ERROR", `${label} failed: ${res.error || res.message}`);
    }
    return res;
  } catch (e) {
    logLine(tab, "ERROR", `${label} failed: ${e.message}`);
    return { success: false, error: e.message };
  }
}

function confirmAction(message) {
  return window.confirm(message);
}

function wireControls() {
  document.getElementById("btn-arm").onclick = () => {
    if (confirmAction("Arm the vehicle? Confirm the vehicle is safe to arm.")) {
      sendCommand("/api/command/arm", { arm: true }, "Arm");
    }
  };
  document.getElementById("btn-disarm").onclick = () => {
    sendCommand("/api/command/arm", { arm: false }, "Disarm");
  };
  document.getElementById("btn-takeoff").onclick = () => {
    const alt = prompt("Takeoff altitude (meters):", "10");
    if (alt === null) return;
    const altNum = parseFloat(alt);
    if (isNaN(altNum) || altNum <= 0) { alert("Enter a valid positive altitude."); return; }
    if (confirmAction(`Take off to ${altNum}m?`)) {
      sendCommand("/api/command/takeoff", { altitude: altNum }, `Takeoff to ${altNum}m`);
    }
  };
  document.getElementById("btn-land").onclick = () => {
    if (confirmAction("Land the vehicle now?")) sendCommand("/api/command/land", {}, "Land");
  };
  document.getElementById("btn-rtl").onclick = () => {
    if (confirmAction("Return to launch?")) sendCommand("/api/command/rtl", {}, "RTL");
  };
  document.getElementById("btn-loiter").onclick = () => sendCommand("/api/command/mode", { mode: "LOITER" }, "Mode: LOITER");
  document.getElementById("btn-guided").onclick = () => sendCommand("/api/command/mode", { mode: "GUIDED" }, "Mode: GUIDED");
  document.getElementById("btn-auto").onclick = () => sendCommand("/api/command/mode", { mode: "AUTO" }, "Mode: AUTO");

  document.getElementById("mode-select").onchange = (e) => {
    sendCommand("/api/command/mode", { mode: e.target.value }, `Mode: ${e.target.value}`);
  };

  document.getElementById("btn-power").onclick = () => {
    logLine("events", "INFO", "Refreshing telemetry connection...");
    pollTelemetry();
  };
}

function renderMissionTable() {
  const tbody = document.getElementById("mission-tbody");
  document.getElementById("wp-count").textContent = state.mission.length + " WP";

  if (state.mission.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No waypoints loaded</td></tr>`;
    AeroMap.renderMission([]);
    return;
  }

  tbody.innerHTML = state.mission.map((wp, idx) => `
    <tr data-idx="${idx}" class="${wp.selected ? 'selected' : ''}">
      <td>${idx + 1}</td><td>${wp.lat.toFixed(6)}</td><td>${wp.lng.toFixed(6)}</td><td>${wp.alt}</td><td>WAYPOINT</td>
    </tr>`).join("");

  tbody.querySelectorAll("tr").forEach(row => {
    row.onclick = () => {
      const idx = parseInt(row.dataset.idx);
      state.mission.forEach((wp, i) => wp.selected = (i === idx));
      renderMissionTable();
    };
  });

  AeroMap.renderMission(state.mission);
}

async function loadMission() {
  try {
    const res = await apiGet("/api/mission");
    if (res.success && res.waypoints) {
      state.mission = res.waypoints.map(wp => ({ lat: wp.lat, lng: wp.lng, alt: wp.alt, selected: false }));
      renderMissionTable();
      logLine("events", "INFO", `Loaded ${state.mission.length} waypoints from vehicle.`);
    }
  } catch (e) {
    logLine("events", "ERROR", "Could not load mission: " + e.message);
  }
}

function wireMission() {
  document.getElementById("btn-wp-add").onclick = () => {
    if (state.addWpMode) {
      state.addWpMode = false;
      AeroMap.disableAddMode();
      document.getElementById("btn-wp-add").style.background = "";
      logLine("events", "INFO", "Add-waypoint mode off.");
      return;
    }
    state.addWpMode = true;
    document.getElementById("btn-wp-add").style.background = "rgba(85,230,90,0.3)";
    logLine("events", "INFO", "Click the map to add a waypoint (default 50m alt).");
    AeroMap.enableAddMode((lat, lng) => {
      state.mission.push({ lat, lng, alt: 50, selected: false });
      renderMissionTable();
    });
  };

  document.getElementById("btn-wp-remove").onclick = () => {
    const idx = state.mission.findIndex(wp => wp.selected);
    if (idx === -1) { alert("Select a waypoint row first."); return; }
    state.mission.splice(idx, 1);
    renderMissionTable();
  };

  document.getElementById("btn-mission-upload").onclick = async () => {
    if (state.mission.length === 0) { alert("No waypoints to upload."); return; }
    const payload = state.mission.map(wp => ({ lat: wp.lat, lng: wp.lng, alt: wp.alt }));
    const res = await sendCommand("/api/mission", { waypoints: payload }, "Upload mission");
    if (res.success) logLine("commands", "INFO", `Mission uploaded (${payload.length} waypoints).`);
  };

  document.getElementById("btn-mission-clear").onclick = async () => {
    if (!confirmAction("Clear the entire mission on the vehicle?")) return;
    try {
      const res = await apiDelete("/api/mission");
      if (res.success) {
        state.mission = [];
        renderMissionTable();
        logLine("commands", "INFO", "Mission cleared.");
      } else {
        logLine("commands", "ERROR", "Clear failed: " + res.error);
      }
    } catch (e) {
      logLine("commands", "ERROR", "Clear failed: " + e.message);
    }
  };
}

function renderParamTable(filter) {
  const tbody = document.getElementById("param-tbody");
  const names = Object.keys(state.cachedParams).sort();
  const filtered = filter ? names.filter(n => n.toLowerCase().includes(filter.toLowerCase())) : names;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="3">No parameters loaded — click Refresh</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(name => {
    const val = state.editedParams.hasOwnProperty(name) ? state.editedParams[name] : state.cachedParams[name];
    const edited = state.editedParams.hasOwnProperty(name);
    const isInt = Number.isInteger(state.cachedParams[name]);
    return `<tr>
      <td>${name}</td>
      <td><input class="param-input ${edited ? 'edited' : ''}" data-name="${name}" value="${val}"></td>
      <td>${isInt ? "INT" : "FLOAT"}</td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll("input.param-input").forEach(inp => {
    inp.oninput = () => {
      const name = inp.dataset.name;
      state.editedParams[name] = parseFloat(inp.value);
      inp.classList.add("edited");
    };
  });
}

function wireParameters() {
  document.getElementById("param-search").oninput = (e) => renderParamTable(e.target.value);

  document.getElementById("btn-param-refresh").onclick = async () => {
    logLine("events", "INFO", "Requesting full parameter list from vehicle...");
    try {
      await apiPost("/api/params/refresh", {});
    } catch (e) {
      logLine("events", "ERROR", "Refresh request failed: " + e.message);
      return;
    }
    setTimeout(async () => {
      try {
        const res = await apiGet("/api/params");
        if (res.success) {
          state.cachedParams = res.parameters;
          state.editedParams = {};
          renderParamTable(document.getElementById("param-search").value);
          logLine("events", "INFO", `Loaded ${res.count} parameters.`);
        } else {
          logLine("events", "ERROR", "Backend returned failure fetching /api/params.");
        }
      } catch (e) {
        logLine("events", "ERROR", "Failed to fetch /api/params: " + e.message);
      }
    }, 2000);
  };

  document.getElementById("btn-param-write").onclick = async () => {
    const names = Object.keys(state.editedParams);
    if (names.length === 0) { alert("No parameter changes to write."); return; }
    if (!confirmAction(`Write ${names.length} changed parameter(s) to the vehicle?`)) return;

    for (const name of names) {
      const res = await apiPost(`/api/params/${name}`, { value: state.editedParams[name] });
      if (res.success) {
        state.cachedParams[name] = res.confirmed_value;
        logLine("commands", "INFO", `Set ${name} = ${res.confirmed_value}`);
      } else {
        logLine("commands", "ERROR", `Failed to set ${name}: ${res.error}`);
      }
    }
    state.editedParams = {};
    renderParamTable(document.getElementById("param-search").value);
  };

  document.getElementById("btn-param-load").onclick = () => {
    alert("Loading parameters from a .param file isn't supported by the backend yet. This would need a new backend route to parse and apply a parameter file.");
  };
  document.getElementById("btn-param-save").onclick = () => {
    alert("Saving parameters to a .param file isn't supported by the backend yet. This would need a new backend route to export the current parameter set.");
  };
}

function wireConsole() {
  document.querySelectorAll(".console-tab").forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll(".console-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      state.activeConsoleTab = tab.dataset.tab;
      renderConsole();
    };
  });

  document.getElementById("autoscroll-toggle").onclick = (e) => {
    state.autoscroll = !state.autoscroll;
    e.currentTarget.classList.toggle("on", state.autoscroll);
  };

  document.getElementById("btn-console-clear").onclick = () => {
    state.consoleLogs[state.activeConsoleTab] = [];
    renderConsole();
  };

  logLine("events", "INFO", "AeroGCS frontend initialized.");
  logLine("mavlink", "INFO", "Raw MAVLink message log isn't exposed over HTTP yet. See /api/logs/sessions for stored session files.");
}

document.addEventListener("DOMContentLoaded", () => {
  AeroPFD.init();
  AeroMap.init();
  wireControls();
  wireMission();
  wireParameters();
  wireConsole();
  loadMission();
  pollTelemetry();
  setInterval(pollTelemetry, 1000);
});
