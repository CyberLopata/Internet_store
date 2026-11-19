/* Вибір міста й відділення Нової пошти на сторінці оформлення.
   Прогресивне покращення: без ключа/JS/при помилці API лишаються звичайні поля. */
(function () {
  var form = document.getElementById('checkout-form');
  if (!form) return;
  var city = form.querySelector('#id_city'), addr = form.querySelector('#id_address');
  if (!city || !addr) return;
  var urlC = form.dataset.npCities, urlW = form.dataset.npWarehouses;
  var cityRef = '', pickedCity = '', pickedAddr = '', manual = false, broken = false;
  var cityField = city.closest('.field'), addrField = addr.closest('.field');

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; }

  var msg = el('div', 'err np-msg'); msg.hidden = true; addrField.appendChild(msg);

  function Picker(input, fetcher, onPick, label) {
    var box = el('div', 'np-list'); box.setAttribute('role', 'listbox'); box.hidden = true;
    input.parentNode.style.position = 'relative'; input.parentNode.appendChild(box);
    input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false'); input.setAttribute('autocomplete', 'off');
    var items = [], active = -1, timer = null, seq = 0;
    function close() { box.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; }
    function mark(i) {
      active = i;
      Array.prototype.forEach.call(box.children, function (c, k) { c.classList.toggle('on', k === i); c.setAttribute('aria-selected', k === i ? 'true' : 'false'); });
    }
    function render(list, emptyText) {
      items = list; box.textContent = '';
      if (!list.length) { box.appendChild(el('div', 'np-empty', emptyText)); }
      list.forEach(function (it, i) {
        var o = el('div', 'np-opt', label(it)); o.setAttribute('role', 'option');
        o.addEventListener('mousedown', function (e) { e.preventDefault(); choose(i); });
        box.appendChild(o);
      });
      box.hidden = false; input.setAttribute('aria-expanded', 'true'); active = -1;
    }
    function choose(i) { var it = items[i]; if (!it) return; close(); onPick(it); }
    function run() {
      var my = ++seq;
      fetcher(input.value.trim(), function (err, list) {
        if (my !== seq) return;
        if (err) { fail(); return; }
        render(list, 'Нічого не знайдено');
      });
    }
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 250); });
    input.addEventListener('focus', function () { if (!input.readOnly && !manual) run(); });
    input.addEventListener('blur', function () { setTimeout(close, 120); });
    input.addEventListener('keydown', function (e) {
      if (box.hidden || !items.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); mark((active + 1) % items.length); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); mark((active - 1 + items.length) % items.length); }
      else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(active); }
      else if (e.key === 'Escape') close();
    });
    return { close: close };
  }

  function get(url, cb) {
    var x = new XMLHttpRequest(); x.open('GET', url);
    x.onload = function () {
      if (x.status !== 200) return cb(true);
      try { cb(null, JSON.parse(x.responseText).results || []); } catch (e) { cb(true); }
    };
    x.onerror = function () { cb(true); };
    x.send();
  }

  function setManual(on, reason) {
    manual = on; city.readOnly = false; addr.readOnly = false; addr.disabled = false;
    if (on) {
      city.placeholder = 'Місто'; addr.placeholder = 'Відділення Нової пошти або адреса';
      msg.hidden = !reason; if (reason) msg.textContent = reason;
    } else {
      city.placeholder = 'Почніть вводити місто';
      addr.placeholder = cityRef || addr.value ? 'Оберіть відділення зі списку' : 'Спочатку оберіть місто';
      addr.disabled = !cityRef && !addr.value; msg.hidden = true;
    }
  }
  function fail() { broken = true; setManual(true, 'Список Нової пошти зараз недоступний — введіть місто (з областю) та адресу вручну.'); }

  var cityPicker = Picker(city, function (q, cb2) {
    if (q.length < 2) return cb2(null, []);
    get(urlC + '?q=' + encodeURIComponent(q), cb2);
  }, function (c) {
    cityRef = c.ref; pickedCity = c.present; city.value = c.present;  /* з областю: «м. Первомайськ, Миколаївська обл.» */
    addr.disabled = false; addr.value = ''; pickedAddr = ''; addr.placeholder = 'Оберіть відділення зі списку';
    addr.focus();
  }, function (c) { return c.present; });

  Picker(addr, function (q, cb2) {
    if (!cityRef) return cb2(null, []);
    get(urlW + '?city=' + encodeURIComponent(cityRef) + '&q=' + encodeURIComponent(q), cb2);
  }, function (w) { pickedAddr = w.name; addr.value = w.name; msg.hidden = true; }, function (w) { return w.name; });

  city.addEventListener('input', function () { if (manual) return; cityRef = ''; pickedCity = ''; pickedAddr = ''; addr.value = ''; addr.disabled = true; addr.placeholder = 'Спочатку оберіть місто'; });
  addr.addEventListener('input', function () { if (!manual) pickedAddr = ''; });


  form.addEventListener('submit', function (e) {
    if (manual || broken) return;
    if (form.dataset.npOptional && !city.value && !addr.value) return;  /* у кабінеті поля необов'язкові */
    if (!city.value || !addr.value || !pickedAddr || addr.value !== pickedAddr || city.value !== pickedCity) {
      e.preventDefault(); msg.textContent = 'Оберіть місто та відділення зі списку.'; msg.hidden = false;
      (city.value && pickedCity === city.value ? addr : city).focus();
    }
  });

  // поля вже заповнені (профіль / помилка форми): лишаємо як є, доки покупець не змінить місто
  pickedCity = city.value; pickedAddr = addr.value; setManual(false);
})();
