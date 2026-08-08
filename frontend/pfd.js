const AeroPFD = (function () {
  const NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  let horizonGroup = null;
  let compassRoseGroup = null;
  let compassLabel = null;
  let vsiNeedle = null;
  let vsiValueEl = null;

  function buildHorizon() {
    const container = document.getElementById("horizon-container");
    const svg = el("svg", { viewBox: "0 0 220 220", width: "130", height: "130" });

    const defs = el("defs", {});
    const clip = el("clipPath", { id: "pfd-clip" });
    clip.appendChild(el("circle", { cx: 110, cy: 110, r: 95 }));
    defs.appendChild(clip);
    svg.appendChild(defs);

    horizonGroup = el("g", { "clip-path": "url(#pfd-clip)" });
    horizonGroup.appendChild(el("rect", { x: -80, y: -140, width: 380, height: 260, fill: "#1B4E73" }));
    horizonGroup.appendChild(el("rect", { x: -80, y: 110, width: 380, height: 260, fill: "#6B4A22" }));
    horizonGroup.appendChild(el("line", { x1: -80, y1: 110, x2: 300, y2: 110, stroke: "#35E59A", "stroke-width": 2 }));
    for (let p = -20; p <= 20; p += 10) {
      if (p === 0) continue;
      const y = 110 - p * 3;
      const w = (p % 20 === 0) ? 50 : 30;
      horizonGroup.appendChild(el("line", { x1: 110 - w, y1: y, x2: 110 + w, y2: y, stroke: "#F2FAF7", "stroke-width": 1.5, opacity: 0.85 }));
    }
    svg.appendChild(horizonGroup);

    svg.appendChild(el("circle", { cx: 110, cy: 110, r: 96, fill: "none", stroke: "#31574D", "stroke-width": 2 }));
    svg.appendChild(el("line", { x1: 60, y1: 110, x2: 92, y2: 110, stroke: "#F2FAF7", "stroke-width": 3 }));
    svg.appendChild(el("line", { x1: 128, y1: 110, x2: 160, y2: 110, stroke: "#F2FAF7", "stroke-width": 3 }));
    svg.appendChild(el("circle", { cx: 110, cy: 110, r: 3, fill: "#F2FAF7" }));

    container.innerHTML = "";
    container.appendChild(svg);
  }

  function buildCompass() {
    const container = document.getElementById("compass-container");
    const svg = el("svg", { viewBox: "0 0 200 200", width: "105", height: "105" });

    svg.appendChild(el("circle", { cx: 100, cy: 100, r: 90, fill: "#123029", stroke: "#31574D", "stroke-width": 1.5 }));

    compassRoseGroup = el("g", {});
    const dirs = [["N", 0, "#FF4B45"], ["E", 90, "#B7CBC3"], ["S", 180, "#B7CBC3"], ["W", 270, "#B7CBC3"]];
    dirs.forEach(([label, angle, color]) => {
      const rad = (angle - 90) * Math.PI / 180;
      const x = 100 + 68 * Math.cos(rad);
      const y = 100 + 68 * Math.sin(rad);
      const t = el("text", { x, y, "text-anchor": "middle", "dominant-baseline": "middle", fill: color, "font-size": 14, "font-weight": 700, "font-family": "Inter, sans-serif" });
      t.textContent = label;
      compassRoseGroup.appendChild(t);
    });
    for (let i = 0; i < 36; i++) {
      const rad = (i * 10 - 90) * Math.PI / 180;
      const inner = i % 9 === 0 ? 78 : 84;
      const x1 = 100 + inner * Math.cos(rad), y1 = 100 + inner * Math.sin(rad);
      const x2 = 100 + 88 * Math.cos(rad), y2 = 100 + 88 * Math.sin(rad);
      compassRoseGroup.appendChild(el("line", { x1, y1, x2, y2, stroke: "#4B7568", "stroke-width": 1 }));
    }
    svg.appendChild(compassRoseGroup);

    svg.appendChild(el("polygon", { points: "100,18 106,32 94,32", fill: "#35E59A" }));

    compassLabel = el("text", { x: 100, y: 106, "text-anchor": "middle", fill: "#F2FAF7", "font-size": 20, "font-weight": 700, "font-family": "JetBrains Mono, monospace" });
    compassLabel.textContent = "--";
    svg.appendChild(compassLabel);

    container.innerHTML = "";
    container.appendChild(svg);
  }

  function buildVSI() {
    const container = document.getElementById("vsi-container");
    const svg = el("svg", { viewBox: "0 0 200 200", width: "105", height: "105" });

    svg.appendChild(el("circle", { cx: 100, cy: 100, r: 90, fill: "#123029", stroke: "#31574D", "stroke-width": 1.5 }));

    for (let v = -10; v <= 10; v += 5) {
      const angle = (v / 10) * 120;
      const rad = (angle - 90) * Math.PI / 180;
      const x1 = 100 + 78 * Math.cos(rad), y1 = 100 + 78 * Math.sin(rad);
      const x2 = 100 + 88 * Math.cos(rad), y2 = 100 + 88 * Math.sin(rad);
      svg.appendChild(el("line", { x1, y1, x2, y2, stroke: "#4B7568", "stroke-width": 1.5 }));
      const lx = 100 + 62 * Math.cos(rad), ly = 100 + 62 * Math.sin(rad);
      const t = el("text", { x: lx, y: ly, "text-anchor": "middle", "dominant-baseline": "middle", fill: "#A7BBB4", "font-size": 10, "font-family": "Inter, sans-serif" });
      t.textContent = String(-v);
      svg.appendChild(t);
    }

    vsiNeedle = el("line", { x1: 100, y1: 100, x2: 100, y2: 25, stroke: "#35E59A", "stroke-width": 2.5 });
    svg.appendChild(vsiNeedle);
    svg.appendChild(el("circle", { cx: 100, cy: 100, r: 4, fill: "#35E59A" }));

    container.innerHTML = "";
    container.appendChild(svg);

    vsiValueEl = document.createElement("div");
    vsiValueEl.style.textAlign = "center";
    vsiValueEl.style.marginTop = "3px";
    vsiValueEl.style.fontFamily = "JetBrains Mono, monospace";
    vsiValueEl.style.fontSize = "12px";
    vsiValueEl.style.fontWeight = "600";
    vsiValueEl.textContent = "-- m/s";
    container.appendChild(vsiValueEl);
  }

  function init() {
    buildHorizon();
    buildCompass();
    buildVSI();
  }

  function update(roll, pitch, yaw, climbRate) {
    if (horizonGroup) {
      const pitchOffsetPx = pitch * 3;
      horizonGroup.setAttribute("transform", `rotate(${-roll} 110 ${110 + pitchOffsetPx}) translate(0 ${pitchOffsetPx})`);
    }
    if (compassRoseGroup) compassRoseGroup.setAttribute("transform", `rotate(${-yaw} 100 100)`);
    if (compassLabel) compassLabel.textContent = Math.round(yaw) + "\u00B0";

    if (vsiNeedle) {
      const clamped = Math.max(-10, Math.min(10, climbRate));
      const angle = (clamped / 10) * 120;
      const rad = (angle - 90) * Math.PI / 180;
      const x2 = 100 + 65 * Math.cos(rad), y2 = 100 + 65 * Math.sin(rad);
      vsiNeedle.setAttribute("x2", x2);
      vsiNeedle.setAttribute("y2", y2);
    }
    if (vsiValueEl) vsiValueEl.textContent = climbRate.toFixed(1) + " m/s";
  }

  return { init, update };
})();
