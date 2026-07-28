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
