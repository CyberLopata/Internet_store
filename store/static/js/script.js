/* Слайдер на головній сторінці */
(function () {
  var slides = document.querySelectorAll(".slide"),
      dots = document.getElementById("dots");
  if (!slides.length || !dots) return;
  var cur = 0;
  function go(i) {
    cur = i;
    slides.forEach(function (s, j) { s.classList.toggle("on", j === i); });
    Array.prototype.forEach.call(dots.children, function (d, j) { d.classList.toggle("on", j === i); });
  }
  slides.forEach(function (_, i) {
    var b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-label", "Слайд " + (i + 1));
    b.onclick = function () { go(i); };
    dots.appendChild(b);
  });
  go(0);
  setInterval(function () { go((cur + 1) % slides.length); }, 5000);
})();

/* Висувний кошик: відкривається при додаванні товару та по кліку на іконку в шапці.
   Без JS усі форми працюють як звичайні (редірект на попередню сторінку / у кошик). */
(function () {
  var drawer = document.getElementById("cart-drawer"),
      scrim = document.getElementById("cart-scrim");
  if (!drawer || !scrim || !window.fetch) return;
  var body = drawer.querySelector("[data-cart-body]"),
      closeBtn = drawer.querySelector(".dclose"),
      lastFocus = null;

  function setCount(n) {
    document.querySelectorAll("[data-cart-count]").forEach(function (b) {
      b.textContent = n;
      b.hidden = !n;
    });
  }
  function render(data) {
    body.innerHTML = data.html;
    setCount(data.count);
  }
  function request(url, options) {
    options = options || {};
    options.credentials = "same-origin";
    options.headers = { "X-Requested-With": "XMLHttpRequest" };
    return fetch(url, options).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function open() {
    if (drawer.classList.contains("open")) return;
    lastFocus = document.activeElement;
    drawer.classList.add("open");
    scrim.classList.add("on");
    drawer.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    closeBtn.focus();
  }
  function close() {
    if (!drawer.classList.contains("open")) return;
    drawer.classList.remove("open");
    scrim.classList.remove("on");
    drawer.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-cart-close]")) { close(); return; }
    var opener = e.target.closest("[data-cart-open]");
    if (!opener || e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
    if (location.pathname.indexOf("/cart/") === 0) return; // ми вже на сторінці кошика
    e.preventDefault();
    open();
    request(drawer.dataset.url).then(render).catch(function () { location.href = opener.href; });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });

  document.addEventListener("submit", function (e) {
    var form = e.target,
        isAdd = form.matches('form[action*="/cart/add/"]');
    if (!isAdd && !form.hasAttribute("data-cart-form")) return;
    e.preventDefault();
    var btn = e.submitter, fd = new FormData(form);
    if (btn && btn.name && !fd.has(btn.name)) fd.set(btn.name, btn.value); // старі браузери без submitter у FormData
    if (btn) btn.disabled = true;
    request(form.action, { method: "POST", body: fd })
      .then(function (data) { render(data); if (isAdd) open(); })
      .catch(function () { form.submit(); })
      .then(function () { if (btn) btn.disabled = false; });
  });
})();

/* Лічильник кількості на сторінці товару */
document.querySelectorAll(".stepper").forEach(function (box) {
  var input = box.querySelector("input");
  box.querySelectorAll("button[data-step]").forEach(function (b) {
    b.addEventListener("click", function () {
      var v = (parseInt(input.value, 10) || 1) + parseInt(b.dataset.step, 10);
      input.value = Math.min(parseInt(input.max, 10) || 99, Math.max(parseInt(input.min, 10) || 1, v));
    });
  });
});
