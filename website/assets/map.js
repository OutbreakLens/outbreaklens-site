(function () {
  "use strict";
  var cfgEl = document.getElementById("map-config"), mapEl = document.getElementById("map");
  var summary = document.getElementById("map-summary");
  if (!cfgEl || !mapEl) return;
  var cfg = JSON.parse(cfgEl.textContent), weeks = cfg.weeks, last = weeks.length - 1;
  var state = { cat: "all", from: 0, to: last };
  var fromSel = document.getElementById("from-week"), toSel = document.getElementById("to-week");
  var slider = document.getElementById("week-slider"), out = document.getElementById("week-out");
  var table = document.getElementById("map-table"), tTitle = document.getElementById("map-table-title");
  var tNote = document.getElementById("map-table-note");
  var SHAPES = { domestic: "circle", wild: "triangle" }, NS = "http://www.w3.org/2000/svg";
  var feats = [], byId = {}, map = null, ready = false, popup = null, mapNote = "";

  function shapeOf(p) { return SHAPES[p.pop] || "square"; }
  function catOf(p) { return cfg.cats[p.cat] ? p.cat : "other"; }
  function total(w) {
    var t = 0;
    for (var i = state.from; i <= state.to; i++) t += w[weeks[i][0]] || 0;
    return t;
  }
  function fmt(n) { return n.toLocaleString("en-GB"); }
  function cap(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function span() {   // "weeks starting 3 Aug to 19 Oct 2026"
    var a = weeks[state.from][1], b = weeks[state.to][1];
    if (state.from === state.to) return "week starting " + b;
    if (a.slice(-4) === b.slice(-4)) a = a.slice(0, -5);
    return "weeks starting " + a + " to " + b;
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
  function glyph(shape, colour) {   // the map symbol, for the pop-up title
    var svg = document.createElementNS(NS, "svg"), s;
    svg.setAttribute("viewBox", "0 0 22 22");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    if (shape === "circle") {
      s = document.createElementNS(NS, "circle");
      s.setAttribute("cx", "11"); s.setAttribute("cy", "11"); s.setAttribute("r", "6.5");
    } else if (shape === "triangle") {
      s = document.createElementNS(NS, "polygon");
      s.setAttribute("points", "11,3.4 19.75,18.6 2.25,18.6");
    } else {
      s = document.createElementNS(NS, "rect");
      s.setAttribute("x", "5.3"); s.setAttribute("y", "5.3"); s.setAttribute("width", "11.4"); s.setAttribute("height", "11.4");
    }
    s.setAttribute("fill", colour);
    svg.appendChild(s);
    return svg;
  }

  // ---------- pop-ups ----------
  function record(f) {
    var p = f.properties, n = total(p.weeks), box = el("div", "pop");
    var unit = n === 1 ? p.unit : (cfg.units[p.unit] || p.unit);
    var t = el("p", "pop-title");
    t.appendChild(glyph(shapeOf(p), cfg.cats[catOf(p)].colour));
    t.appendChild(document.createTextNode(p.title));
    box.appendChild(t);
    box.appendChild(el("p", "pop-place", p.place));
    box.appendChild(el("p", "pop-pop", cfg.pop[p.pop] || cfg.pop[""]));
    var num = el("p", "pop-num");
    num.appendChild(el("span", "pop-n", fmt(n)));
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
  function openPopup(at, list) {
    if (!list.length) return;
    var node;
    if (list.length === 1) {
      node = record(list[0]);
    } else {
      node = el("div");
      node.appendChild(el("p", "pop-count", list.length + " records here"));
      var wrap = el("div", "pop-list");
      list.sort(function (a, b) { return total(b.properties.weeks) - total(a.properties.weeks); })
        .forEach(function (f) { wrap.appendChild(record(f)); });
      node.appendChild(wrap);
    }
    if (popup) popup.remove();
    var pp = new maplibregl.Popup({ maxWidth: "300px", offset: 12, focusAfterOpen: true });
    pp.setLngLat(at).setDOMContent(node).addTo(map);
    pp.on("close", function () { if (popup === pp) popup = null; });
    popup = pp;
  }

  // ---------- the table under the map ----------
  function renderTable(list) {
    if (!table) return;
    var all = state.cat === "all", rows = {}, keys = [], split = 0;
    list.forEach(function (f) {
      var p = f.properties, n = total(p.weeks), k = (p.iso3 || p.cc) + "|" + (all ? catOf(p) : "");
      var r = rows[k];
      if (!r) { r = rows[k] = { cc: p.cc, cat: catOf(p), wild: 0, dom: 0, all: 0 }; keys.push(k); }
      if (p.pop === "wild") r.wild += n; else if (p.pop === "domestic") r.dom += n; else split += n;
      r.all += n;
    });
    var data = keys.map(function (k) { return rows[k]; }).sort(function (a, b) {
      return b.all - a.all || a.cc.localeCompare(b.cc, "en-GB");
    });
    var cols = [["Country", "text"]];
    if (all) cols.push(["Disease", "text"]);
    cols.push(["Wild", "num"], ["Domestic", "num"], ["Total", "num"]);
    var head = el("tr");
    cols.forEach(function (c, i) {
      var th = el("th", c[1] === "num" ? "num" : null), b = el("button", null, c[0]);
      th.scope = "col";
      th.setAttribute("data-col", String(i));
      th.setAttribute("data-sort", c[1]);
      th.setAttribute("aria-sort", c[0] === "Total" ? "descending" : "none");
      b.type = "button";
      th.appendChild(b);
      head.appendChild(th);
    });
    table.tHead.textContent = "";
    table.tHead.appendChild(head);
    var body = table.tBodies[0];
    body.textContent = "";
    data.forEach(function (r) {
      var tr = el("tr"), th = el("th", null, r.cc);
      th.scope = "row";
      tr.appendChild(th);
      if (all) tr.appendChild(el("td", null, cfg.cats[r.cat].short));
      [r.wild, r.dom, r.all].forEach(function (v) {
        var td = el("td", "num", fmt(v));
        td.setAttribute("data-v", String(v));
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    if (!data.length) {
      var tr = el("tr"), td = el("td", "dash", "No reports in these weeks.");
      td.colSpan = cols.length;
      tr.appendChild(td);
      body.appendChild(tr);
    }
    table.setAttribute("data-noun", all ? "rows" : "countries");
    table.setAttribute("data-open", "0");
    tTitle.textContent = all ? cap("reports by country, " + span())
      : cfg.cats[state.cat].short + ": reports by country, " + span();
    tNote.textContent = cfg.tableNote + (split ? " Total also includes " + fmt(split) +
      " that cover both wild and domestic animals, or do not say which." : "");
    if (window.OLTables) window.OLTables.setup(table);
  }

  // ---------- the map ----------
  function current() {
    var show = [];
    feats.forEach(function (f) {
      var p = f.properties;
      if (state.cat !== "all" && p.cat !== state.cat) return;
      if (total(p.weeks) > 0) show.push(f);
    });
    return show;
  }
  function lite(list) {   // the map only needs the place, the id and the symbol
    return { type: "FeatureCollection", features: list.map(function (f) {
      return { type: "Feature", geometry: f.geometry,
        properties: { id: f.properties.id, sym: shapeOf(f.properties) + "-" + catOf(f.properties) } };
    }) };
  }
  function webgl() {
    try {
      var c = document.createElement("canvas");
      return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
    } catch (e) { return false; }
  }
  function off(msg) {
    ready = false;
    mapEl.textContent = "";
    mapEl.appendChild(el("p", "map-off", msg ||
      "This map needs WebGL, which this browser does not offer. The table below and the open data hold the same records."));
    mapEl.style.height = "auto";
    mapEl.style.minHeight = "0";
  }
  function tidy(style) {   // credit line, English place names and quieter labels, so the data stands out
    if (style.sources && style.sources.openmaptiles) style.sources.openmaptiles.attribution = cfg.attribution;
    var name = ["coalesce", ["get", "name_en"], ["get", "name:latin"], ["get", "name"]];
    (style.layers || []).forEach(function (l) {
      var lo = l.layout;
      if (lo && lo["text-field"] && JSON.stringify(lo["text-field"]).indexOf("name:nonlatin") >= 0) lo["text-field"] = name;
      if (/^label_/.test(l.id) && l.paint) l.paint["text-color"] = /country/.test(l.id) ? "#4f545b" : "#676c73";
    });
    return style;
  }
  function plain() {
    return { version: 8, glyphs: cfg.glyphs, sources: {},
      layers: [{ id: "background", type: "background", paint: { "background-color": "#f2f3f0" } }] };
  }
  function icon(shape, colour) {   // drawn at twice the size, with a white ring and a faint dark edge
    var r = 2, S = 22, c = document.createElement("canvas"), g;
    c.width = c.height = S * r;
    g = c.getContext("2d");
    g.scale(r, r);
    g.lineJoin = "round";
    g.beginPath();
    if (shape === "circle") g.arc(11, 11, 6.5, 0, 2 * Math.PI);
    else if (shape === "triangle") { g.moveTo(11, 3.4); g.lineTo(19.75, 18.6); g.lineTo(2.25, 18.6); g.closePath(); }
    else g.rect(5.3, 5.3, 11.4, 11.4);
    g.lineWidth = 3.8; g.strokeStyle = "rgba(28,27,25,.38)"; g.stroke();
    g.lineWidth = 2.4; g.strokeStyle = "#fff"; g.stroke();
    g.fillStyle = colour; g.fill();
    return g.getImageData(0, 0, S * r, S * r);
  }
  function layers() {
    Object.keys(cfg.cats).forEach(function (k) {
      ["circle", "triangle", "square"].forEach(function (sh) {
        if (!map.hasImage(sh + "-" + k)) map.addImage(sh + "-" + k, icon(sh, cfg.cats[k].colour), { pixelRatio: 2 });
      });
    });
    map.addSource("reports", { type: "geojson", data: lite(current()), cluster: true,
      clusterRadius: 36, clusterMaxZoom: cfg.maxZoom });
    map.addLayer({ id: "clusters", type: "circle", source: "reports", filter: ["has", "point_count"],
      paint: { "circle-color": "#1F3864", "circle-stroke-width": 3, "circle-stroke-color": "rgba(250,247,241,0.92)",
        "circle-radius": ["step", ["get", "point_count"], 14, 10, 17, 50, 20, 200, 23] } });
    map.addLayer({ id: "cluster-count", type: "symbol", source: "reports", filter: ["has", "point_count"],
      layout: { "text-field": ["get", "point_count_abbreviated"], "text-font": ["Noto Sans Bold"], "text-size": 12,
        "text-allow-overlap": true, "text-ignore-placement": true },
      paint: { "text-color": "#ffffff" } });
    map.addLayer({ id: "points", type: "symbol", source: "reports", filter: ["!", ["has", "point_count"]],
      layout: { "icon-image": ["get", "sym"], "icon-allow-overlap": true, "icon-ignore-placement": true } });
    map.on("click", "clusters", function (e) {
      var f = e.features[0], src = map.getSource("reports"), id = f.properties.cluster_id, at = f.geometry.coordinates;
      src.getClusterExpansionZoom(id).then(function (z) {
        if (z <= map.getMaxZoom()) { map.easeTo({ center: at, zoom: z }); return null; }
        return src.getClusterLeaves(id, 200, 0).then(function (leaves) {   // same place: list them instead
          openPopup(at, leaves.map(function (l) { return byId[l.properties.id]; }).filter(Boolean));
        });
      }).catch(function () {});
    });
    map.on("click", "points", function (e) {
      var seen = {}, list = [];
      e.features.forEach(function (x) {
        var f = byId[x.properties.id];
        if (f && !seen[f.properties.id]) { seen[f.properties.id] = 1; list.push(f); }
      });
      if (list.length) openPopup(list[0].geometry.coordinates, list);
    });
    ["clusters", "points"].forEach(function (id) {
      map.on("mouseenter", id, function () { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, function () { map.getCanvas().style.cursor = ""; });
    });
    ready = true;
  }
  function start(style) {
    var small = window.matchMedia("(max-width: 639px)").matches;
    try {
      map = new maplibregl.Map({ container: mapEl, style: style, center: small ? [12, 46] : [14, 47], zoom: small ? 0.9 : 2,
        minZoom: 0.6, maxZoom: cfg.maxZoom, cooperativeGestures: true, dragRotate: false, pitchWithRotate: false,
        touchPitch: false, maxPitch: 0 });
    } catch (e) { off(); return; }
    mapEl.outbreakLensMap = map;   // handy for testing and for embedding scripts
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", layers);
  }

  function render() {
    var list = current();
    if (ready) map.getSource("reports").setData(lite(list));
    if (popup) popup.remove();
    var what = state.cat === "all" ? "any of the eight diseases" : cfg.cats[state.cat].phrase;
    summary.textContent = (list.length
      ? fmt(list.length) + (list.length === 1 ? " place" : " places") + " with reports of " + what + " in these weeks."
      : "No reports of " + what + " in these weeks.") + mapNote;
    renderTable(list);
  }
  function sync() {
    fromSel.value = String(state.from);
    toSel.value = String(state.to);
    slider.value = String(state.to);
    out.textContent = cap(span());
    slider.setAttribute("aria-valuetext", cap(span()));
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

  if (!window.maplibregl || !webgl()) {
    off();
  } else {
    fetch(cfg.style).then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(function (st) { start(tidy(st)); })
      .catch(function () {
        mapNote = " The basemap did not load, so the points sit on a plain background.";
        start(plain());
      });
  }
  fetch(cfg.data, { credentials: "same-origin" })
    .then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
    .then(function (gj) {
      feats = gj.features;
      feats.forEach(function (f) { byId[f.properties.id] = f; });
      sync();
      render();
    })
    .catch(function () { summary.textContent = "The map data did not load. The same records are in the open data."; });
})();
