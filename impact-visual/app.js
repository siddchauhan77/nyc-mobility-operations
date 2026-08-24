const cases = {
  event: {
    tabId: "tab-event",
    triggerTitle: "Street closure",
    triggerEvidence: "176 alerts · 00:00–05:00",
    demandState: "moves outward",
    supplyState: "stays inside plan",
    mismatchState: "cars in the wrong zones",
    humanDecision: "Re-stage outside closures",
    moneyImpact: "missed trips",
    timeImpact: "empty travel",
    riskImpact: "pickup friction",
    demandScale: 0.9,
    supplyScale: 0.42,
    taxiPositions: [18, 34, 52],
    mapTitle: "New Year’s alert geography",
    mapSubtitle: "Top alert zones plus the Times Square pickup collapse.",
    mapStatValue: "176",
    mapStatLabel: "alerts across 45 zones",
    mapZones: {
      "246": { count: 9, detail: "West Chelsea / Hudson Yards · 9 alerts" },
      "68": { count: 7, detail: "East Chelsea · 7 alerts" },
      "114": { count: 7, detail: "Greenwich Village South · 7 alerts" },
      "148": { count: 7, detail: "Lower East Side · 7 alerts" },
      "48": { count: 6, detail: "Clinton East · 6 alerts" },
      "79": { count: 6, detail: "East Village · 6 alerts" },
      "107": { count: 6, detail: "Gramercy · 6 alerts" },
      "144": { count: 6, detail: "Little Italy / NoLiTa · 6 alerts" },
      "186": { count: 6, detail: "Penn Station / Madison Sq West · 6 alerts" },
      "249": { count: 6, detail: "West Village · 6 alerts" },
      "230": { count: 2, critical: true, detail: "Times Sq / Theatre District · 2 alerts; 0 pickups at midnight vs 78.5 baseline" }
    },
    summary: "Street closures aligned with displaced pickup demand. A fleet operator would review driver staging outside the closure boundary and measure trips per driver-hour and empty miles."
  },
  airport: {
    tabId: "tab-airport",
    triggerTitle: "Winter storm",
    triggerEvidence: "0 pickups · baselines 230 / 325",
    demandState: "falls near zero",
    supplyState: "keeps arriving",
    mismatchState: "excess airport supply",
    humanDecision: "Verify status, redirect fleet",
    moneyImpact: "idle driver hours",
    timeImpact: "airport waiting",
    riskImpact: "dispatch waste",
    demandScale: 0.08,
    supplyScale: 0.86,
    taxiPositions: [62, 75, 88],
    mapTitle: "LaGuardia disruption signal",
    mapSubtitle: "The airport zone fell to zero pickups during two storm hours.",
    mapStatValue: "0",
    mapStatLabel: "pickups vs baselines 230 / 325",
    mapZones: {
      "138": { count: 2, critical: true, detail: "LaGuardia Airport · 0 pickups at 22:00 and 23:00" }
    },
    summary: "LaGuardia pickups fell to zero during two storm hours. A fleet operator would verify airport status before dispatch and measure waiting time and empty miles."
  },
  recovery: {
    tabId: "tab-recovery",
    triggerTitle: "Post-storm slowdown",
    triggerEvidence: "95 / 110 duration alerts",
    demandState: "remains active",
    supplyState: "moves slower",
    mismatchState: "lower fleet throughput",
    humanDecision: "Extend recovery 72 hours",
    moneyImpact: "fewer trips per hour",
    timeImpact: "longer trips",
    riskImpact: "late service",
    demandScale: 0.74,
    supplyScale: 0.45,
    taxiPositions: [28, 48, 64],
    mapTitle: "Post-storm slowdown concentration",
    mapSubtitle: "Top zones from 138 alerts between January 27 and 29.",
    mapStatValue: "138",
    mapStatLabel: "alerts across 32 zones",
    mapZones: {
      "229": { count: 23, detail: "Sutton Place / Turtle Bay North · 23 alerts" },
      "141": { count: 12, detail: "Lenox Hill West · 12 alerts" },
      "262": { count: 10, detail: "Yorkville East · 10 alerts" },
      "162": { count: 8, detail: "Midtown East · 8 alerts" },
      "48": { count: 7, detail: "Clinton East · 7 alerts" },
      "140": { count: 7, detail: "Lenox Hill East · 7 alerts" },
      "263": { count: 7, detail: "Yorkville West · 7 alerts" },
      "166": { count: 6, detail: "Morningside Heights · 6 alerts" },
      "161": { count: 5, detail: "Midtown Center · 5 alerts" },
      "170": { count: 5, detail: "Murray Hill · 5 alerts" }
    },
    summary: "Trip-duration signals remained concentrated after snowfall. A fleet operator would extend recovery monitoring and measure pickup delay and completed trips per shift."
  }
};

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const viewTabs = [...document.querySelectorAll("[data-view]")];
const views = {
  impact: document.querySelector("#impact-view"),
  "three-p": document.querySelector("#three-p-view")
};
const pipeline = document.querySelector("#pipeline");
const replay = document.querySelector("#replay");
const replayStatus = document.querySelector("#replay-status");
const decisionFlow = document.querySelector("#case-detail");
const mapShell = document.querySelector(".map-shell");
const nycMap = document.querySelector("#nyc-map");
const mapLayer = document.querySelector("#map-layer");
const mapLoading = document.querySelector("#map-loading");
const tabs = [...document.querySelectorAll("[data-case]")];
let mapFeatures = [];
let currentCase = "event";
let pipelineRunId = 0;
let pipelineTimers = [];

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function animateCount(element, target, delay, runId) {
  const duration = 520;
  const startTime = performance.now() + delay;

  function update(now) {
    if (runId !== pipelineRunId) return;
    if (now < startTime) {
      requestAnimationFrame(update);
      return;
    }

    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = formatNumber(Math.round(target * eased));

    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

function schedulePipelineStep(callback, delay, runId) {
  const timer = window.setTimeout(() => {
    if (runId === pipelineRunId) callback();
  }, delay);
  pipelineTimers.push(timer);
}

function finishPipeline(runId, announce) {
  if (runId !== pipelineRunId) return;
  pipeline.querySelectorAll(".is-replay-step").forEach((element) => element.classList.remove("is-replay-step"));
  replay.disabled = false;
  replay.textContent = "Replay flow";
  replayStatus.textContent = announce ? "Replay complete" : "Ready";
}

function runPipeline({ announce = true } = {}) {
  pipelineRunId += 1;
  const runId = pipelineRunId;
  pipelineTimers.forEach(window.clearTimeout);
  pipelineTimers = [];

  replay.disabled = true;
  replay.textContent = "Replaying…";
  replayStatus.textContent = "Starting flow";
  pipeline.querySelectorAll(".is-replay-step").forEach((element) => element.classList.remove("is-replay-step"));
  pipeline.classList.remove("is-running");
  void pipeline.offsetWidth;
  pipeline.classList.add("is-running");

  const counts = [...pipeline.querySelectorAll(".count")];
  counts.forEach((element) => {
    element.textContent = "0";
  });

  if (prefersReducedMotion) {
    const steps = [
      { selector: ".before-state", status: "Step 1 of 3: raw trip records", count: counts[0] },
      { selector: ".fde-transform", status: "Step 2 of 3: scope, clean, rank, prove" },
      { selector: ".after-state", status: "Step 3 of 3: ranked prompts", count: counts[1] }
    ];

    steps.forEach((step, index) => {
      schedulePipelineStep(() => {
        pipeline.querySelectorAll(".is-replay-step").forEach((element) => element.classList.remove("is-replay-step"));
        pipeline.querySelector(step.selector).classList.add("is-replay-step");
        if (step.count) step.count.textContent = formatNumber(Number(step.count.dataset.value));
        replayStatus.textContent = step.status;
      }, index * 420, runId);
    });
    schedulePipelineStep(() => finishPipeline(runId, announce), 1420, runId);
    return;
  }

  counts.forEach((element, index) => {
    animateCount(element, Number(element.dataset.value), index * 100, runId);
  });
  schedulePipelineStep(() => finishPipeline(runId, announce), 850, runId);
}

function setText(id, value) {
  document.querySelector(`#${id}`).textContent = value;
}

function selectView(viewName, moveFocus = false, updateHash = true) {
  if (!views[viewName]) return;

  viewTabs.forEach((tab) => {
    const active = tab.dataset.view === viewName;
    tab.setAttribute("aria-selected", String(active));
    tab.setAttribute("tabindex", active ? "0" : "-1");
    if (active && moveFocus) tab.focus();
  });

  Object.entries(views).forEach(([name, view]) => {
    view.hidden = name !== viewName;
  });

  document.title = viewName === "three-p"
    ? "NYC Mobility Operations | 3Ps Brief"
    : "NYC Mobility Operations | From Signal to Decision";

  if (viewName === "impact" && mapFeatures.length) updateMap(currentCase);
  if (updateHash) history.replaceState(null, "", viewName === "three-p" ? "#three-ps" : location.pathname + location.search);
  window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" });
}

function geometryRings(geometry) {
  if (geometry.type === "Polygon") return geometry.coordinates;
  return geometry.coordinates.flat();
}

function buildProjection(features) {
  const coordinates = features.flatMap((feature) => geometryRings(feature.geometry).flat());
  const longitudes = coordinates.map((point) => point[0]);
  const latitudes = coordinates.map((point) => point[1]);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const longitudeScale = Math.cos(((minLatitude + maxLatitude) / 2) * Math.PI / 180);
  const rawWidth = (maxLongitude - minLongitude) * longitudeScale;
  const rawHeight = maxLatitude - minLatitude;
  const padding = 24;
  const width = 760;
  const height = 500;
  const scale = Math.min((width - padding * 2) / rawWidth, (height - padding * 2) / rawHeight);
  const renderedWidth = rawWidth * scale;
  const renderedHeight = rawHeight * scale;
  const offsetX = (width - renderedWidth) / 2;
  const offsetY = (height - renderedHeight) / 2;

  return ([longitude, latitude]) => [
    offsetX + (longitude - minLongitude) * longitudeScale * scale,
    height - offsetY - (latitude - minLatitude) * scale
  ];
}

function geometryPath(geometry, project) {
  return geometryRings(geometry).map((ring) => {
    return ring.map((point, index) => {
      const [x, y] = project(point);
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(" ") + " Z";
  }).join(" ");
}

function showMapDetail(path) {
  if (!path.classList.contains("is-focus")) return;
  setText("map-tooltip-zone", path.dataset.zone);
  setText("map-tooltip-detail", path.dataset.detail);
}

function updateMapViewport(focusPaths) {
  const mapWidth = 760;
  const mapHeight = 500;
  const mapAspect = mapWidth / mapHeight;

  if (!focusPaths.length) {
    nycMap.setAttribute("viewBox", `0 0 ${mapWidth} ${mapHeight}`);
    return;
  }

  const bounds = focusPaths.map((path) => path.getBBox());
  const minX = Math.min(...bounds.map((box) => box.x));
  const minY = Math.min(...bounds.map((box) => box.y));
  const maxX = Math.max(...bounds.map((box) => box.x + box.width));
  const maxY = Math.max(...bounds.map((box) => box.y + box.height));
  const focusWidth = Math.max(maxX - minX, 1);
  const focusHeight = Math.max(maxY - minY, 1);
  const paddingX = Math.max(focusWidth * 0.18, 14);
  const paddingY = Math.max(focusHeight * 0.18, 14);
  let viewWidth = focusWidth + paddingX * 2;
  let viewHeight = focusHeight + paddingY * 2;

  if (viewWidth / viewHeight > mapAspect) {
    viewHeight = viewWidth / mapAspect;
  } else {
    viewWidth = viewHeight * mapAspect;
  }

  if (viewWidth < 190) {
    const scale = 190 / viewWidth;
    viewWidth *= scale;
    viewHeight *= scale;
  }

  viewWidth = Math.min(viewWidth, mapWidth);
  viewHeight = Math.min(viewHeight, mapHeight);
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const viewX = Math.max(0, Math.min(centerX - viewWidth / 2, mapWidth - viewWidth));
  const viewY = Math.max(0, Math.min(centerY - viewHeight / 2, mapHeight - viewHeight));

  nycMap.setAttribute("viewBox", [viewX, viewY, viewWidth, viewHeight].map((value) => value.toFixed(2)).join(" "));
}

function renderMap(features) {
  const project = buildProjection(features);
  const fragment = document.createDocumentFragment();

  features.forEach((feature) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", geometryPath(feature.geometry, project));
    path.setAttribute("fill-rule", "evenodd");
    path.classList.add("taxi-zone", "is-muted");
    path.dataset.locationId = feature.properties.locationid;
    path.dataset.zone = feature.properties.zone;
    path.dataset.borough = feature.properties.borough;
    path.addEventListener("mouseenter", () => showMapDetail(path));
    path.addEventListener("focus", () => showMapDetail(path));
    fragment.appendChild(path);
  });

  mapLayer.replaceChildren(fragment);
  mapFeatures = [...mapLayer.querySelectorAll(".taxi-zone")];
  mapLoading.classList.add("is-hidden");
  updateMap(currentCase);
}

function updateMap(caseName) {
  currentCase = caseName;
  const selected = cases[caseName];
  setText("map-title", selected.mapTitle);
  setText("map-subtitle", selected.mapSubtitle);
  setText("map-stat-value", selected.mapStatValue);
  setText("map-stat-label", selected.mapStatLabel);
  setText("map-tooltip-zone", "Select a highlighted zone");
  setText("map-tooltip-detail", "Alert evidence appears here.");

  mapShell.classList.remove("is-changing");
  void mapShell.offsetWidth;
  mapShell.classList.add("is-changing");

  mapFeatures.forEach((path) => {
    const focus = selected.mapZones[path.dataset.locationId];
    path.classList.toggle("is-focus", Boolean(focus));
    path.classList.toggle("is-muted", !focus);
    path.classList.toggle("is-critical", Boolean(focus?.critical));

    if (focus) {
      path.dataset.detail = focus.detail;
      path.setAttribute("tabindex", "0");
      path.setAttribute("role", "button");
      path.setAttribute("aria-label", focus.detail);
    } else {
      path.removeAttribute("tabindex");
      path.removeAttribute("role");
      path.removeAttribute("aria-label");
      delete path.dataset.detail;
    }
  });

  updateMapViewport(mapFeatures.filter((path) => path.classList.contains("is-focus")));
}

async function loadMap() {
  try {
    const response = await fetch("data/taxi-zones.geojson");
    if (!response.ok) throw new Error(`Map request failed with HTTP ${response.status}`);
    const geojson = await response.json();
    renderMap(geojson.features);
  } catch (error) {
    mapLoading.textContent = "Map requires the localhost server. See README instructions.";
    console.error(error);
  }
}

function selectCase(caseName, moveFocus = false) {
  const selected = cases[caseName];
  if (!selected) return;

  tabs.forEach((tab) => {
    const active = tab.dataset.case === caseName;
    tab.setAttribute("aria-selected", String(active));
    tab.setAttribute("tabindex", active ? "0" : "-1");
    if (active && moveFocus) tab.focus();
  });

  decisionFlow.setAttribute("aria-labelledby", selected.tabId);
  decisionFlow.classList.remove("is-changing");
  void decisionFlow.offsetWidth;
  decisionFlow.classList.add("is-changing");
  updateMap(caseName);

  setText("trigger-title", selected.triggerTitle);
  setText("trigger-evidence", selected.triggerEvidence);
  setText("demand-state", selected.demandState);
  setText("supply-state", selected.supplyState);
  setText("mismatch-state", selected.mismatchState);
  setText("human-decision", selected.humanDecision);
  setText("money-impact", selected.moneyImpact);
  setText("time-impact", selected.timeImpact);
  setText("risk-impact", selected.riskImpact);
  setText("case-summary", selected.summary);

  document.querySelector("#demand-flow").style.transform = `scaleX(${selected.demandScale})`;
  document.querySelector("#supply-flow").style.transform = `scaleX(${selected.supplyScale})`;
  document.querySelectorAll(".taxi").forEach((taxi, index) => {
    taxi.style.left = `${selected.taxiPositions[index]}%`;
  });
}

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectCase(tab.dataset.case));
  tab.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (index + direction + tabs.length) % tabs.length;
    selectCase(tabs[nextIndex].dataset.case, true);
  });
});

viewTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectView(tab.dataset.view));
  tab.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (index + direction + viewTabs.length) % viewTabs.length;
    selectView(viewTabs[nextIndex].dataset.view, true);
  });
});

window.addEventListener("hashchange", () => {
  selectView(location.hash === "#three-ps" ? "three-p" : "impact", false, false);
});

replay.addEventListener("click", () => runPipeline());

runPipeline({ announce: false });
selectCase("event");
loadMap();
selectView(location.hash === "#three-ps" ? "three-p" : "impact", false, false);
