(() => {
  'use strict';

  const root = document.documentElement;
  const header = document.getElementById('siteHeader');
  const progress = document.getElementById('readingProgress');
  const themeButton = document.getElementById('themeToggle');
  const menuButton = document.getElementById('menuToggle');
  const navigation = document.getElementById('siteNav');

  const updateChrome = () => {
    const top = window.scrollY;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    header.classList.toggle('scrolled', top > 12);
    progress.style.width = `${scrollable > 0 ? Math.min(100, (top / scrollable) * 100) : 0}%`;
  };

  updateChrome();
  window.addEventListener('scroll', updateChrome, { passive: true });

  themeButton.addEventListener('click', () => {
    const next = root.dataset.theme === 'light' ? 'dark' : 'light';
    root.dataset.theme = next;
    localStorage.setItem('depi-theme', next);
  });

  menuButton.addEventListener('click', () => {
    const expanded = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!expanded));
    navigation.classList.toggle('open', !expanded);
  });

  navigation.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      navigation.classList.remove('open');
      menuButton.setAttribute('aria-expanded', 'false');
    });
  });

  const revealElements = document.querySelectorAll('.reveal, .reveal-left, .reveal-right');
  if ('IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.14 });
    revealElements.forEach((element) => revealObserver.observe(element));
  } else {
    revealElements.forEach((element) => element.classList.add('visible'));
  }

  const counters = document.querySelectorAll('.counter');
  const animateCounter = (element) => {
    const target = Number(element.dataset.target || 0);
    const started = performance.now();
    const duration = 750;
    const step = (now) => {
      const ratio = Math.min(1, (now - started) / duration);
      element.textContent = String(Math.round(target * (1 - Math.pow(1 - ratio, 3))));
      if (ratio < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  if ('IntersectionObserver' in window) {
    const counterObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      });
    });
    counters.forEach((counter) => counterObserver.observe(counter));
  } else {
    counters.forEach(animateCounter);
  }

  const sections = [...document.querySelectorAll('main section[id]')];
  const navLinks = [...navigation.querySelectorAll('a[href^="#"]')];
  if ('IntersectionObserver' in window) {
    const sectionObserver = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      navLinks.forEach((link) => link.classList.toggle('active', link.getAttribute('href') === `#${visible.target.id}`));
    }, { rootMargin: '-30% 0px -55%', threshold: [0, .25, .5] });
    sections.forEach((section) => sectionObserver.observe(section));
  }

  const canvas = document.getElementById('particleCanvas');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (canvas && !reducedMotion) {
    const context = canvas.getContext('2d');
    let width = 0;
    let height = 0;
    let particles = [];

    const resize = () => {
      const ratio = Math.min(devicePixelRatio || 1, 2);
      width = innerWidth;
      height = innerHeight;
      canvas.width = Math.floor(width * ratio);
      canvas.height = Math.floor(height * ratio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      const count = Math.min(55, Math.max(22, Math.floor(width / 24)));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - .5) * .18,
        vy: (Math.random() - .5) * .18,
        radius: Math.random() * 1.4 + .35,
      }));
    };

    const draw = () => {
      context.clearRect(0, 0, width, height);
      particles.forEach((particle, index) => {
        particle.x += particle.vx;
        particle.y += particle.vy;
        if (particle.x < 0 || particle.x > width) particle.vx *= -1;
        if (particle.y < 0 || particle.y > height) particle.vy *= -1;
        context.beginPath();
        context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
        context.fillStyle = 'rgba(70, 203, 232, .38)';
        context.fill();
        for (let next = index + 1; next < particles.length; next += 1) {
          const other = particles[next];
          const dx = particle.x - other.x;
          const dy = particle.y - other.y;
          const distance = Math.hypot(dx, dy);
          if (distance >= 105) continue;
          context.beginPath();
          context.moveTo(particle.x, particle.y);
          context.lineTo(other.x, other.y);
          context.strokeStyle = `rgba(19, 196, 163, ${(1 - distance / 105) * .13})`;
          context.stroke();
        }
      });
      requestAnimationFrame(draw);
    };

    resize();
    addEventListener('resize', resize, { passive: true });
    requestAnimationFrame(draw);
  }
})();
