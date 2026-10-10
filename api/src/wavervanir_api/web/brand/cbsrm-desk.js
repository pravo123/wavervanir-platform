(function () {
  "use strict";
  function presentTables() {
    document.querySelectorAll("#terminal table").forEach(function (table) {
      if (table.parentElement.classList.contains("table-scroll")) return;
      var wrapper = document.createElement("div");
      wrapper.className = "table-scroll";
      wrapper.tabIndex = 0;
      table.before(wrapper);
      wrapper.appendChild(table);
    });
  }
  function mount() {
    presentTables();
    new MutationObserver(presentTables).observe(document.getElementById("terminal"), { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
}());
