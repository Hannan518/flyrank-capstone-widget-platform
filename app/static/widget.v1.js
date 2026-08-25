(function () {
  "use strict";

  var script =
    document.currentScript ||
    (function () {
      var all = document.getElementsByTagName("script");
      return all[all.length - 1];
    })();

  var query = (script.src.split("?")[1] || "");
  var widgetId = new URLSearchParams(query).get("id");
  if (!widgetId) return;

  var root = script.src.replace(/\/widget(\.v[0-9]+)?\.js.*$/, "");
  var configUrl = root + "/api/v1/public/widgets/" + encodeURIComponent(widgetId) + "/config";
  var submitUrl = root + "/api/v1/public/submissions";

  fetch(configUrl)
    .then(function (res) {
      if (!res.ok) throw new Error("config " + res.status);
      return res.json();
    })
    .then(render)
    .catch(function () {
      /* fail silent: a broken embed must never break the host page */
    });

  function fallbackUuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function freshKey() {
    return typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : fallbackUuid();
  }

  function render(cfg) {
    var host = document.createElement("div");
    host.setAttribute("data-flyrank-widget", widgetId);
    host.style.cssText =
      "max-width:420px;font-family:system-ui,sans-serif;border:1px solid #ddd;" +
      "border-radius:8px;padding:16px;margin:8px 0;";

    var heading = document.createElement("div");
    heading.textContent = cfg.title || "";
    heading.style.cssText = "font-size:18px;font-weight:600;margin-bottom:4px;";
    host.appendChild(heading);

    if (cfg.description) {
      var desc = document.createElement("div");
      desc.textContent = cfg.description;
      desc.style.cssText = "font-size:14px;color:#555;margin-bottom:8px;";
      host.appendChild(desc);
    }

    var form = document.createElement("form");
    form.noValidate = false;

    (cfg.fields || []).forEach(function (field) {
      var wrap = document.createElement("div");
      wrap.style.cssText = "margin-bottom:10px;";

      var label = document.createElement("label");
      label.textContent = field.label;
      label.style.cssText = "display:block;font-size:13px;margin-bottom:2px;";

      var input =
        field.type === "textarea"
          ? document.createElement("textarea")
          : document.createElement("input");
      input.name = field.name;
      input.required = !!field.required;
      if (field.type === "email") input.type = "email";
      input.style.cssText =
        "width:100%;box-sizing:border-box;padding:6px 8px;font-size:14px;";

      wrap.appendChild(label);
      wrap.appendChild(input);
      form.appendChild(wrap);
    });

    var honeypotWrap = document.createElement("div");
    honeypotWrap.style.cssText = "display:none;position:absolute;left:-9999px;";
    honeypotWrap.setAttribute("aria-hidden", "true");
    var honeypotLabel = document.createElement("label");
    honeypotLabel.textContent = "Website";
    var honeypot = document.createElement("input");
    honeypot.name = "website";
    honeypot.tabIndex = -1;
    honeypot.autocomplete = "off";
    honeypotWrap.appendChild(honeypotLabel);
    honeypotWrap.appendChild(honeypot);
    form.appendChild(honeypotWrap);

    var keyField = document.createElement("input");
    keyField.type = "hidden";
    keyField.name = "idempotency_key";
    keyField.value = freshKey();
    form.appendChild(keyField);

    var button = document.createElement("button");
    button.type = "submit";
    button.textContent = cfg.button_text || "Submit";
    button.style.cssText =
      "background:#2563eb;color:#fff;border:0;border-radius:6px;" +
      "padding:8px 16px;font-size:14px;cursor:pointer;";
    form.appendChild(button);

    var message = document.createElement("div");
    message.style.cssText = "font-size:13px;margin-top:8px;display:none;";

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      send(0);
    });

    host.appendChild(form);
    host.appendChild(message);
    script.parentNode.insertBefore(host, script);

    function setMsg(text, color) {
      message.textContent = text;
      message.style.color = color || "";
      message.style.display = text ? "block" : "none";
    }

    function collectFields() {
      var fields = {};
      Array.prototype.forEach.call(form.elements, function (el) {
        if (
          el.name &&
          el.name !== "website" &&
          el.name !== "idempotency_key" &&
          typeof el.value === "string"
        ) {
          fields[el.name] = el.value;
        }
      });
      return fields;
    }

    function body() {
      return JSON.stringify({
        widget_id: widgetId,
        fields: collectFields(),
        website: honeypot.value,
        idempotency_key: keyField.value,
      });
    }

    function finishSuccess() {
      setMsg("Thanks! Your submission was received.", "#16a34a");
      keyField.value = freshKey();
      form.reset();
      button.disabled = false;
    }

    function finishError(text) {
      setMsg(text, "#dc2626");
      button.disabled = false;
    }

    function send(attempt) {
      button.disabled = true;
      setMsg("");
      fetch(submitUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body(),
      })
        .then(function (res) {
          return res
            .json()
            .catch(function () {
              return {};
            })
            .then(function (data) {
              return { status: res.status, ok: res.ok, data: data };
            });
        })
        .then(function (result) {
          if (result.status === 201 || result.status === 200 || result.status === 202) {
            /* 202 is the spam path — reply stays indistinguishable from success */
            finishSuccess();
            return;
          }
          if (result.status >= 500 && attempt < 2) {
            setTimeout(function () { send(attempt + 1); }, 500 * (attempt + 1));
            return;
          }
          finishError("Something went wrong. Please try again.");
        })
        .catch(function () {
          /* network failure: same idempotency_key goes out on retry */
          if (attempt < 2) {
            setTimeout(function () { send(attempt + 1); }, 500 * (attempt + 1));
            return;
          }
          finishError("Network error. Please try again.");
        });
    }
  }
})();
