// Small helpers shared by login.html and admin.html (no framework).
const KEY = 'tab2hand_token';
const $ = (id) => document.getElementById(id);
const store = {
  get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } },
  set(t) { try { localStorage.setItem(KEY, t); } catch (e) {} },
  clear() { try { localStorage.removeItem(KEY); } catch (e) {} },
};
async function api(path, opt = {}) {
  opt.headers = Object.assign({ 'Content-Type': 'application/json' }, opt.headers || {});
  const t = store.get();
  if (t) opt.headers.Authorization = 'Bearer ' + t;
  const r = await fetch('/api' + path, opt);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const det = d.detail;
    const msg = typeof det === 'string' ? det : Array.isArray(det) ? det.map((x) => x.msg).join('; ') : 'Error ' + r.status;
    const e = new Error(msg); e.status = r.status; throw e;
  }
  return d;
}
async function currentUser() {
  if (!store.get()) return null;
  try { return await api('/me'); } catch (e) { if (e.status === 401) store.clear(); return null; }
}
function say(id, text, kind) { const el = $(id); if (!el) return; el.textContent = text || ''; el.className = (el.className.split(' ')[0] || 'msg') + (kind ? ' ' + kind : ''); }
