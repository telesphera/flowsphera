// the language first: English is in the code, another language is a dictionary i18n/<code>.json (none = English);
// the saved choice, else the browser's language; then the app
(function () {
  // (2.12.6, forum #102) index.html names this script boot.js?v=<stamp>: app.js gets the same stamp, so an upgrade
  // loads the new front end at once instead of the browser's day-old copy
  const v = ((document.currentScript && document.currentScript.src) || '').split('?v=')[1] || '';
  let l = ''; try { l = localStorage.getItem('ft-lang') || ''; } catch (e) {}
  if (!/^[a-z]{2,3}$/.test(l)) l = (navigator.language || 'en').slice(0, 2).toLowerCase();
  const start = (lang, dict) => { window.FT_LANG = lang; window.FT_DICT = dict;
    const s = document.createElement('script'); s.src = 'app.js' + (v ? '?v=' + encodeURIComponent(v) : ''); document.body.appendChild(s); };
  if (!/^[a-z]{2,3}$/.test(l) || l === 'en') return start('en', {});
  fetch(`i18n/${l}.json`, {cache: 'no-cache'}).then(r => r.ok ? r.json() : null).catch(() => null)
    .then(d => d ? start(l, d) : start('en', {}));
})();
