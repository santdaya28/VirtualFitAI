import { useState, useEffect } from 'react';

/**
 * Custom hook to monitor window scroll position
 * Useful for sticky headers, navbar blur transitions, and back-to-top buttons
 */
export function useScrollPosition() {
  const [scrollPosition, setScrollPosition] = useState(0);

  useEffect(() => {
    const updatePosition = () => {
      setScrollPosition(window.pageYOffset || document.documentElement.scrollTop);
    };

    window.addEventListener('scroll', updatePosition, { passive: true });
    updatePosition();

    return () => window.removeEventListener('scroll', updatePosition);
  }, []);

  return scrollPosition;
}

