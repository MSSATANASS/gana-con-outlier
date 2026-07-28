// ===== MENÚ MÓVIL =====
const menuToggle = document.getElementById('menuToggle');
const nav = document.getElementById('nav');

menuToggle.addEventListener('click', () => {
  nav.classList.toggle('nav--open');
  menuToggle.classList.toggle('menu-toggle--open');
});

// Cerrar menú al hacer clic en un enlace
nav.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    nav.classList.remove('nav--open');
    menuToggle.classList.remove('menu-toggle--open');
  });
});

// ===== HEADER CON SOMBRA AL SCROLL =====
const header = document.getElementById('header');
window.addEventListener('scroll', () => {
  header.classList.toggle('header--scrolled', window.scrollY > 10);
});

// ===== FAQ ACORDEÓN =====
document.querySelectorAll('.faq__question').forEach(button => {
  button.addEventListener('click', () => {
    const item = button.parentElement;
    const answer = item.querySelector('.faq__answer');
    const isOpen = item.classList.contains('faq__item--open');

    // Cerrar todos
    document.querySelectorAll('.faq__item--open').forEach(openItem => {
      openItem.classList.remove('faq__item--open');
      openItem.querySelector('.faq__answer').style.maxHeight = null;
    });

    // Abrir el clickeado (si no estaba abierto)
    if (!isOpen) {
      item.classList.add('faq__item--open');
      answer.style.maxHeight = answer.scrollHeight + 'px';
    }
  });
});

// ===== ANIMACIÓN REVEAL AL SCROLL =====
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('reveal--visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
