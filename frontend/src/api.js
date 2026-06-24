const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TOKEN_KEY = "panpay_token";
const ADMIN_TOKEN_KEY = "panpay_admin_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}
export function getAdminToken() {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}
export function setAdminToken(t) {
  if (t) localStorage.setItem(ADMIN_TOKEN_KEY, t);
  else localStorage.removeItem(ADMIN_TOKEN_KEY);
}

async function request(path, { method = "GET", body, auth = true, admin = false, form } = {}) {
  const headers = {};
  const token = admin ? getAdminToken() : getToken();
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = form; // FormData
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${API_URL}${path}`, { method, headers, body: payload });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail;
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : detail || res.statusText;
    throw new Error(msg);
  }
  return data;
}

export const api = {
  // auth
  register: (b) => request("/auth/register", { method: "POST", body: b, auth: false }),
  login: (b) => request("/auth/login", { method: "POST", body: b, auth: false }),
  me: () => request("/auth/me"),
  // settings
  updateSettings: (b) => request("/dashboard/settings", { method: "PATCH", body: b }),
  // api keys
  listKeys: () => request("/dashboard/api-keys"),
  createKey: (b) => request("/dashboard/api-keys", { method: "POST", body: b }),
  revokeKey: (id) => request(`/dashboard/api-keys/${id}`, { method: "DELETE" }),
  // receiving accounts
  listAccounts: () => request("/dashboard/receiving-accounts"),
  createAccount: (b) => request("/dashboard/receiving-accounts", { method: "POST", body: b }),
  setDefaultAccount: (id) => request(`/dashboard/receiving-accounts/${id}/default`, { method: "POST" }),
  deleteAccount: (id) => request(`/dashboard/receiving-accounts/${id}`, { method: "DELETE" }),
  // audit log
  auditLogs: () => request("/dashboard/audit-logs"),
  // membership: plans
  listPlans: () => request("/dashboard/plans"),
  createPlan: (b) => request("/dashboard/plans", { method: "POST", body: b }),
  updatePlan: (id, b) => request(`/dashboard/plans/${id}`, { method: "PATCH", body: b }),
  deletePlan: (id) => request(`/dashboard/plans/${id}`, { method: "DELETE" }),
  // membership: subscriptions
  listSubscriptions: () => request("/dashboard/subscriptions"),
  createSubscription: (b) => request("/dashboard/subscriptions", { method: "POST", body: b }),
  getSubscription: (id) => request(`/dashboard/subscriptions/${id}`),
  renewSubscription: (id) => request(`/dashboard/subscriptions/${id}/invoice`, { method: "POST" }),
  cancelSubscription: (id) => request(`/dashboard/subscriptions/${id}/cancel`, { method: "POST" }),
  generateDueInvoices: () => request("/dashboard/subscriptions/generate-due", { method: "POST" }),
  subscriptionStats: () => request("/dashboard/subscription-stats"),
  changePlan: (id, planId) => request(`/dashboard/subscriptions/${id}/change-plan`, { method: "POST", body: { plan_id: planId } }),
  // coupons
  listCoupons: () => request("/dashboard/coupons"),
  createCoupon: (b) => request("/dashboard/coupons", { method: "POST", body: b }),
  deleteCoupon: (id) => request(`/dashboard/coupons/${id}`, { method: "DELETE" }),
  // notifications
  listNotifications: () => request("/dashboard/notifications"),
  // public member portal
  portalView: (token) => request(`/portal/${token}`, { auth: false }),
  portalRenew: (token) => request(`/portal/${token}/renew`, { method: "POST", auth: false }),
  // settlements
  listSettlements: () => request("/dashboard/settlements"),
  generateSettlement: (b = {}) => request("/dashboard/settlements/generate", { method: "POST", body: b }),
  payout: (id, reference) => request(`/dashboard/settlements/${id}/payout`, { method: "POST", body: { reference } }),
  // charges / stats
  stats: (days = 14) => request(`/dashboard/stats?days=${days}`),
  charges: (status) => request(`/dashboard/charges${status ? `?status=${status}` : ""}`),
  createCharge: (b) => request("/dashboard/charges", { method: "POST", body: b }),
  voidCharge: (id) => request(`/dashboard/charges/${id}/void`, { method: "POST" }),
  refundCharge: (id, reason) => request(`/dashboard/charges/${id}/refund`, { method: "POST", body: { reason } }),
  // public checkout
  checkout: (id) => request(`/checkout/${id}`, { auth: false }),
  submitSlip: (id, formData) =>
    request(`/checkout/${id}/slip`, { method: "POST", form: formData, auth: false }),
};

// Platform admin console (separate token, typ=admin).
export const adminApi = {
  login: (b) => request("/admin/login", { method: "POST", body: b, auth: false }),
  me: () => request("/admin/me", { admin: true }),
  stats: () => request("/admin/stats", { admin: true }),
  merchants: (q) => request(`/admin/merchants${q ? `?q=${encodeURIComponent(q)}` : ""}`, { admin: true }),
  merchant: (id) => request(`/admin/merchants/${id}`, { admin: true }),
  updateMerchant: (id, b) => request(`/admin/merchants/${id}`, { method: "PATCH", body: b, admin: true }),
  actAs: (id) => request(`/admin/merchants/${id}/act-as`, { method: "POST", admin: true }),
  charges: ({ merchantId, status } = {}) => {
    const p = new URLSearchParams();
    if (merchantId) p.set("merchant_id", merchantId);
    if (status) p.set("status", status);
    const qs = p.toString();
    return request(`/admin/charges${qs ? `?${qs}` : ""}`, { admin: true });
  },
  settlements: (merchantId) =>
    request(`/admin/settlements${merchantId ? `?merchant_id=${merchantId}` : ""}`, { admin: true }),
  auditLogs: ({ merchantId, action } = {}) => {
    const p = new URLSearchParams();
    if (merchantId) p.set("merchant_id", merchantId);
    if (action) p.set("action", action);
    const qs = p.toString();
    return request(`/admin/audit-logs${qs ? `?${qs}` : ""}`, { admin: true });
  },

  // Membership management for a specific merchant (admin acts on the merchant's behalf)
  mPlans: (mid) => request(`/admin/merchants/${mid}/plans`, { admin: true }),
  mCreatePlan: (mid, b) => request(`/admin/merchants/${mid}/plans`, { method: "POST", body: b, admin: true }),
  mUpdatePlan: (mid, id, b) => request(`/admin/merchants/${mid}/plans/${id}`, { method: "PATCH", body: b, admin: true }),
  mDeletePlan: (mid, id) => request(`/admin/merchants/${mid}/plans/${id}`, { method: "DELETE", admin: true }),
  mSubscriptions: (mid) => request(`/admin/merchants/${mid}/subscriptions`, { admin: true }),
  mCreateSubscription: (mid, b) => request(`/admin/merchants/${mid}/subscriptions`, { method: "POST", body: b, admin: true }),
  mRenewSubscription: (mid, id) => request(`/admin/merchants/${mid}/subscriptions/${id}/invoice`, { method: "POST", admin: true }),
  mCancelSubscription: (mid, id) => request(`/admin/merchants/${mid}/subscriptions/${id}/cancel`, { method: "POST", admin: true }),
  mGenerateDue: (mid) => request(`/admin/merchants/${mid}/subscriptions/generate-due`, { method: "POST", admin: true }),
  mSubscriptionStats: (mid) => request(`/admin/merchants/${mid}/subscription-stats`, { admin: true }),
  mChangePlan: (mid, id, planId) => request(`/admin/merchants/${mid}/subscriptions/${id}/change-plan`, { method: "POST", body: { plan_id: planId }, admin: true }),
  mCoupons: (mid) => request(`/admin/merchants/${mid}/coupons`, { admin: true }),
  mCreateCoupon: (mid, b) => request(`/admin/merchants/${mid}/coupons`, { method: "POST", body: b, admin: true }),
  mDeleteCoupon: (mid, id) => request(`/admin/merchants/${mid}/coupons/${id}`, { method: "DELETE", admin: true }),
  mNotifications: (mid) => request(`/admin/merchants/${mid}/notifications`, { admin: true }),
};

// Download an authenticated file (e.g. CSV) by fetching with the token then
// triggering a browser save.
export async function downloadFile(path, filename) {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("ดาวน์โหลดไม่สำเร็จ");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Public receipt URL (no auth required; works for paid/refunded charges).
export const receiptUrl = (chargeId) => `${API_URL}/checkout/${chargeId}/receipt.pdf`;

export { API_URL };
