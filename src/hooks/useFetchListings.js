import { useState, useEffect } from 'react';

/**
 * Hook to fetch apartment listings from the backend API.
 * Falls back silently to the static apartments.json if the API is unavailable
 * or VITE_API_URL is not configured.
 *
 * Usage (future integration):
 *   const { listings, loading } = useFetchListings('all', 20);
 */
export function useFetchListings(city = 'all', count = 20) {
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';

    if (!apiBase) {
      // No API configured — fall back to static JSON
      import('../../apartments.json').then((m) => {
        setListings(m.default);
        setLoading(false);
      });
      return;
    }

    fetch(`${apiBase}/listings?city=${city}&limit=${count}&random=true`)
      .then((r) => r.json())
      .then((data) => {
        setListings(data);
        setLoading(false);
      })
      .catch(() => {
        // API unavailable — silent fallback to static JSON
        import('../../apartments.json').then((m) => {
          setListings(m.default);
          setLoading(false);
        });
      });
  }, [city, count]);

  return { listings, loading };
}
