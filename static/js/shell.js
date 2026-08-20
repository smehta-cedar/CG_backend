/*
 * shell.js — sidebar collapse, mobile drawer, and the user dropdown.
 *
 * The shell is laid out entirely in base.html. Nothing here positions anything:
 * every function below flips a class that the template already accounts for, so
 * with JS disabled the page is still correct (see the <noscript> block in head).
 *
 * Vanilla only — no framework, no build step.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "cg:sidebar";
  var DESKTOP = window.matchMedia("(min-width: 1024px)");

  var root = document.documentElement;
  var body = document.body;
  var sidebar = document.querySelector("[data-sidebar-el]");
  var sidebarHead = document.querySelector("[data-sidebar-head]");
  var backdrop = document.querySelector("[data-drawer-backdrop]");
  var drawerToggle = document.querySelector("[data-drawer-toggle]");
  var collapseToggle = document.querySelector("[data-sidebar-toggle]");

  /* ------------------------------------------------------------------ icons */

  /*
   * lucide swaps each <i data-lucide> for an <svg>, so any markup injected after
   * the first pass renders as an empty tag until this runs again. Call it after
   * every DOM change that adds an icon.
   */
  function renderIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  /* ---------------------------------------------------------------- storage */

  function readStored() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (err) {
      return null; // private mode / storage disabled — fall back to expanded
    }
  }

  function writeStored(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (err) {
      /* nothing to do; the toggle still works for this page view */
    }
  }

  /* --------------------------------------------------- sidebar collapse (lg) */

  /*
   * Collapse is a width change and nothing more. The lg: prefixes keep it off
   * the mobile drawer entirely — below lg the sidebar is always full width.
   */
  function setCollapsed(collapsed) {
    if (!sidebar) return;

    sidebar.classList.toggle("lg:w-20", collapsed);

    Array.prototype.forEach.call(
      document.querySelectorAll("[data-sidebar-el] [data-nav-label]"),
      function (label) {
        label.classList.toggle("lg:hidden", collapsed);
      }
    );

    Array.prototype.forEach.call(
      document.querySelectorAll("[data-sidebar-el] [data-nav], [data-sidebar-el] [data-sidebar-row]"),
      function (row) {
        row.classList.toggle("lg:justify-center", collapsed);
        row.classList.toggle("lg:px-0", collapsed);
      }
    );

    if (sidebarHead) {
      sidebarHead.classList.toggle("lg:justify-center", collapsed);
      sidebarHead.classList.toggle("lg:px-0", collapsed);
    }

    if (collapseToggle) {
      collapseToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      collapseToggle.setAttribute(
        "aria-label",
        collapsed ? "Expand sidebar" : "Collapse sidebar"
      );
      // Both chevrons are pre-rendered in the template, so this swap needs no
      // renderIcons() pass and cannot flicker.
      var expanded = collapseToggle.querySelector("[data-icon-expanded]");
      var collapsedIcon = collapseToggle.querySelector("[data-icon-collapsed]");
      if (expanded) expanded.classList.toggle("hidden", collapsed);
      if (collapsedIcon) collapsedIcon.classList.toggle("hidden", !collapsed);
    }

    body.setAttribute("data-sidebar", collapsed ? "collapsed" : "expanded");
  }

  /* ------------------------------------------------------ mobile drawer (<lg) */

  function drawerOpen() {
    return !!sidebar && !sidebar.classList.contains("-translate-x-full");
  }

  function setDrawer(open) {
    if (!sidebar) return;

    // lg:translate-x-0 in the template keeps the desktop sidebar put regardless.
    sidebar.classList.toggle("-translate-x-full", !open);
    if (backdrop) backdrop.classList.toggle("hidden", !open);
    if (drawerToggle) drawerToggle.setAttribute("aria-expanded", open ? "true" : "false");

    // Stop the page behind the drawer from scrolling with it.
    root.classList.toggle("overflow-hidden", open);
    body.classList.toggle("overflow-hidden", open);
  }

  /* -------------------------------------------------------------- dropdowns */

  function closeDropdowns(except) {
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-dropdown]"),
      function (panel) {
        if (panel === except) return;
        panel.classList.add("hidden");
        var owner = document.querySelector(
          '[data-dropdown-trigger="' + panel.getAttribute("data-dropdown") + '"]'
        );
        if (owner) owner.setAttribute("aria-expanded", "false");
      }
    );
  }

  function toggleDropdown(name) {
    var panel = document.querySelector('[data-dropdown="' + name + '"]');
    var trigger = document.querySelector('[data-dropdown-trigger="' + name + '"]');
    if (!panel) return;

    var willOpen = panel.classList.contains("hidden");
    closeDropdowns(panel); // one open at a time
    panel.classList.toggle("hidden", !willOpen);
    if (trigger) trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
  }

  /* ------------------------------------------------------------------ wiring */

  if (collapseToggle) {
    collapseToggle.addEventListener("click", function () {
      var next = body.getAttribute("data-sidebar") !== "collapsed";
      setCollapsed(next);
      writeStored(next ? "collapsed" : "expanded");
    });
  }

  if (drawerToggle) {
    drawerToggle.addEventListener("click", function (event) {
      event.stopPropagation();
      setDrawer(!drawerOpen());
    });
  }

  if (backdrop) {
    backdrop.addEventListener("click", function () {
      setDrawer(false);
    });
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || typeof target.closest !== "function") return;

    var trigger = target.closest("[data-dropdown-trigger]");
    if (trigger) {
      event.preventDefault();
      event.stopPropagation();
      toggleDropdown(trigger.getAttribute("data-dropdown-trigger"));
      return;
    }
    // A click that lands outside any open panel closes it.
    if (!target.closest("[data-dropdown]")) closeDropdowns();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape" && event.key !== "Esc") return;
    closeDropdowns();
    if (drawerOpen() && !DESKTOP.matches) {
      setDrawer(false);
      if (drawerToggle) drawerToggle.focus();
    }
  });

  // Growing past lg puts the sidebar back in flow, so drop any drawer state.
  function syncToViewport() {
    if (DESKTOP.matches && drawerOpen()) setDrawer(false);
  }
  if (typeof DESKTOP.addEventListener === "function") {
    DESKTOP.addEventListener("change", syncToViewport);
  } else if (typeof DESKTOP.addListener === "function") {
    DESKTOP.addListener(syncToViewport); // Safari < 14
  }

  /* -------------------------------------------------------------------- init */

  setCollapsed(readStored() === "collapsed");
  setDrawer(false);
  renderIcons();
})();
