// ===== MENÚ MÓVIL =====
const menuBtn = document.getElementById('menuBtn');
const nav = document.getElementById('nav');

menuBtn.addEventListener('click', () => nav.classList.toggle('is-open'));
nav.querySelectorAll('a').forEach(a =>
  a.addEventListener('click', () => nav.classList.remove('is-open'))
);

// ===== FECHA EN LA BARRA macOS =====
const fecha = new Date();
document.getElementById('menubarDate').textContent = new Intl.DateTimeFormat('es-MX', {
  weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit'
}).format(fecha).replace(/\./g, '');

// ===== FAQ ACORDEÓN =====
document.querySelectorAll('.faq__q').forEach(btn => {
  btn.addEventListener('click', () => {
    const item = btn.parentElement;
    const answer = item.querySelector('.faq__a');
    const abierto = item.classList.contains('is-open');

    document.querySelectorAll('.faq__item.is-open').forEach(open => {
      open.classList.remove('is-open');
      open.querySelector('.faq__a').style.maxHeight = null;
    });

    if (!abierto) {
      item.classList.add('is-open');
      answer.style.maxHeight = answer.scrollHeight + 'px';
    }
  });
});

// ===== REVEAL AL SCROLL =====
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// ===== VIDEO DE FONDO: reintento de autoplay =====
const video = document.querySelector('.bg-video video');
if (video) {
  const reproducir = () => video.play().catch(() => {});
  reproducir();
  document.addEventListener('click', reproducir, { once: true });
  document.addEventListener('touchstart', reproducir, { once: true });
}

// ===== MODAL DE CAPTURA DE LEADS =====
(function () {
  var overlay = document.getElementById('capOverlay');
  var form = document.getElementById('capForm');
  if (!overlay || !form) return;

  var note = document.getElementById('capNote');
  var submitBtn = document.getElementById('capSubmit');

  // ?fuente=ig etc. para saber de qué red viene el lead
  var fuente = new URLSearchParams(location.search).get('fuente') || 'directo';
  var REFERRAL_FALLBACK =
    'https://app.outlier.ai/expert/referrals/link/4JBXAOTH_L2a6J68TED52x5hpHk';

  function open() {
    overlay.classList.add('is-open');
    overlay.setAttribute('aria-hidden', 'false');
    var n = document.getElementById('capNombre');
    if (n) setTimeout(function () { n.focus(); }, 50);
  }
  function close() {
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden', 'true');
  }

  // Todos los botones data-capture abren el modal
  document.querySelectorAll('[data-capture]').forEach(function (b) {
    b.addEventListener('click', open);
  });
  var closeBtn = document.getElementById('capClose');
  if (closeBtn) closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    submitBtn.disabled = true;
    note.textContent = 'Guardando...';
    var payload = {
      nombre: document.getElementById('capNombre').value.trim(),
      email: document.getElementById('capEmail').value.trim(),
      whatsapp: document.getElementById('capWhats').value.trim(),
      website: document.getElementById('capWebsite').value,
      fuente: fuente
    };
    function go(link) { window.location.href = link || REFERRAL_FALLBACK; }

    fetch('/api/lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, b: b }; }); })
      .then(function (res) {
        if (res.ok && res.b && res.b.referral) {
          note.textContent = '¡Listo! Te llevo a Outlier...';
          go(res.b.referral);
        } else {
          // No perdemos al lead: lo mandamos igual al referral
          note.textContent = 'Continuando...';
          go(REFERRAL_FALLBACK);
        }
      })
      .catch(function () {
        note.textContent = 'Continuando...';
        go(REFERRAL_FALLBACK);
      });
  });
})();
