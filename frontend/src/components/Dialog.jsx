import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

const DialogContext = createContext(null);

/** Async replacements for window.confirm / prompt / alert, rendered as styled modals.
 *  Usage: const ui = useDialog(); if (await ui.confirm("ลบ?")) ...
 *  Each returns a promise: confirm → bool, prompt → string|null, alert → void. */
export function DialogProvider({ children }) {
  const [dlg, setDlg] = useState(null); // { kind, title, message, ... , resolve }
  const [value, setValue] = useState("");
  const inputRef = useRef(null);

  const open = useCallback((spec) => {
    return new Promise((resolve) => {
      const opts = typeof spec === "string" ? { message: spec } : spec || {};
      setValue(opts.defaultValue || "");
      setDlg({ ...opts, resolve });
    });
  }, []);

  const close = useCallback((result) => {
    setDlg((cur) => {
      if (cur) cur.resolve(result);
      return null;
    });
  }, []);

  const ctx = {
    confirm: (spec) => open({ kind: "confirm", ...(typeof spec === "string" ? { message: spec } : spec) }),
    prompt: (spec) => open({ kind: "prompt", ...(typeof spec === "string" ? { message: spec } : spec) }),
    alert: (spec) => open({ kind: "alert", ...(typeof spec === "string" ? { message: spec } : spec) }),
  };

  useEffect(() => {
    if (!dlg) return;
    if (dlg.kind === "prompt") inputRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") close(dlg.kind === "confirm" ? false : dlg.kind === "prompt" ? null : undefined);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dlg, close]);

  function onSubmit(e) {
    e.preventDefault();
    if (dlg.kind === "prompt") close(value);
    else close(true);
  }

  const cancelResult = dlg ? (dlg.kind === "confirm" ? false : dlg.kind === "prompt" ? null : undefined) : undefined;

  return (
    <DialogContext.Provider value={ctx}>
      {children}
      {dlg && (
        <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && close(cancelResult)}>
          <form className="modal-card" style={{ maxWidth: 420 }} onSubmit={onSubmit}>
            <div className="modal-head">
              <h3>{dlg.title || (dlg.kind === "alert" ? "แจ้งเตือน" : dlg.kind === "prompt" ? "กรอกข้อมูล" : "ยืนยัน")}</h3>
              <button type="button" className="modal-close" onClick={() => close(cancelResult)} aria-label="close">✕</button>
            </div>
            {dlg.message && (
              <p style={{ marginTop: 0, color: "var(--text)", whiteSpace: "pre-line", lineHeight: 1.5 }}>{dlg.message}</p>
            )}
            {dlg.kind === "prompt" && (
              <label className="field" style={{ marginBottom: 0 }}>
                {dlg.label && <span className="lbl">{dlg.label}</span>}
                <input
                  ref={inputRef}
                  value={value}
                  placeholder={dlg.placeholder || ""}
                  onChange={(e) => setValue(e.target.value)}
                />
              </label>
            )}
            <div className="modal-actions">
              {dlg.kind !== "alert" && (
                <button type="button" className="btn ghost" onClick={() => close(cancelResult)}>
                  {dlg.cancelLabel || "ยกเลิก"}
                </button>
              )}
              <button type="submit" className={`btn ${dlg.danger ? "danger" : ""}`} autoFocus={dlg.kind !== "prompt"}>
                {dlg.confirmLabel || (dlg.kind === "alert" ? "ตกลง" : "ยืนยัน")}
              </button>
            </div>
          </form>
        </div>
      )}
    </DialogContext.Provider>
  );
}

export function useDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) throw new Error("useDialog must be used within a DialogProvider");
  return ctx;
}
