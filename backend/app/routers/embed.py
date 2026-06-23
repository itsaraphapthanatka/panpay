"""Serves panpay.js — a drop-in script merchants embed to open a popup checkout.

Usage on the merchant's site:

    <script src="https://your-gateway/panpay.js"></script>
    <script>
      // chargeId comes from POST /v1/charges on your server
      PanPay.checkout({
        chargeId: "chg_...",
        onSuccess: function (e) { console.log("paid", e); },
        onClose:   function () { console.log("closed"); },
      });
    </script>
"""

from fastapi import APIRouter, Response

from ..config import settings

router = APIRouter(tags=["embed"])

_PANPAY_JS = """
(function () {
  "use strict";
  var BASE = "__CHECKOUT_BASE__";
  function el(tag, css) { var e = document.createElement(tag); if (css) e.style.cssText = css; return e; }

  function checkout(opts) {
    opts = opts || {};
    if (!opts.chargeId) { console.error("[PanPay] checkout: chargeId is required"); return; }
    var overlay = el("div",
      "position:fixed;inset:0;background:rgba(15,23,42,.55);display:flex;" +
      "align-items:center;justify-content:center;z-index:2147483647;padding:16px;");
    var frame = el("iframe",
      "width:440px;max-width:100%;height:660px;max-height:94vh;border:0;border-radius:18px;" +
      "box-shadow:0 24px 70px rgba(0,0,0,.35);background:#fff;");
    frame.src = BASE + "/pay/" + encodeURIComponent(opts.chargeId) + "?embed=1";
    frame.allow = "clipboard-write";
    overlay.appendChild(frame);
    document.body.appendChild(overlay);

    function close() {
      window.removeEventListener("message", onMsg);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      if (opts.onClose) opts.onClose();
    }
    function onMsg(e) {
      var d = e.data;
      if (!d || typeof d !== "object" || !d.type) return;
      if (d.chargeId && d.chargeId !== opts.chargeId) return;
      if (d.type === "panpay:paid") { if (opts.onSuccess) opts.onSuccess(d); }
      else if (d.type === "panpay:close") { close(); }
    }
    window.addEventListener("message", onMsg);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });
    return { close: close };
  }

  window.PanPay = { checkout: checkout, base: BASE };
})();
""".strip()


@router.get("/panpay.js")
def panpay_js():
    js = _PANPAY_JS.replace("__CHECKOUT_BASE__", settings.checkout_base_url)
    return Response(
        content=js,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )
