/* PLANiT Agrivoltaic — 공통 인터랙션 (수정할 필요 없음; 원본: shipping site.js) */
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* 항로 실선 채움 트리거 */
window.addEventListener('load', () => document.body.classList.add('loaded'));

/* 스크롤 리빌 */
const io = new IntersectionObserver(es => {
  es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
}, { threshold: .12 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));

/* 진행 바 (.pbar .fill, .series-progress .fill) */
document.querySelectorAll('.pbar .fill, .series-progress .fill').forEach(fill => {
  const pio = new IntersectionObserver(es => {
    es.forEach(e => {
      if (e.isIntersecting) { fill.style.width = (fill.dataset.progress || 0) + '%'; pio.unobserve(fill); }
    });
  }, { threshold: .5 });
  pio.observe(fill);
});

/* 숫자 카운트업 (.count[data-target]) */
document.querySelectorAll('.count').forEach(el => {
  const cio = new IntersectionObserver(es => {
    es.forEach(e => {
      if (!e.isIntersecting) return;
      cio.unobserve(el);
      const target = +el.dataset.target;
      if (reduced) { el.textContent = target.toLocaleString(); return; }
      const dur = 1400, t0 = performance.now();
      (function tick(t) {
        const p = Math.min((t - t0) / dur, 1);
        el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString();
        if (p < 1) requestAnimationFrame(tick);
      })(t0);
    });
  }, { threshold: .6 });
  cio.observe(el);
});

/* 모바일 메뉴: 링크 클릭 시 닫기 */
document.querySelectorAll('#menu a').forEach(a =>
  a.addEventListener('click', () => document.getElementById('menu').classList.remove('open')));
