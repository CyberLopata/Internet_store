/* Чат з продавцем: віджет покупця і сторінка продавця (опитування кожні кілька секунд). */
(function () {
  function Chat(root, side, urls, hooks) {
    var list = root.querySelector(".cm-list"), form = root.querySelector(".cm-form");
    var ta = form.querySelector("textarea"), err = root.querySelector(".cm-err");
    var last = 0, seen = {}, busy = false, product = null, timer = null, interval = 0;
    hooks = hooks || {};

    function el(tag, cls, text) {
      var n = document.createElement(tag);
      if (cls) n.className = cls;
      if (text != null) n.textContent = text;  // лише textContent: текст клієнта не стає HTML
      return n;
    }
    function nearBottom() { return list.scrollHeight - list.scrollTop - list.clientHeight < 80; }
    function add(m, force) {
      if (seen[m.id]) return;
      seen[m.id] = 1; if (m.id > last) last = m.id;
      var stick = force || nearBottom();
      var empty = list.querySelector(".cm-empty"); if (empty) empty.remove();
      var d = el("div", "cm " + (m.seller === (side === "seller") ? "mine" : "theirs"));
      if (m.product) {
        var a = el("a", "cm-prod", "🛍 " + m.product.name); a.href = m.product.url; d.appendChild(a);
      }
      d.appendChild(el("p", "cm-text", m.text));
      d.appendChild(el("span", "cm-time", m.time));
      list.appendChild(d);
      if (stick) list.scrollTop = list.scrollHeight;
    }
    function showErr(t) { err.textContent = t || ""; err.hidden = !t; }

    function poll(open) {
      if (document.hidden && !open) return Promise.resolve();
      var q = urls.messages + "?after=" + last + (open ? "&open=1" : "");
      return fetch(q, { headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data) return;
          data.messages.forEach(function (m) { add(m, false); });
          if (hooks.unread) hooks.unread(data.unread);
        }).catch(function () {});
    }
    function schedule(ms) {
      clearInterval(timer); interval = ms;
      if (ms) timer = setInterval(function () { poll(hooks.isOpen ? hooks.isOpen() : true); }, ms);
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = ta.value.trim();
      if (!text || busy) return;
      busy = true; showErr("");
      var fd = new FormData(form);
      if (product) fd.set("product", product.id);
      fetch(urls.send, { method: "POST", body: fd, credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (!res.ok) { showErr(res.j.error || "Не вдалося надіслати. Спробуйте ще раз."); return; }
          add(res.j.message, true); ta.value = ""; grow(); setProduct(null);
        })
        .catch(function () { showErr("Немає зв'язку. Спробуйте ще раз."); })
        .then(function () { busy = false; ta.focus(); });
    });
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
    });
    function grow() { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; }
    ta.addEventListener("input", grow);

    function setProduct(p) { product = p; if (hooks.product) hooks.product(p); }
    return { poll: poll, schedule: schedule, setProduct: setProduct, focus: function () { ta.focus(); },
             draft: function (t) { if (!ta.value) { ta.value = t; grow(); } }, scroll: function () { list.scrollTop = list.scrollHeight; } };
  }

  /* Сторінка продавця */
  var page = document.querySelector(".chatpage");
  if (page) {
    var c = Chat(page, "seller", { messages: page.dataset.messagesUrl, send: page.dataset.sendUrl });
    c.poll(true).then(c.scroll); c.schedule(4000);
  }

  /* Віджет покупця */
  var w = document.getElementById("chat-widget");
  if (!w) return;
  var panel = w.querySelector("[data-chat-panel]"), fab = w.querySelector("[data-chat-toggle]");
  var badge = w.querySelector("[data-chat-badge]"), attach = w.querySelector("[data-chat-attach]");
  var open = false;
  var chat = Chat(w, "customer", { messages: w.dataset.messagesUrl, send: w.dataset.sendUrl }, {
    isOpen: function () { return open; },
    unread: function (n) { badge.textContent = n; badge.hidden = !n || open; },
    product: function (p) {
      attach.hidden = !p; w.querySelector("[data-chat-attach-name]").textContent = p ? p.name : "";
    }
  });
  function setOpen(v) {
    open = v; panel.hidden = !v; fab.setAttribute("aria-expanded", v ? "true" : "false");
    fab.hidden = false; w.classList.toggle("is-open", v);
    if (v) { badge.hidden = true; chat.poll(true).then(chat.scroll); chat.schedule(4000); chat.focus(); }
    else { chat.schedule(30000); }
  }
  fab.addEventListener("click", function () { setOpen(!open); });
  w.querySelector("[data-chat-close]").addEventListener("click", function () { setOpen(false); fab.focus(); });
  w.querySelector("[data-chat-attach-clear]").addEventListener("click", function () { chat.setProduct(null); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && open) setOpen(false); });
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-chat-open]");
    if (!b) return;
    e.preventDefault();
    if (b.dataset.productId) {
      chat.setProduct({ id: b.dataset.productId, name: b.dataset.productName });
      chat.draft("Доброго дня! Цікавить «" + b.dataset.productName + "». ");
    }
    setOpen(true);
  });
  chat.poll(false); chat.schedule(30000);  // значок непрочитаних
})();
