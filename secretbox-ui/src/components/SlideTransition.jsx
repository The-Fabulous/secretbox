import { useLayoutEffect, useRef } from 'react';

// Animate the existing DOM so inputs keep their focus and state.
export default function SlideTransition({ transitionKey, index = 0, className = '', children }) {
  const element = useRef(null);
  const previousIndex = useRef(index);

  useLayoutEffect(() => {
    const direction = index < previousIndex.current ? -1 : 1;
    previousIndex.current = index;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (motion.matches || !element.current?.animate) return undefined;

    const animation = element.current.animate([
      { opacity: 0, transform: `translate3d(calc(var(--slide-distance, 32px) * ${direction}), 0, 0)` },
      { opacity: 1, transform: 'translate3d(0, 0, 0)' },
    ], { duration: 380, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
    const stop = () => animation.cancel();
    motion.addEventListener('change', stop);
    return () => {
      stop();
      motion.removeEventListener('change', stop);
    };
  }, [transitionKey, index]);

  return <div ref={element} className={`slide-transition ${className}`}>{children}</div>;
}
