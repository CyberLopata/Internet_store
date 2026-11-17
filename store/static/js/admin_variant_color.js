/* Адмінка: біля поля «Колір кружечка» додає віконце вибору кольору мишкою.
   Віконце нічого не надсилає саме: у поле потрапляє лише колір, який ви справді вибрали. */
(function () {
  function enhance(text) {
    if (text.dataset.picker || text.name.indexOf("__prefix__") !== -1) return;
    text.dataset.picker = "1";
    text.placeholder = "авто за назвою";
    text.style.width = "110px";
    var pick = document.createElement("input");
    pick.type = "color";
    pick.title = "Вибрати колір";
    pick.style.cssText = "margin-left:6px;width:38px;height:28px;padding:0;vertical-align:middle;cursor:pointer";
    pick.value = /^#[0-9a-f]{6}$/i.test(text.value) ? text.value : "#cccccc";
    pick.addEventListener("input", function () { text.value = pick.value; });
    text.addEventListener("input", function () {
      if (/^#[0-9a-f]{6}$/i.test(text.value)) pick.value = text.value;
    });
    text.insertAdjacentElement("afterend", pick);
  }
  function scan() { document.querySelectorAll('input[name$="-color_hex"]').forEach(enhance); }
  document.addEventListener("DOMContentLoaded", scan);
  document.addEventListener("formset:added", scan);  // рядок, доданий кнопкою «Додати ще один»
})();
