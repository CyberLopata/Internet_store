/* Вибір розміру і кольору на сторінці товару. Без JS працює запасний <select> у <noscript>. */
(function () {
  var box = document.querySelector("[data-variants]"), src = document.getElementById("variants-data");
  if (!box || !src) return;
  var data = JSON.parse(src.textContent), form = box.closest("form");
  var input = form.querySelector("[data-variant-input]"), btn = form.querySelector("[data-add-btn]");
  var qty = form.querySelector('input[name="quantity"]'), status = box.querySelector("[data-vstatus]");
  var priceEl = document.querySelector(".pprice b"), basePrice = priceEl ? priceEl.textContent : "";
  var btnText = btn.textContent;
  var sel = { color: null, size: null };

  function uniq(key) {
    var seen = {}, out = [];
    data.forEach(function (v) { if (v[key] && !seen[v[key]]) { seen[v[key]] = 1; out.push(v); } });
    return out;
  }
  var axes = { color: uniq("color"), size: uniq("size") };
  var groups = {};
  ["color", "size"].forEach(function (k) {
    var g = box.querySelector('[data-vgroup="' + k + '"]');
    groups[k] = g;
    if (!axes[k].length) return;
    g.hidden = false;
    var holder = g.querySelector(".vopts");
    axes[k].forEach(function (v) {
      var b = document.createElement("button");
      b.type = "button"; b.dataset.value = v[k]; b.setAttribute("role", "radio");
      if (k === "color") {
        b.className = "vopt vcolor"; b.title = v.color; b.setAttribute("aria-label", v.color);
        var dot = document.createElement("span"); dot.className = "vdot";
        if (v.hex) dot.style.background = v.hex; else dot.textContent = v.color.charAt(0);
        b.appendChild(dot);
        if (!v.hex) { b.className = "vopt vchip"; b.textContent = v.color; }
      } else { b.className = "vopt vchip"; b.textContent = v.size; }
      b.addEventListener("click", function () {
        var other = k === "color" ? "size" : "color", val = v[k];
        // опції, якої немає в наявності в жодному поєднанні, обрати не можна
        if (!data.some(function (x) { return x[k] === val && x.stock > 0; })) return;
        sel[k] = sel[k] === val ? null : val;  // повторний клік знімає вибір
        // якщо з новим вибором поточна пара на іншій осі недоступна, скидаємо її, щоб покупець не застрягав
        if (sel[k] && sel[other]) {
          var t = {}; t[k] = sel[k]; t[other] = sel[other];
          if (!data.some(function (x) { return x.stock > 0 && matches(x, t); })) sel[other] = null;
        }
        refresh();
      });
      holder.appendChild(b);
    });
  });

  function matches(v, s) {
    return (!s.color || v.color === s.color) && (!s.size || v.size === s.size);
  }
  function complete() {
    return (!axes.color.length || sel.color) && (!axes.size.length || sel.size);
  }
  function fmt(n) { return Math.round(n).toLocaleString("uk-UA").replace(/\s/g, " ") + " ₴"; }

  function refresh() {
    // кнопка опції доступна, якщо з нею (і з вибраним на іншій осі) є щось у наявності
    ["color", "size"].forEach(function (k) {
      var other = k === "color" ? "size" : "color";
      groups[k].querySelectorAll(".vopt").forEach(function (b) {
        var test = {}; test[k] = b.dataset.value; test[other] = sel[other];
        var ok = data.some(function (v) { return v.stock > 0 && matches(v, test); });
        b.setAttribute("aria-disabled", ok ? "false" : "true");
        b.classList.toggle("off", !ok);
        var on = sel[k] === b.dataset.value;
        b.classList.toggle("on", on); b.setAttribute("aria-checked", on ? "true" : "false");
      });
      groups[k].querySelector("[data-vval]").textContent = sel[k] || "не обрано";
    });
    var cur = complete() ? data.filter(function (v) { return matches(v, sel); })[0] : null;
    var ready = !!cur && cur.stock > 0;
    input.value = ready ? cur.id : "";
    btn.disabled = !ready;
    if (ready) btn.textContent = btnText;
    else if (cur) btn.textContent = "Немає в наявності";
    else {
      var need = [];
      if (axes.size.length && !sel.size) need.push("розмір");
      if (axes.color.length && !sel.color) need.push("колір");
      btn.textContent = "Оберіть " + need.join(" і ");
    }
    if (priceEl) priceEl.textContent = cur ? fmt(cur.price) : basePrice;
    if (qty) { var max = ready ? Math.min(99, cur.stock) : 99; qty.max = max; if (+qty.value > max) qty.value = max; }
    status.className = "vstatus" + (cur ? (ready ? (cur.stock <= 5 ? " low" : " ok") : " out") : "");
    status.textContent = !cur ? "" : !ready ? "Цього варіанту немає в наявності"
      : cur.stock <= 5 ? "Залишилось лише " + cur.stock + " шт." : "В наявності";
  }

  // якщо опція одна — обираємо її одразу; якщо все розпродано — одразу про це кажемо
  ["color", "size"].forEach(function (k) { if (axes[k].length === 1) sel[k] = axes[k][0][k]; });
  btn.disabled = true;
  refresh();
  if (!data.some(function (v) { return v.stock > 0; })) { status.className = "vstatus out"; status.textContent = "Товару немає в наявності"; btn.textContent = "Немає в наявності"; }
})();
