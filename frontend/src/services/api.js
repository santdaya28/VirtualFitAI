/**
 * VirtualFit AI — API Client Service
 * Connects frontend pages to FastAPI backend endpoints with graceful fallback
 * to local sample data when backend is not running.
 */
import { SAMPLE_CLOTHES } from '../data/sampleClothes';

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Check backend health and connectivity
 */
export async function checkBackendHealth() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);

    const response = await fetch(`${API_BASE_URL}/health`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      return { connected: true, data };
    }
    return { connected: false, error: `HTTP ${response.status}` };
  } catch (err) {
    return {
      connected: false,
      error: err.name === 'AbortError' ? 'Connection timed out' : err.message,
    };
  }
}

/**
 * Fetch catalogue garments with optional category and search filters
 */
export async function fetchGarments({ category = 'All', search = '' } = {}) {
  try {
    const params = new URLSearchParams();
    if (category && category !== 'All') {
      params.append('category', category);
    }
    if (search && search.trim()) {
      params.append('search', search.trim());
    }

    const queryString = params.toString();
    const url = `${API_BASE_URL}/garments${queryString ? `?${queryString}` : ''}`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data.items) && data.items.length > 0) {
        return { source: 'backend', items: data.items, total: data.total };
      }
    }
  } catch {
    // Backend offline or unreachable — seamlessly use local fallback
  }

  // Graceful Fallback: filter local sample clothes
  let filtered = Array.isArray(SAMPLE_CLOTHES) ? [...SAMPLE_CLOTHES] : [];

  if (category && category !== 'All') {
    filtered = filtered.filter(
      (item) => item.category?.toLowerCase() === category.toLowerCase()
    );
  }

  if (search && search.trim()) {
    const q = search.toLowerCase();
    filtered = filtered.filter(
      (item) =>
        item.name?.toLowerCase().includes(q) ||
        item.description?.toLowerCase().includes(q)
    );
  }

  return { source: 'local', items: filtered, total: filtered.length };
}

/**
 * Fetch a single garment by ID
 */
export async function fetchGarmentById(id) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);

    const response = await fetch(`${API_BASE_URL}/garments/${id}`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      return await response.json();
    }
  } catch {
    // Fallback
  }

  return (
    SAMPLE_CLOTHES.find((g) => g.id === id || String(g.id) === String(id)) ||
    null
  );
}

/**
 * Submit a Virtual Try-On request
 */
export async function submitTryOnRequest({
  customerPhotoUrl,
  garmentId,
  userNotes = '',
}) {
  try {
    const response = await fetch(`${API_BASE_URL}/tryon`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        customer_photo_url: customerPhotoUrl,
        garment_id: garmentId,
        notes: userNotes,
      }),
    });

    if (response.ok) {
      return await response.json();
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed with HTTP ${response.status}`);
  } catch (err) {
    return {
      status: 'pending_ai_integration',
      message: 'AI Try-on service adapter queued. Model connection pending in Step 2.',
      error: err.message,
    };
  }
}
