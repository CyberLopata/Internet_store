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

/* Перемикач світлої/темної теми. Без збереженого вибору сайт іде за налаштуванням системи.
   Збережена тема виставляється ще в <head> (див. base.html), щоб не було миготіння. */
(function () {
  var btn = document.querySelector("[data-theme-toggle]");
  if (!btn) return;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null,
      root = document.documentElement;

  function current() {
    var t = root.getAttribute("data-theme");
    if (t === "dark" || t === "light") return t;
    return mq && mq.matches ? "dark" : "light";
  }
  function paint() {
    var dark = current() === "dark";
    btn.textContent = dark ? "☀️" : "🌙"; // показуємо тему, на яку перейдемо
    btn.setAttribute("aria-label", dark ? "Увімкнути світлу тему" : "Увімкнути темну тему");
    btn.title = btn.getAttribute("aria-label");
  }
  btn.hidden = false;
  paint();
  btn.addEventListener("click", function () {
    var next = current() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
    paint();
  });
  if (mq && mq.addEventListener) mq.addEventListener("change", paint);
})();

/* Галерея фото на сторінці товару: мініатюри, стрілки, клавіші ←/→ і свайп. */
(function () {
  var box = document.querySelector("[data-gallery]");
  if (!box) return;
  var main = box.querySelector("[data-gallery-main]"),
      thumbs = box.querySelectorAll("[data-gallery-thumb]");
  if (!main || thumbs.length < 2) return;
  var cur = 0, startX = null;

  function show(i) {
    cur = (i + thumbs.length) % thumbs.length;
    main.src = thumbs[cur].dataset.src;
    thumbs.forEach(function (t, j) {
      t.classList.toggle("on", j === cur);
      if (j === cur) t.scrollIntoView({ block: "nearest", inline: "nearest" });
    });
  }
  thumbs.forEach(function (t, j) {
    t.addEventListener("click", function () { show(j); });
  });
  box.querySelectorAll("[data-gallery-step]").forEach(function (b) {
    b.addEventListener("click", function () { show(cur + parseInt(b.dataset.galleryStep, 10)); });
  });
  box.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") show(cur - 1);
    else if (e.key === "ArrowRight") show(cur + 1);
  });
  main.addEventListener("touchstart", function (e) { startX = e.touches[0].clientX; }, { passive: true });
  main.addEventListener("touchend", function (e) {
    if (startX === null) return;
    var dx = e.changedTouches[0].clientX - startX;
    startX = null;
    if (Math.abs(dx) > 40) show(cur + (dx < 0 ? 1 : -1));
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
