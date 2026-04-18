import anime from "animejs";

export type AnimeTargets = string | Element | NodeListOf<Element> | Element[];

/**
 * Stagger fade-up entrance for a sequence of elements.
 * Uses transform + opacity only (compositor-friendly).
 */
export function fadeUp(
  targets: AnimeTargets,
  opts: { delay?: number; stagger?: number; duration?: number } = {}
) {
  const { delay = 0, stagger = 70, duration = 800 } = opts;
  return anime({
    targets,
    opacity: [0, 1],
    translateY: [24, 0],
    easing: "cubicBezier(0.22, 1, 0.36, 1)",
    duration,
    delay: anime.stagger(stagger, { start: delay }),
  });
}

/**
 * Reveal a headline word-by-word. Targets must already be split into spans.
 */
export function wordReveal(
  targets: AnimeTargets,
  opts: { delay?: number; stagger?: number } = {}
) {
  const { delay = 0, stagger = 60 } = opts;
  return anime({
    targets,
    opacity: [0, 1],
    translateY: [40, 0],
    rotate: [4, 0],
    easing: "cubicBezier(0.22, 1, 0.36, 1)",
    duration: 900,
    delay: anime.stagger(stagger, { start: delay }),
  });
}

/**
 * Animate a numeric counter from 0 to target value when it scrolls into view.
 * Returns an IntersectionObserver — disconnect on unmount.
 */
export function countUpOnView(
  el: HTMLElement,
  target: number,
  opts: { duration?: number; suffix?: string; prefix?: string; decimals?: number } = {}
) {
  const { duration = 1800, suffix = "", prefix = "", decimals = 0 } = opts;
  let triggered = false;
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && !triggered) {
          triggered = true;
          const obj = { val: 0 };
          anime({
            targets: obj,
            val: target,
            round: decimals === 0 ? 1 : Math.pow(10, decimals),
            duration,
            easing: "easeOutExpo",
            update: () => {
              const formatted =
                decimals === 0
                  ? Math.round(obj.val).toLocaleString("en-IN")
                  : obj.val.toFixed(decimals);
              el.textContent = `${prefix}${formatted}${suffix}`;
            },
          });
        }
      });
    },
    { threshold: 0.4 }
  );
  observer.observe(el);
  return observer;
}

/**
 * Stagger fade-up triggered when container scrolls into view.
 */
export function fadeUpOnView(
  container: HTMLElement,
  selector: string,
  opts: { stagger?: number; duration?: number } = {}
) {
  const { stagger = 90, duration = 800 } = opts;
  const els = container.querySelectorAll(selector);
  els.forEach((el) => {
    (el as HTMLElement).style.opacity = "0";
    (el as HTMLElement).style.transform = "translateY(28px)";
    (el as HTMLElement).style.willChange = "transform, opacity";
  });
  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          anime({
            targets: els,
            opacity: [0, 1],
            translateY: [28, 0],
            easing: "cubicBezier(0.22, 1, 0.36, 1)",
            duration,
            delay: anime.stagger(stagger),
          });
          obs.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );
  observer.observe(container);
  return observer;
}

/**
 * Subtle drifting motion for a background dot grid (transform only).
 */
export function driftBackground(target: AnimeTargets) {
  return anime({
    targets: target,
    translateX: [0, 18, -12, 0],
    translateY: [0, -10, 14, 0],
    duration: 16000,
    easing: "easeInOutSine",
    loop: true,
  });
}
