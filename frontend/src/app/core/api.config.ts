/**
 * Base path for backend API calls. Relative on purpose: nginx reverse-proxies
 * `/api` to the backend in production, and `proxy.conf.json` does the same for
 * `ng serve` in development.
 */
export const API_BASE = '/api';
