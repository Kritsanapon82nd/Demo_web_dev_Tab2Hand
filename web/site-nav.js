/* Adds "Songs" and "Sign in" buttons to the viewer's top bar.
   Injected into index.html by the server, so a rebuilt viewer keeps it.
   "Songs" lists what the admin put in the library and opens a song through the viewer's own library dialog. */
(function () {
  if (window.__t2hNav) return;
  window.__t2hNav = true;
  var KEY = 'tab2hand_token';
  function tok() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }

  var st = document.createElement('style');
  st.textContent =
    '.t2h-nav{text-decoration:none;color:inherit}' +
    '.t2h-float{position:fixed;top:60px;right:16px;z-index:30}' +
    '.t2h-back{position:fixed;inset:0;z-index:40;background:#252b2e59;display:grid;place-items:center}' +
    '.t2h-box{background:#efe7d6;border-radius:14px;width:min(520px,100vw - 32px);max-height:calc(100vh - 48px);display:flex;flex-direction:column;padding:18px 20px 16px;box-shadow:0 20px 60px #00000040;color:#252b2e;font-family:inherit}' +
    '.t2h-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}' +
    '.t2h-head h2{margin:0;font-size:18px;font-weight:650}' +
    '.t2h-x{border:0;background:transparent;font-size:22px;line-height:1;cursor:pointer;color:#252b2e;width:34px;height:34px;border-radius:6px}' +
    '.t2h-x:hover{background:#252b2e14}' +
    '.t2h-sub{margin:0 0 10px;color:#5d676c;font-size:13px}' +
    '.t2h-q{width:100%;height:36px;padding:0 12px;border:1px solid #252b2e2e;border-radius:6px;background:#fff9;font:inherit;margin-bottom:10px}' +
    '.t2h-list{list-style:none;margin:0;padding:0;overflow:auto;border-top:1px solid #252b2e18}' +
    '.t2h-list li{display:flex;align-items:center;gap:12px;padding:10px 2px;border-bottom:1px solid #252b2e18}' +
    '.t2h-main{flex:1;min-width:0}' +
    '.t2h-main strong{display:block;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
    '.t2h-main span{font-size:12.5px;color:#5d676c}' +
    '.t2h-empty{padding:18px 2px;color:#5d676c}' +
    '.t2h-msg{margin:10px 0 0;font-size:13px;color:#b4452a;min-height:18px}';
  document.head.appendChild(st);

  function mk(cls, text, href) {
    var e = document.createElement(href ? 'a' : 'button');
    e.className = cls; e.textContent = text;
    if (href) e.href = href; else e.type = 'button';
    return e;
  }
  var songs = mk('btn t2h-nav', 'Songs');
  var sign = mk('btn t2h-nav', 'Sign in', '/login.html');

  function mount() {
    var host = document.querySelector('.topbar-actions');
    [songs, sign].forEach(function (el, i) {
      if (host) {
        if (el.parentNode !== host) { el.classList.remove('t2h-float'); host.appendChild(el); }
      } else if (!el.isConnected && document.body) {
        el.classList.add('t2h-float');
        if (i === 0) el.style.right = '110px';
        document.body.appendChild(el);
      }
    });
  }
  new MutationObserver(mount).observe(document.documentElement, { childList: true, subtree: true });
  mount();

  // ---------- who is signed in ----------
  var t = tok();
  if (t) {
    fetch('/api/me', { headers: { Authorization: 'Bearer ' + t } })
      .then(function (r) {
        if (r.status === 401) { try { localStorage.removeItem(KEY); } catch (e) {} return null; }
        return r.ok ? r.json() : null;
      })
      .then(function (u) { if (u) { sign.textContent = u.username; sign.title = 'Account (' + u.role + ')'; } })
      .catch(function () {});
  }

  // ---------- song list ----------
  function convButton() {
    var bs = document.querySelectorAll('button');
    for (var i = 0; i < bs.length; i++) {
      var s = ((bs[i].textContent || '') + ' ' + (bs[i].getAttribute('aria-label') || '') + ' ' + (bs[i].title || '')).toLowerCase();
      if (s.indexOf('hand poses') >= 0 && !bs[i].closest('.t2h-box')) return bs[i];
    }
    return null;
  }
  function rowFor(item) {
    var rows = document.querySelectorAll('.conv-lib li');
    var best = null;
    for (var i = 0; i < rows.length; i++) {
      var strong = rows[i].querySelector('strong');
      var name = strong ? strong.textContent.trim() : '';
      if (name !== (item.title || item.file)) continue;
      best = best || rows[i];
      var span = rows[i].querySelector('.conv-dim');
      if (item.trackName && span && span.textContent.indexOf(item.trackName) >= 0) return rows[i];
    }
    return best;
  }
  function openSong(item, back, msg) {
    var b = convButton();
    if (!b) { msg.textContent = 'Could not find the viewer’s own library button. Use Make hand poses → Converted songs.'; return; }
    back.remove();
    b.click();
    var tries = 0;
    var iv = setInterval(function () {
      var row = rowFor(item);
      if (row) {
        clearInterval(iv);
        var openBtn = row.querySelector('button.btn-quiet') || row.querySelector('button');
        if (openBtn) openBtn.click();
      } else if (++tries > 40) {
        clearInterval(iv);   // the viewer’s dialog is open now; the song is under "Converted songs"
      }
    }, 250);
  }

  function showSongs() {
    var back = document.createElement('div'); back.className = 't2h-back';
    back.innerHTML =
      '<div class="t2h-box" role="dialog" aria-modal="true" aria-label="Song library">' +
      '<div class="t2h-head"><h2>Song library</h2><button class="t2h-x" type="button" aria-label="Close">×</button></div>' +
      '<p class="t2h-sub">Songs that were already converted. Pick one to watch the hand play it. To use your own tab, drop the tab file and its poses file on the page.</p>' +
      '<input class="t2h-q" type="search" placeholder="Search songs" aria-label="Search songs">' +
      '<ul class="t2h-list"></ul><p class="t2h-msg"></p></div>';
    document.body.appendChild(back);
    var list = back.querySelector('.t2h-list'), q = back.querySelector('.t2h-q'), msg = back.querySelector('.t2h-msg');
    var items = [];
    function close() { back.remove(); document.removeEventListener('keydown', onKey); }
    function onKey(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);
    back.addEventListener('click', function (e) { if (e.target === back) close(); });
    back.querySelector('.t2h-x').onclick = close;

    function draw() {
      var term = q.value.trim().toLowerCase();
      var shown = items.filter(function (it) { return !term || (it.title + ' ' + it.trackName).toLowerCase().indexOf(term) >= 0; });
      list.innerHTML = '';
      if (!shown.length) {
        var li0 = document.createElement('li'); li0.className = 't2h-empty';
        li0.textContent = items.length ? 'No song matches.' : 'No songs have been added yet.';
        list.appendChild(li0); return;
      }
      shown.forEach(function (it) {
        var li = document.createElement('li');
        var main = document.createElement('div'); main.className = 't2h-main';
        var s1 = document.createElement('strong'); s1.textContent = it.title || it.file; s1.title = it.file;
        var s2 = document.createElement('span');
        s2.textContent = (it.trackName ? 'Track: ' + it.trackName + ' · ' : '') + it.notes + ' keyframes';
        main.appendChild(s1); main.appendChild(s2);
        var ob = document.createElement('button'); ob.type = 'button'; ob.className = 'btn btn-primary'; ob.textContent = 'Open';
        ob.style.height = '34px'; ob.style.padding = '0 16px';
        ob.onclick = function () { openSong(it, back, msg); };
        li.appendChild(main); li.appendChild(ob); list.appendChild(li);
      });
    }
    q.oninput = draw;
    list.innerHTML = '<li class="t2h-empty">Loading…</li>';
    fetch('/api/library', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (d) { items = d.items || []; draw(); q.focus(); })
      .catch(function () { list.innerHTML = '<li class="t2h-empty">Could not load the list.</li>'; });
  }
  songs.addEventListener('click', showSongs);
})();
