import { API } from './state.js';

export async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const txt = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${txt}`);
  }
  return res.json();
}
