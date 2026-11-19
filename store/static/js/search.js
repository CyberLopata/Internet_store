/* Живий пошук: підказки під час набору. Без JS працює звичайна форма пошуку. */
(function () {
  var form = document.querySelector("form.search[data-suggest-url]");
  if (!form || !window.fetch) return;
  var input = form.querySelector("input[name=q]"), url = form.dataset.suggestUrl;
  var box = document.createElement("div"), cache = {}, timer = null, ctrl = null, active = -1, current = "";
  box.className = "sg"; box.id = "search-suggest"; box.setAttribute("role", "listbox"); box.hidden = true;
  box.setAttribute("aria-label", "Підказки пошуку");
  form.appendChild(box);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", box.id);
  input.setAttribute("aria-expanded", "false");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;  // лише textContent: назви товарів не стають HTML
    return n;
  }
  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  function highlight(node, text, q) {
    var ws = q.split(/\s+/).filter(Boolean);
    if (!ws.length) { node.textContent = text; return; }
    text.split(new RegExp("(" + ws.map(esc).join("|") + ")", "gi")).forEach(function (part, i) {
      if (!part) return;
      if (i % 2) node.appendChild(el("mark", null, part)); else node.appendChild(document.createTextNode(part));
    });
  }
  function options() { return box.querySelectorAll("[role=option]"); }
  function setActive(i) {
    var opts = options();
    if (!opts.length) { active = -1; input.removeAttribute("aria-activedescendant"); return; }
    active = (i + opts.length) % opts.length;
    opts.forEach(function (o, j) { o.setAttribute("aria-selected", j === active ? "true" : "false"); o.classList.toggle("on", j === active); });
    input.setAttribute("aria-activedescendant", opts[active].id);
    opts[active].scrollIntoView({ block: "nearest" });
  }
  function close() {
    box.hidden = true; active = -1;
    input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant");
  }
  function open() { box.hidden = false; input.setAttribute("aria-expanded", "true"); }

  function allLink(q, total) {
    var a = el("a", "sg-all", total ? "Показати всі результати (" + total + ") →" : "Відкрити пошук у каталозі →");
    a.href = form.action + "?q=" + encodeURIComponent(q);
    a.setAttribute("role", "option"); a.id = "sg-all"; a.setAttribute("aria-selected", "false");
    return a;
  }
  function render(data) {
    box.textContent = ""; active = -1; input.removeAttribute("aria-activedescendant");
    if (!data.results.length) {
      box.appendChild(el("div", "sg-empty", "Нічого не знайдено за «" + data.q + "». Спробуйте інше слово."));
      box.appendChild(allLink(data.q, 0));
      open(); return;
    }
    data.results.forEach(function (r, i) {
      var a = el("a", "sg-item"); a.href = r.url; a.id = "sg-" + i;
      a.setAttribute("role", "option"); a.setAttribute("aria-selected", "false");
      var th = el("span", "sg-th");
      if (r.image) { var im = document.createElement("img"); im.src = r.image; im.alt = ""; im.loading = "lazy"; th.appendChild(im); }
      else { th.textContent = r.emoji; th.style.background = r.color || ""; }
      var txt = el("span", "sg-txt"), name = el("span", "sg-name");
      highlight(name, r.name, data.q);
      txt.appendChild(name);
      txt.appendChild(el("span", "sg-meta", r.category + (r.in_stock ? "" : " · немає в наявності")));
      var pr = el("span", "sg-price"); pr.appendChild(el("b", null, r.price));
      if (r.old_price) pr.appendChild(el("s", null, r.old_price));
      a.appendChild(th); a.appendChild(txt); a.appendChild(pr);
      a.addEventListener("mousemove", function () { if (active !== i) setActive(i); });
      box.appendChild(a);
    });
    box.appendChild(allLink(data.q, data.total));
    open();
  }

  function load(q) {
    if (cache[q]) { render(cache[q]); return; }
    if (ctrl) ctrl.abort();
    ctrl = window.AbortController ? new AbortController() : null;
    fetch(url + "?q=" + encodeURIComponent(q), { credentials: "same-origin", signal: ctrl ? ctrl.signal : undefined,
                                                 headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        cache[q] = data;
        if (q === current) render(data);  // відповідь на застарілий запит ігноруємо
      })
      .catch(function () {});
  }
  input.addEventListener("input", function () {
    current = input.value.trim();
    clearTimeout(timer);
    if (current.length < 2) { if (ctrl) ctrl.abort(); close(); return; }
    timer = setTimeout(function () { load(current); }, 180);
  });
  input.addEventListener("focus", function () {
    if (box.childElementCount && input.value.trim() === current && current.length >= 2) open();
  });
  input.addEventListener("keydown", function (e) {
    if (box.hidden) { if (e.key === "ArrowDown" && box.childElementCount && input.value.trim().length >= 2) { open(); setActive(0); e.preventDefault(); } return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active < 0 ? -1 : active - 1); }
    else if (e.key === "Escape") { close(); }
    else if (e.key === "Enter" && active >= 0) { e.preventDefault(); location.href = options()[active].href; }
  });
  document.addEventListener("click", function (e) { if (!form.contains(e.target)) close(); });
  form.addEventListener("submit", function () { clearTimeout(timer); if (ctrl) ctrl.abort(); close(); });
})();
