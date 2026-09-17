/* 小六壬皮肤运行时：在 <head> 内执行。
   - 首屏绘制前把已保存的皮肤写到 <html data-theme>，避免闪烁；
   - window.msrTheme.apply(id) 在浏览器端切换并写入 localStorage，不经服务器；
   - 需要脚本的皮肤效果（如星夜的星空画布）只在激活时启动，切走时完整清理。 */
(function () {
  const IDS = window.MSR_THEME_IDS || ['paper'];
  const DEFAULT = window.MSR_THEME_DEFAULT || IDS[0];
  const KEY = 'msr-theme';
  const root = document.documentElement;
  const motionQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  const reducedMotion = () => !!(motionQuery && motionQuery.matches);

  function readInitial() {
    let fromUrl = null;
    try { fromUrl = new URLSearchParams(location.search).get('theme'); } catch (e) { /* 无 URL 时忽略 */ }
    if (IDS.includes(fromUrl)) return { id: fromUrl, persist: true };
    let stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) { /* 隐私模式可能禁用存储 */ }
    return { id: IDS.includes(stored) ? stored : DEFAULT, persist: false };
  }

  /* 星夜：闪烁星空、偶发流星与随指针移动的提灯光晕。 */
  function nightEffect() {
    let canvas = null, ctx = null, frameId = 0, stars = [], meteors = [], nextMeteorAt = 0;
    let onResize = null, onMove = null, onVisibility = null, onMotionChange = null;

    function seed() {
      const count = Math.min(260, Math.round(innerWidth * innerHeight / 9000));
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * innerWidth, y: Math.random() * innerHeight,
        r: 0.3 + Math.random() * 1.3, phase: Math.random() * Math.PI * 2,
        speed: 0.4 + Math.random() * 1.2, warm: Math.random() < 0.25,
      }));
    }
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = innerWidth * dpr;
      canvas.height = innerHeight * dpr;
      canvas.style.width = innerWidth + 'px';
      canvas.style.height = innerHeight + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
      if (reducedMotion()) draw(0);
    }
    function spawnMeteor() {
      const x = innerWidth * (0.2 + Math.random() * 0.7);
      meteors.push({ x, y: -20, vx: -4 - Math.random() * 3, vy: 3 + Math.random() * 2, life: 1 });
    }
    function draw(t) {
      ctx.clearRect(0, 0, innerWidth, innerHeight);
      for (const s of stars) {
        const twinkle = reducedMotion() ? 0.7 : 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(s.phase + t / 1000 * s.speed));
        ctx.beginPath();
        ctx.fillStyle = s.warm ? `rgba(241, 212, 138, ${twinkle})` : `rgba(226, 232, 255, ${twinkle})`;
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      meteors = meteors.filter(m => m.life > 0);
      for (const m of meteors) {
        const gradient = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 14, m.y - m.vy * 14);
        gradient.addColorStop(0, `rgba(241, 212, 138, ${m.life})`);
        gradient.addColorStop(1, 'rgba(241, 212, 138, 0)');
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(m.x, m.y);
        ctx.lineTo(m.x - m.vx * 14, m.y - m.vy * 14);
        ctx.stroke();
        m.x += m.vx; m.y += m.vy; m.life -= 0.012;
      }
    }
    function frame(t) {
      if (t > nextMeteorAt) { spawnMeteor(); nextMeteorAt = t + 5000 + Math.random() * 7000; }
      draw(t);
      frameId = requestAnimationFrame(frame);
    }
    function start() {
      if (canvas) return;
      canvas = document.createElement('canvas');
      canvas.id = 'msr-stars';
      canvas.setAttribute('aria-hidden', 'true');
      ctx = canvas.getContext('2d');
      document.body.appendChild(canvas);
      onResize = resize;
      addEventListener('resize', onResize);
      resize();
      if (!reducedMotion()) frameId = requestAnimationFrame(frame);
      onMove = (event) => {
        root.style.setProperty('--msr-mx', event.clientX + 'px');
        root.style.setProperty('--msr-my', event.clientY + 'px');
      };
      addEventListener('pointermove', onMove, { passive: true });
      onVisibility = () => {
        cancelAnimationFrame(frameId);
        if (!document.hidden && !reducedMotion()) frameId = requestAnimationFrame(frame);
      };
      document.addEventListener('visibilitychange', onVisibility);
      onMotionChange = () => {
        cancelAnimationFrame(frameId);
        meteors = [];
        if (reducedMotion()) draw(0); else if (!document.hidden) frameId = requestAnimationFrame(frame);
      };
      if (motionQuery && typeof motionQuery.addEventListener === 'function') motionQuery.addEventListener('change', onMotionChange);
    }
    function stop() {
      if (!canvas) return;
      cancelAnimationFrame(frameId);
      removeEventListener('resize', onResize);
      removeEventListener('pointermove', onMove);
      document.removeEventListener('visibilitychange', onVisibility);
      if (motionQuery && typeof motionQuery.removeEventListener === 'function') motionQuery.removeEventListener('change', onMotionChange);
      canvas.remove();
      canvas = null; ctx = null; stars = []; meteors = [];
      root.style.removeProperty('--msr-mx');
      root.style.removeProperty('--msr-my');
    }
    return { start, stop };
  }

  const effects = { night: nightEffect() };
  let active = null;
  let fadeTimer = 0;

  function syncSwatches() {
    document.querySelectorAll('.theme-swatch[data-theme-id]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.themeId === root.dataset.theme));
    });
  }

  function apply(id, persist = true) {
    if (!IDS.includes(id)) id = DEFAULT;
    const changed = root.dataset.theme !== id;
    if (changed && document.body && !reducedMotion()) {
      root.classList.add('msr-theme-fade');
      clearTimeout(fadeTimer);
      fadeTimer = setTimeout(() => root.classList.remove('msr-theme-fade'), 500);
    }
    root.dataset.theme = id;
    if (persist) { try { localStorage.setItem(KEY, id); } catch (e) { /* 存储不可用时仅本次生效 */ } }
    if (active !== id) {
      if (active && effects[active]) effects[active].stop();
      if (effects[id] && document.body) effects[id].start();
      active = id;
    }
    syncSwatches();
  }

  const initial = readInitial();
  root.dataset.theme = initial.id;
  document.addEventListener('DOMContentLoaded', () => {
    apply(initial.id, initial.persist);
    // 切换按钮由 Vue 稍后挂载；出现后同步一次 aria-pressed 即可，之后由 apply 维护。
    let giveUp = 0;
    const observer = new MutationObserver(() => {
      if (document.querySelector('.theme-swatch')) { syncSwatches(); observer.disconnect(); clearTimeout(giveUp); }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    giveUp = setTimeout(() => observer.disconnect(), 15000);
  });

  window.msrTheme = { apply, current: () => root.dataset.theme, ids: IDS.slice() };
})();
