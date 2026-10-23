/* Adds a Sign in / account button to the viewer's top bar. Injected into index.html by the server, so a rebuilt viewer keeps it. */
(function () {
  var KEY = 'tab2hand_token';
  function tok() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  var st = document.createElement('style');
  st.textContent = '.t2h-nav{text-decoration:none;color:inherit}.t2h-float{position:fixed;top:60px;right:16px;z-index:30}';
  document.head.appendChild(st);
  var el = document.createElement('a');
  el.className = 'btn t2h-nav';
  el.href = '/login.html';
  el.textContent = 'Sign in';

  function mount() {
    var host = document.querySelector('.topbar-actions');
    if (host) {
      if (el.parentNode !== host) { el.classList.remove('t2h-float'); host.appendChild(el); }
    } else if (!el.isConnected && document.body) {
      el.classList.add('t2h-float');
      document.body.appendChild(el);
    }
  }
  new MutationObserver(mount).observe(document.documentElement, { childList: true, subtree: true });
  mount();

  var t = tok();
  if (!t) return;
  fetch('/api/me', { headers: { Authorization: 'Bearer ' + t } })
    .then(function (r) {
      if (r.status === 401) { try { localStorage.removeItem(KEY); } catch (e) {} return null; }
      return r.ok ? r.json() : null;
    })
    .then(function (u) {
      if (!u) return;
      el.textContent = u.username;
      el.title = 'Account (' + u.role + ')';
    })
    .catch(function () {});
})();
