(() => {
  const ORIG = EventTarget.prototype.addEventListener;
  const HOVER = new Set(["mouseenter", "mouseover", "pointerenter"]);
  EventTarget.prototype.addEventListener = function (type, listener, opts) {
    if (HOVER.has(type)) {
      try {
        console.log("hover event", type);
        // only real elements (skip window / document)
        if (this && this.setAttribute) {
          console.log("setting attribute", this);
          this.setAttribute("data-maybe-hoverable", "true");
        }
      } catch (_) {
        /* ignore edge-cases */
      }
    }
    return ORIG.call(this, type, listener, opts);
  };

  const NETWORK_ORIG_XHR = window.XMLHttpRequest;
  const NETWORK_ORIG_FETCH = window.fetch;

  window.__networkActivity = {
    activeRequests: 0,
    lastActivity: Date.now(),
    eventTarget: new EventTarget(),
    _xhrPatched: false,
    _fetchPatched: false,
    debug: false,

    _log(...args) {
      if (this.debug) console.log(...args);
    },

    _emitEvent(type, data = {}) {
      this.eventTarget.dispatchEvent(new CustomEvent(type, { detail: data }));
    },

    _touch() {
      this.lastActivity = Date.now();
    },

    _changeActive(delta, source) {
      const next = Math.max(0, this.activeRequests + delta);
      this.activeRequests = next;
      this._touch();

      this._emitEvent(delta > 0 ? "request-start" : "request-complete", {
        type: source,
        active: next,
      });
    },

    trackXHR() {
      if (this._xhrPatched) return this;
      if (typeof NETWORK_ORIG_XHR !== "function") return this;

      const tracker = this;

      function PatchedXHR(...args) {
        const xhr = new NETWORK_ORIG_XHR(...args);
        let counted = false;

        const originalSend = xhr.send;

        const markDone = () => {
          if (!counted) return;
          counted = false;
          tracker._changeActive(-1, "xhr");
          tracker._log("XHR completed, active:", tracker.activeRequests);
        };

        xhr.send = function (...sendArgs) {
          if (!counted) {
            counted = true;
            tracker._changeActive(1, "xhr");
            tracker._log("XHR started, active:", tracker.activeRequests);

            xhr.addEventListener("loadend", markDone, { once: true });
          }

          try {
            return originalSend.apply(xhr, sendArgs);
          } catch (err) {
            markDone();
            throw err;
          }
        };

        return xhr;
      }

      PatchedXHR.prototype = NETWORK_ORIG_XHR.prototype;
      Object.setPrototypeOf(PatchedXHR, NETWORK_ORIG_XHR);

      window.XMLHttpRequest = PatchedXHR;
      this._xhrPatched = true;
      return this;
    },

    trackFetch() {
      if (this._fetchPatched) return this;
      if (typeof NETWORK_ORIG_FETCH !== "function") return this;

      const tracker = this;

      window.fetch = function (...args) {
        tracker._changeActive(1, "fetch");
        tracker._log("Fetch started, active:", tracker.activeRequests);

        let result;
        try {
          result = NETWORK_ORIG_FETCH.apply(this, args);
        } catch (err) {
          tracker._changeActive(-1, "fetch");
          tracker._log(
            "Fetch failed synchronously, active:",
            tracker.activeRequests,
          );
          throw err;
        }

        return Promise.resolve(result).finally(() => {
          tracker._changeActive(-1, "fetch");
          tracker._log("Fetch completed, active:", tracker.activeRequests);
        });
      };

      this._fetchPatched = true;
      return this;
    },

    isIdle(idleTimeMs = 500) {
      return (
        this.activeRequests === 0 &&
        Date.now() - this.lastActivity >= idleTimeMs
      );
    },

    waitForIdle(idleTimeMs = 500, timeoutMs = 10000) {
      const tracker = this;

      return new Promise((resolve) => {
        let resolved = false;
        let idleTimer = null;
        let timeoutTimer = null;

        const cleanup = () => {
          if (idleTimer) clearTimeout(idleTimer);
          if (timeoutTimer) clearTimeout(timeoutTimer);

          tracker.eventTarget.removeEventListener(
            "request-start",
            onRequestStart,
          );
          tracker.eventTarget.removeEventListener(
            "request-complete",
            onRequestComplete,
          );
        };

        const finish = (value) => {
          if (resolved) return;
          resolved = true;
          cleanup();
          resolve(value);
        };

        const scheduleCheck = () => {
          if (resolved) return;

          if (tracker.activeRequests > 0) {
            if (idleTimer) {
              clearTimeout(idleTimer);
              idleTimer = null;
            }
            return;
          }

          const quietFor = Date.now() - tracker.lastActivity;
          const remaining = idleTimeMs - quietFor;

          if (remaining <= 0) {
            finish(true);
            return;
          }

          if (idleTimer) clearTimeout(idleTimer);
          idleTimer = setTimeout(() => {
            idleTimer = null;
            if (
              tracker.activeRequests === 0 &&
              Date.now() - tracker.lastActivity >= idleTimeMs
            ) {
              finish(true);
            } else {
              scheduleCheck();
            }
          }, remaining);
        };

        const onRequestStart = () => {
          if (idleTimer) {
            clearTimeout(idleTimer);
            idleTimer = null;
          }
        };

        const onRequestComplete = () => {
          setTimeout(scheduleCheck, 50);
        };

        tracker.eventTarget.addEventListener("request-start", onRequestStart);
        tracker.eventTarget.addEventListener(
          "request-complete",
          onRequestComplete,
        );

        timeoutTimer = setTimeout(() => {
          finish(false);
        }, timeoutMs);

        scheduleCheck();
      });
    },

    getStatus() {
      return {
        activeRequests: this.activeRequests,
        lastActivity: this.lastActivity,
        timeSinceLastActivity: Date.now() - this.lastActivity,
      };
    },

    trackDomResources: function () {
      if (this._domResourcesPatched) return this;
      this._domResourcesPatched = true;

      const tracker = this;
      const tracked = new WeakSet();

      const isStylesheetLink = (el) =>
        el.tagName === "LINK" &&
        (el.rel || "").toLowerCase().split(/\s+/).includes("stylesheet");

      const arm = (el, kind) => {
        if (!(el instanceof Element)) return;
        if (tracked.has(el)) return;

        // IMG: если уже завершился до нашего подключения, считать бессмысленно
        if (kind === "img" && el.complete) return;

        tracked.add(el);
        tracker._changeActive(1, kind);
        tracker._log(`${kind} started, active:`, tracker.activeRequests);

        const done = () => {
          if (!tracked.has(el)) return;
          tracked.delete(el);
          tracker._changeActive(-1, kind);
          tracker._log(`${kind} completed, active:`, tracker.activeRequests);
        };

        el.addEventListener("load", done, { once: true });
        el.addEventListener("error", done, { once: true });
      };

      const watchNode = (node) => {
        if (!(node instanceof Element)) return;

        // Сам узел
        if (node.tagName === "IMG" && node.getAttribute("src")) {
          arm(node, "img");
        } else if (node.tagName === "SCRIPT" && node.getAttribute("src")) {
          arm(node, "script");
        } else if (isStylesheetLink(node) && node.getAttribute("href")) {
          arm(node, "link");
        } else if (node.tagName === "IFRAME" && node.getAttribute("src")) {
          arm(node, "iframe");
        }

        // Потомки
        node
          .querySelectorAll?.(
            'img, script[src], link[rel~="stylesheet"], iframe[src]',
          )
          .forEach((el) => {
            if (el.tagName === "IMG" && el.getAttribute("src")) arm(el, "img");
            if (el.tagName === "SCRIPT" && el.getAttribute("src"))
              arm(el, "script");
            if (isStylesheetLink(el) && el.getAttribute("href"))
              arm(el, "link");
            if (el.tagName === "IFRAME" && el.getAttribute("src"))
              arm(el, "iframe");
          });
      };

      const start = () => {
        const root = document.documentElement;
        if (!root) return;

        // Первичный обход уже существующих элементов
        watchNode(root);

        // Отслеживание новых элементов и изменений src/href/rel
        const mo = new MutationObserver((records) => {
          for (const record of records) {
            if (record.type === "childList") {
              for (const node of record.addedNodes) watchNode(node);
            } else if (
              record.type === "attributes" &&
              record.target instanceof Element
            ) {
              watchNode(record.target);
            }
          }
        });

        mo.observe(root, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ["src", "href", "rel"],
        });

        this._domResourceObserver = mo;
      };

      if (document.documentElement) {
        start();
      } else {
        document.addEventListener("DOMContentLoaded", start, { once: true });
      }

      return this;
    },
  };

  window.__networkActivity.trackXHR();
  window.__networkActivity.trackFetch();
  window.__networkActivity.trackDomResources();

  console.log("initscript.js loaded with network tracking");
})();
