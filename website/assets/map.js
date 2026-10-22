(function () {
  "use strict";
  var cfgEl = document.getElementById("map-config"), mapEl = document.getElementById("map");
  var summary = document.getElementById("map-summary");
  if (!cfgEl || !mapEl) return;
  if (!window.L || !L.markerClusterGroup) {
    summary.textContent = "The map could not load. The same records are in the open data.";
    return;
  }
  var cfg = JSON.parse(cfgEl.textContent), weeks = cfg.weeks, last = weeks.length - 1;
  var state = { cat: "all", from: 0, to: last };
  var fromSel = document.getElementById("from-week"), toSel = document.getElementById("to-week");
  var slider = document.getElementById("week-slider"), out = document.getElementById("week-out");
  var small = window.matchMedia("(max-width: 639px)").matches;
  var map = L.map(mapEl, { scrollWheelZoom: false, minZoom: small ? 1 : 2, maxZoom: 9,
    maxBounds: [[-75, -200], [88, 200]], maxBoundsViscosity: 0.8 });
  map.setView(small ? [47, 12] : [47, 14], small ? 2 : 3);
  mapEl.outbreakLensMap = map;   // handy for testing and for embedding scripts
  if (cfg.tiles && cfg.tiles.url) {
    L.tileLayer(cfg.tiles.url, { attribution: cfg.tiles.attribution, subdomains: "abcd", maxZoom: 19 }).addTo(map);
  } else if (cfg.basemap) {
    map.attributionControl.addAttribution("Basemap: Natural Earth");
    fetch(cfg.basemap, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (gj) {
      L.geoJSON(gj, { interactive: false, renderer: L.canvas({ padding: 0.5 }),
        style: { color: "#d5cec1", weight: 0.7, fillColor: "#fbf9f4", fillOpacity: 1 } }).addTo(map).bringToBack();
    }).catch(function () {});
  }
  var group = L.markerClusterGroup({
    showCoverageOnHover: false, maxClusterRadius: 44, spiderfyOnMaxZoom: true,
    iconCreateFunction: function (c) {
      var n = c.getChildCount(), s = n < 10 ? 30 : n < 50 ? 36 : n < 200 ? 42 : 48;
      return L.divIcon({ html: '<span class="cluster">' + n + "</span>", className: "cluster-wrap", iconSize: [s, s] });
    }
  });
  map.addLayer(group);
  var markers = [];

  function total(w) {
    var t = 0;
    for (var i = state.from; i <= state.to; i++) t += w[weeks[i][0]] || 0;
    return t;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function link(text, href) {
    if (!/^https?:\/\//.test(href || "")) return el("span", null, text);
    var a = el("a", null, text);
    a.href = href; a.target = "_blank"; a.rel = "noopener";
    return a;
  }
  function popup(m) {
    var p = m.feature.properties, n = total(p.weeks), box = el("div", "pop");
    var unit = n === 1 ? p.unit : (cfg.units[p.unit] || p.unit);
    box.appendChild(el("p", "pop-title", p.title));
    box.appendChild(el("p", "pop-place", p.place));
    var num = el("p");
    num.appendChild(el("span", "pop-n", n.toLocaleString("en-GB")));
    num.appendChild(document.createTextNode(" " + unit + (/season/.test(unit) ? "" : " in the weeks shown")));
    box.appendChild(num);
    if (p.note) box.appendChild(el("p", "pop-meta", p.note));
    var links = el("p", "pop-links");
    links.appendChild(link("Source: " + p.src, p.url));
    (p.also || []).forEach(function (x) {
      links.appendChild(document.createTextNode(" · "));
      links.appendChild(link("Also: " + x[0], x[1]));
    });
    box.appendChild(links);
    return box;
  }
  function marker(f) {
    var p = f.properties, c = f.geometry.coordinates, st = cfg.cats[p.cat] || cfg.cats.other;
    var icon = L.divIcon({ className: "pin-wrap", iconSize: null,
      html: '<span class="pin" style="--c:' + st.colour + '"><i></i>' + st.code + "</span>" });
    var m = L.marker([c[1], c[0]], { icon: icon, title: st.label + ": " + p.place, riseOnHover: true });
    m.feature = f;
    m.bindPopup(function () { return popup(m); }, { maxWidth: 280, autoPanPadding: [16, 16] });
    return m;
  }
  function describe() {
    return state.from === 0 && state.to === last ? "Weeks starting " + weeks[0][1] + " to " + weeks[last][1]
      : state.from === state.to ? "Week starting " + weeks[state.to][1]
      : "Weeks starting " + weeks[state.from][1] + " to " + weeks[state.to][1];
  }
  function render() {
    var show = [];
    markers.forEach(function (m) {
      var p = m.feature.properties;
      if (state.cat !== "all" && p.cat !== state.cat) return;
      if (total(p.weeks) > 0) show.push(m);
    });
    group.clearLayers();
    group.addLayers(show);
    var what = state.cat === "all" ? "any of the eight diseases" : cfg.cats[state.cat].phrase;
    summary.textContent = show.length
      ? show.length.toLocaleString("en-GB") + (show.length === 1 ? " place" : " places") + " with reports of " + what + " in these weeks."
      : "No reports of " + what + " in these weeks.";
  }
  function sync() {
    fromSel.value = String(state.from);
    toSel.value = String(state.to);
    slider.value = String(state.to);
    out.textContent = describe();
    slider.setAttribute("aria-valuetext", describe());
  }
  Array.prototype.forEach.call(document.querySelectorAll('input[name="map-cat"]'), function (r) {
    r.addEventListener("change", function () { state.cat = r.value; render(); });
  });
  fromSel.addEventListener("change", function () {
    state.from = +fromSel.value; if (state.to < state.from) state.to = state.from; sync(); render();
  });
  toSel.addEventListener("change", function () {
    state.to = +toSel.value; if (state.from > state.to) state.from = state.to; sync(); render();
  });
  slider.addEventListener("input", function () {
    state.to = +slider.value; if (state.from > state.to) state.from = state.to; sync(); render();
  });
  fetch(cfg.data, { credentials: "same-origin" })
    .then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
    .then(function (gj) { markers = gj.features.map(marker); sync(); render(); })
    .catch(function () { summary.textContent = "The map data did not load. The same records are in the open data."; });
})();
