// Stub viewer.js — boots against the data-api-base attribute on #live-paper-root
// and pings /api/ping + /api/bundle-info. M2 swaps this for the real SPA bundle.
(function () {
  "use strict";

  var root = document.getElementById("live-paper-root");
  if (!root) {
    console.error("[live-paper] root element missing");
    return;
  }
  var apiBase = root.getAttribute("data-api-base") || "/api/";
  if (apiBase.charAt(apiBase.length - 1) !== "/") {
    apiBase += "/";
  }

  function url(endpoint) {
    return apiBase + endpoint;
  }

  function setStatus(payload) {
    var pre = document.getElementById("live-paper-bundle-info");
    if (pre) {
      pre.textContent = JSON.stringify(payload, null, 2);
    }
  }

  fetch(url("ping"))
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data || data.ok !== true) {
        throw new Error("ping failed: " + JSON.stringify(data));
      }
      return fetch(url("bundle-info"));
    })
    .then(function (r) { return r.json(); })
    .then(setStatus)
    .catch(function (err) {
      console.error("[live-paper] boot failed", err);
      setStatus({ error: String(err) });
    });
})();
