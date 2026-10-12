/* Johansen Bolig – henter indstillinger fra redigeringspanelet (/admin).
 * Filen admin/indstillinger.json læses direkte fra GitHub, så rettelser
 * i panelet vises uden en ny udgivelse på Netlify.
 * Indsættes på alle sider via Netlify → Snippet injection:
 *   <script src="/admin/indlaes-indstillinger.js" defer></script>
 * Fejler hentningen, vises sidens standardtekster. */
(function () {
  var KILDE = 'https://raw.githubusercontent.com/Johansenbolig/johansenbolig-website/main/admin/indstillinger.json';
  var NOEGLER = ['trippelStatus', 'olufStatus', 'email', 'visMedieomtale'];
  var data = null;
  var forsoeg = 0;

  fetch(KILDE, { cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && typeof d === 'object') { data = d; anvend(); } })
    .catch(function () {});

  function anvend() {
    var klar = typeof window.__dcSetProps === 'function' &&
               typeof window.__dcRootName === 'function' &&
               document.getElementById('dc-root');
    if (!klar) {
      if (forsoeg++ < 400) setTimeout(anvend, 50);
      return;
    }
    var props = {};
    NOEGLER.forEach(function (k) {
      if (data[k] !== undefined && data[k] !== null && data[k] !== '') props[k] = data[k];
    });
    window.__dcSetProps(window.__dcRootName(), props);
    if (props.email) retMailLinks(props.email);
  }

  /* Mail-linket (mailto:) står fast i designet – ret det, så det følger panelet. */
  function retMailLinks(email) {
    var rod = document.getElementById('dc-root');
    var ret = function () {
      var links = rod.querySelectorAll('a[href^="mailto:"]');
      for (var i = 0; i < links.length; i++) {
        if (links[i].getAttribute('href') !== 'mailto:' + email) links[i].setAttribute('href', 'mailto:' + email);
      }
    };
    ret();
    new MutationObserver(ret).observe(rod, { childList: true, subtree: true });
  }
})();
