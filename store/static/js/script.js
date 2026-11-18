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

/* Галерея фото на сторінці товару: мініатюри, стрілки, клавіші ←/→ і свайп.
   Набір фото можна підмінити через box.gallery.set([...]) — так фото змінюються при виборі кольору. */
(function () {
  var box = document.querySelector("[data-gallery]");
  if (!box) return;
  var main = box.querySelector("[data-gallery-main]");
  if (!main) return;
  var pimg = box.querySelector(".pimg"), strip = box.querySelector(".gthumbs"),
      emoji = box.querySelector("[data-gallery-emoji]"), navs = box.querySelectorAll("[data-gallery-step]");
  var urls = Array.prototype.map.call(box.querySelectorAll("[data-gallery-thumb]"), function (t) { return t.dataset.src; });
  if (!urls.length && !main.hidden && main.getAttribute("src")) urls = [main.getAttribute("src")];
  var cur = 0, startX = null;

  function thumbs() { return strip ? strip.querySelectorAll("[data-gallery-thumb]") : []; }
  function show(i) {
    if (!urls.length) return;
    cur = (i + urls.length) % urls.length;
    main.src = urls[cur];
    thumbs().forEach(function (t, j) {
      t.classList.toggle("on", j === cur);
      if (j === cur) t.scrollIntoView({ block: "nearest", inline: "nearest" });
    });
  }
  function render() {
    var many = urls.length > 1;
    if (strip) {
      strip.textContent = "";
      if (many) urls.forEach(function (u, j) {
        var b = document.createElement("button"), im = document.createElement("img");
        b.type = "button"; b.className = "gthumb"; b.dataset.galleryThumb = ""; b.dataset.src = u;
        b.setAttribute("aria-label", "Фото " + (j + 1));
        im.src = u; im.alt = ""; im.loading = "lazy"; b.appendChild(im); strip.appendChild(b);
      });
      strip.hidden = !many;
    }
    navs.forEach(function (n) { n.hidden = !many; });
    var any = urls.length > 0;
    main.hidden = !any;
    pimg.classList.toggle("has-img", any);
    pimg.style.background = any ? "" : (pimg.dataset.bg || "");
    if (emoji) emoji.hidden = any;
  }
  function set(list) {
    list = list.slice();
    if (list.join("|") === urls.join("|")) return;
    urls = list; render(); show(0);
    urls.forEach(function (u) { new Image().src = u; });  // підвантажуємо наперед, щоб зміна була миттєвою
  }

  if (strip) strip.addEventListener("click", function (e) {
    var t = e.target.closest("[data-gallery-thumb]");
    if (t) show(Array.prototype.indexOf.call(thumbs(), t));
  });
  navs.forEach(function (b) {
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
    if (urls.length > 1 && Math.abs(dx) > 40) show(cur + (dx < 0 ? 1 : -1));
  });
  box.gallery = { set: set, urls: function () { return urls.slice(); }, show: show };
})();

/* Збільшення фото товару: клік по фото відкриває повноекранний перегляд зі стрілками,
   клавішами ←/→/Esc і свайпом. Клік по фото в перегляді збільшує його вдвічі
   (далі фото рухається за курсором або пальцем), ще один клік повертає назад. */
(function () {
  var main = document.querySelector("[data-gallery-main]");
  if (!main) return;
  var gallery = main.closest("[data-gallery]"),
      lb, stage, img, count, closeBtn, prevBtn, nextBtn,
      urls = [], idx = 0, startIdx = 0, zoomed = false, baseRect = null,
      startX = null, startY = 0, handled = false, lastFocus = null;

  main.classList.add("zoomable");
  main.tabIndex = 0;
  main.setAttribute("role", "button");
  main.setAttribute("aria-label", "Збільшити фото");

  function build() {
    lb = document.createElement("div");
    lb.className = "lb";
    lb.hidden = true;
    lb.setAttribute("role", "dialog");
    lb.setAttribute("aria-modal", "true");
    lb.setAttribute("aria-label", "Перегляд фото");
    lb.innerHTML =
      '<div class="lb-stage"><img class="lb-img" alt="" draggable="false"></div>' +
      '<button type="button" class="lb-close" aria-label="Закрити">✕</button>' +
      '<button type="button" class="lb-nav prev" aria-label="Попереднє фото">‹</button>' +
      '<button type="button" class="lb-nav next" aria-label="Наступне фото">›</button>' +
      '<div class="lb-count" aria-live="polite"></div>';
    document.body.appendChild(lb);
    stage = lb.querySelector(".lb-stage");
    img = lb.querySelector(".lb-img");
    count = lb.querySelector(".lb-count");
    closeBtn = lb.querySelector(".lb-close");
    prevBtn = lb.querySelector(".lb-nav.prev");
    nextBtn = lb.querySelector(".lb-nav.next");

    lb.addEventListener("click", function (e) {
      if (e.target === closeBtn) close();
      else if (e.target === prevBtn) step(-1);
      else if (e.target === nextBtn) step(1);
      else if (handled) handled = false;        // дію вже виконано на pointerup (тап/свайп)
      else if (e.target === img) toggleZoom(e);
      else close();                             // клік по темному фону
    });
    img.addEventListener("load", fit);
    window.addEventListener("resize", function () { if (!lb.hidden) { resetZoom(); fit(); } });
    // Тап і свайп обробляємо на pointer-подіях: після свайпу деякі мобільні браузери не надсилають click.
    lb.addEventListener("pointerdown", function (e) { startX = e.clientX; startY = e.clientY; handled = false; });
    stage.addEventListener("pointermove", function (e) { if (zoomed) setOrigin(e); });
    stage.addEventListener("pointerup", function (e) {
      if (startX === null) return;
      var dx = e.clientX - startX, dy = e.clientY - startY;
      startX = null;
      if (!zoomed && Math.abs(dx) > 50) { handled = true; step(dx < 0 ? 1 : -1); }
      else if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
        handled = true;
        if (e.target === img) toggleZoom(e); else close(); // тап по фото збільшує, по темному фону закриває
      }
    });
  }

  function fit() { // вписуємо фото в екран, дрібні трохи збільшуємо (до ×3), щоб воно було більшим, ніж на сторінці
    var w = img.naturalWidth, h = img.naturalHeight;
    if (!w || !h) return;
    var cs = getComputedStyle(stage),
        aw = stage.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight),
        ah = stage.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom),
        k = Math.min(3, aw / w, ah / h);
    img.style.width = Math.round(w * k) + "px";
    img.style.height = Math.round(h * k) + "px";
  }
  function setOrigin(e) {
    var x = Math.min(1, Math.max(0, (e.clientX - baseRect.left) / baseRect.width)) * 100,
        y = Math.min(1, Math.max(0, (e.clientY - baseRect.top) / baseRect.height)) * 100;
    img.style.transformOrigin = x + "% " + y + "%";
  }
  function resetZoom() {
    zoomed = false;
    img.classList.remove("zoomed");
    img.style.transformOrigin = "";
  }
  function toggleZoom(e) {
    if (zoomed) { resetZoom(); return; }
    baseRect = img.getBoundingClientRect();
    zoomed = true;
    setOrigin(e);
    img.classList.add("zoomed");
  }
  function show(i) {
    idx = (i + urls.length) % urls.length;
    resetZoom();
    img.src = urls[idx];
    img.alt = main.alt;
    count.textContent = urls.length > 1 ? (idx + 1) + " / " + urls.length : "";
    if (urls.length > 1) { // підвантажуємо сусідні фото наперед
      new Image().src = urls[(idx + 1) % urls.length];
      new Image().src = urls[(idx - 1 + urls.length) % urls.length];
    }
  }
  function step(d) {
    if (urls.length > 1) show(idx + d);
  }
  function open() {
    if (!lb) build();
    urls = gallery && gallery.gallery ? gallery.gallery.urls() : [];
    if (!urls.length) urls = [main.getAttribute("src")];
    startIdx = Math.max(0, urls.indexOf(main.getAttribute("src")));
    lastFocus = document.activeElement;
    prevBtn.hidden = nextBtn.hidden = urls.length < 2;
    lb.hidden = false;
    document.body.style.overflow = "hidden";
    show(startIdx);
    closeBtn.focus();
  }
  function close() {
    if (!lb || lb.hidden) return;
    lb.hidden = true;
    resetZoom();
    document.body.style.overflow = "";
    if (idx !== startIdx && gallery && gallery.gallery) gallery.gallery.show(idx); // галерея на сторінці показує те саме фото
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  }

  main.addEventListener("click", open);
  main.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
  });
  document.addEventListener("keydown", function (e) {
    if (!lb || lb.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") step(-1);
    else if (e.key === "ArrowRight") step(1);
    else if (e.key === "Tab") { // фокус не виходить за межі перегляду
      var f = Array.prototype.filter.call(lb.querySelectorAll("button"), function (b) { return !b.hidden; });
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
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
