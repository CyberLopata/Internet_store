/* Обране: перемикання сердечка без перезавантаження сторінки (без JS працює звичайна форма). */
(function () {
  if (!window.fetch) return;
  function paint(pid, active) {
    document.querySelectorAll('.fav-btn[data-fav="' + pid + '"]').forEach(function (b) {
      b.classList.toggle("on", active);
      b.setAttribute("aria-pressed", active ? "true" : "false");
      var label = active ? "Прибрати з обраного" : "Додати в обране";
      b.setAttribute("aria-label", label); b.title = label;
      var t = b.querySelector(".fav-text");
      if (t) t.textContent = active ? t.dataset.on : t.dataset.off;
    });
  }
  document.addEventListener("submit", function (e) {
    var form = e.target.closest ? e.target.closest("form.fav") : null;
    if (!form) return;
    e.preventDefault();
    var btn = form.querySelector(".fav-btn");
    if (btn.disabled) return;
    btn.disabled = true;
    fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin",
                         headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        paint(btn.dataset.fav, d.active);
        document.querySelectorAll("[data-fav-count]").forEach(function (b) { b.textContent = d.count; b.hidden = !d.count; });
        var page = document.querySelector("[data-fav-page]");
        if (page && !d.active) {  // на сторінці обраного прибраний товар зникає
          var card = form.closest(".card"); if (card) card.remove();
          if (!page.querySelector(".card")) location.reload();
        }
      })
      .catch(function () { form.submit(); })
      .then(function () { btn.disabled = false; });
  });
})();
