(function () {
  "use strict";
  var cards = Array.prototype.slice.call(document.querySelectorAll(".chart-card"));
  Array.prototype.forEach.call(document.querySelectorAll('input[name="num-cat"]'), function (r) {
    r.addEventListener("change", function () {
      cards.forEach(function (c) { c.hidden = r.value !== "all" && c.getAttribute("data-cat") !== r.value; });
    });
  });
  cards.forEach(function (card) {
    var svg = card.querySelector("svg.chart");
    if (!svg) return;
    var hits = svg.querySelectorAll(".hit"), cur = -1;
    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.setAttribute("aria-hidden", "true");
    card.appendChild(tip);
    function bar(i) { return svg.querySelector('.bar[data-i="' + i + '"]'); }
    function show(i) {
      if (cur >= 0 && bar(cur)) bar(cur).classList.remove("on");
      cur = i;
      var h = hits[i], b = bar(i);
      if (!h) return;
      if (b) b.classList.add("on");
      tip.textContent = "";
      var s = document.createElement("strong");
      s.textContent = h.getAttribute("data-v");
      tip.appendChild(s);
      tip.appendChild(document.createTextNode(h.getAttribute("data-l")));
      var cr = card.getBoundingClientRect(), hr = h.getBoundingClientRect(), sr = svg.getBoundingClientRect();
      var topY = (b ? b.getBoundingClientRect().top : sr.top + sr.height * 0.79) - cr.top;
      var x = hr.left + hr.width / 2 - cr.left;
      tip.style.left = Math.min(Math.max(x, 90), cr.width - 90) + "px";
      tip.style.top = Math.max(topY, sr.top - cr.top + 24) + "px";
      tip.classList.add("show");
    }
    function hide() {
      tip.classList.remove("show");
      if (cur >= 0 && bar(cur)) bar(cur).classList.remove("on");
      cur = -1;
    }
    Array.prototype.forEach.call(hits, function (h, i) {
      h.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse") show(i); });
      h.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") hide(); });
      h.addEventListener("click", function () { if (cur === i) hide(); else show(i); });
    });
    svg.addEventListener("focus", function () { show(hits.length - 1); });
    svg.addEventListener("blur", hide);
    svg.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        var i = cur < 0 ? hits.length - 1 : cur + (e.key === "ArrowRight" ? 1 : -1);
        show(Math.max(0, Math.min(hits.length - 1, i)));
      } else if (e.key === "Escape") {
        hide();
      }
    });
  });
})();
