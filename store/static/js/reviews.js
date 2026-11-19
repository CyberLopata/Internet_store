/* Фото у відгуках: перегляд збільшеним і попередній перегляд вибраних файлів у формі. */
(function () {
  document.querySelectorAll("[data-rv-photos]").forEach(function (box) {
    var btns = Array.prototype.slice.call(box.querySelectorAll(".rv-ph"));
    var urls = btns.map(function (b) { return b.dataset.src; });
    btns.forEach(function (b, i) {
      b.addEventListener("click", function () {
        if (window.openLightbox) window.openLightbox(urls, i, "Фото з відгуку");
      });
    });
  });

  var input = document.querySelector(".rv-form input[type=file]");
  var prev = document.querySelector("[data-rv-previews]");
  if (!input || !prev) return;
  var MAX = 4, note = document.createElement("div");
  note.className = "err"; note.hidden = true; prev.parentNode.insertBefore(note, prev.nextSibling);
  var urls = [];
  input.addEventListener("change", function () {
    urls.forEach(function (u) { URL.revokeObjectURL(u); }); urls = [];
    prev.textContent = ""; note.hidden = true;
    var files = Array.prototype.slice.call(input.files || []);
    if (files.length > MAX) {
      input.value = "";
      note.textContent = "Можна додати не більше " + MAX + " фото."; note.hidden = false;
      return;
    }
    files.forEach(function (f) {
      if (!/^image\//.test(f.type)) return;
      var u = URL.createObjectURL(f); urls.push(u);
      var im = document.createElement("img"); im.src = u; im.alt = ""; prev.appendChild(im);
    });
  });
})();
