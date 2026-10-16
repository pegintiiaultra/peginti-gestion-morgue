// Accès à l'API. Le jeton est gardé dans sessionStorage (effacé à la fermeture de l'onglet).
const KEY = "peginti_token";
export const state = { user: null };

export const getToken = () => { try { return sessionStorage.getItem(KEY); } catch { return null; } };
export function setToken(t) {
  try { t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY); } catch { /* stockage indisponible */ }
}

export class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status = status; this.code = code; }
}

async function raw(path, opt = {}) {
  const headers = {};
  const t = getToken();
  if (t) headers.Authorization = "Bearer " + t;
  let body;
  if (opt.form) body = opt.form;
  else if (opt.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opt.body); }
  let res;
  try { res = await fetch(path, { method: opt.method || "GET", headers, body }); }
  catch { throw new ApiError("Serveur injoignable. Vérifiez la connexion et réessayez.", 0); }
  if (res.status === 401 && !opt.noAuthEvent) window.dispatchEvent(new Event("auth-expired"));
  return res;
}

export async function api(path, opt) {
  const res = await raw(path, opt);
  let data = null;
  try { data = await res.json(); } catch { /* réponse vide */ }
  if (res.status === 403 && data && data.code === "MFA_A_ACTIVER") window.dispatchEvent(new Event("mfa-required"));
  if (!res.ok) throw new ApiError((data && data.error) || `Erreur ${res.status}`, res.status, data && data.code);
  return data;
}

export async function apiBlob(path, opt) {
  const res = await raw(path, opt);
  if (!res.ok) {
    let msg = "Fichier introuvable.";
    try { msg = (await res.json()).error || msg; } catch { /* pas de détail */ }
    throw new ApiError(msg, res.status);
  }
  return res.blob();
}
