/**
 * VirtualFit AI — API Client Service
 * Connects frontend pages to FastAPI backend endpoints (/api/shops and /api/products)
 * with robust error handling, bidirectional data adapters, and strict multi-shop isolation.
 */

// Base API URL pointing to the FastAPI backend (/api)
export const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Returns the backend origin/root URL without a trailing /api suffix.
 */
export function getBackendRootUrl() {
  return API_BASE_URL.replace(/\/api\/?$/, '');
}

/**
 * Parses HTTP error responses from FastAPI / Pydantic v2 into readable error messages
 */
async function parseErrorMessage(response, defaultMessage = 'API request failed') {
  if (response.status === 401) {
    // Automatically purge rejected or expired token from client storage
    clearAuthToken();
  }
  try {
    const data = await response.json();
    if (data?.detail) {
      if (Array.isArray(data.detail)) {
        // Pydantic validation error list
        return data.detail
          .map((err) => `${err.loc?.slice(-1)[0] || 'field'}: ${err.msg}`)
          .join('; ');
      }
      return String(data.detail);
    }
  } catch {
    // Response was not JSON
  }
  return `${defaultMessage} (HTTP ${response.status} ${response.statusText})`.trim();
}

/* ==========================================================================
   AUTHENTICATION & SESSION TOKEN MANAGEMENT
   ========================================================================== */

const TOKEN_STORAGE_KEY = 'virtualfit_auth_token';

export function getAuthToken() {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Ignore storage quota errors
  }
}

export function clearAuthToken() {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore
  }
}

export function getAuthHeaders() {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Registers a new customer or shop owner account.
 * POST /api/auth/register
 */
export async function registerUser({ email, password, fullName = '', role = 'customer', shopName = '' }) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      full_name: fullName,
      role,
      shop_name: shopName || undefined,
    }),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Registration failed');
    throw new Error(errorMsg);
  }

  const data = await response.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

/**
 * Authenticates user credentials and stores access token.
 * POST /api/auth/login
 */
export async function loginUser({ email, password }) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Login failed');
    throw new Error(errorMsg);
  }

  const data = await response.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

/**
 * Retrieves the currently authenticated user's profile using the stored token.
 * GET /api/auth/me
 */
export async function fetchCurrentUser() {
  const token = getAuthToken();
  if (!token) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      clearAuthToken();
      return null;
    }

    return await response.json();
  } catch {
    return null;
  }
}

/**
 * Logs out the current user, revoking the active bearer token on the backend
 * and clearing local session storage.
 * POST /api/auth/logout
 */
export async function logoutUser() {
  const token = getAuthToken();
  if (token) {
    try {
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
      });
    } catch {
      // Backend unreachable or offline; safely continue to purge local token
    }
  }
  clearAuthToken();
}


/* ==========================================================================
   DATA ADAPTERS: BACKEND ↔ FRONTEND NORMALIZATION
   ========================================================================== */

/**
 * Converts a backend ProductResponse object into the format expected by frontend UI components.
 *
 * Mappings:
 * - id: number
 * - product_name -> name
 * - description -> description
 * - category -> category
 * - price -> numeric price
 * - size (comma-separated string e.g. "S, M, L, XL") -> sizes (array of strings)
 * - color (string e.g. "Navy Blue") -> colors (array of strings)
 * - image_url -> image
 * - stock_quantity & is_available -> status ('In Stock' | 'Low Stock' | 'Out of Stock')
 */
export function backendToFrontendProduct(backendProduct) {
  if (!backendProduct) return null;

  // 1. Format sizes into an array
  let sizes = ['S', 'M', 'L', 'XL'];
  if (backendProduct.size && typeof backendProduct.size === 'string') {
    const parsed = backendProduct.size
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (parsed.length > 0) sizes = parsed;
  }

  // 2. Format colors into an array
  let colors = ['Navy Blue'];
  if (backendProduct.color && typeof backendProduct.color === 'string') {
    const parsed = backendProduct.color
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);
    if (parsed.length > 0) colors = parsed;
  }

  // 3. Compute status badge from stock_quantity and is_available
  let status = 'In Stock';
  const qty = Number(backendProduct.stock_quantity ?? 0);
  const available = backendProduct.is_available !== false;

  if (!available || qty === 0) {
    status = 'Out of Stock';
  } else if (qty <= 5) {
    status = 'Low Stock';
  } else {
    status = 'In Stock';
  }

  // 4. Parse numeric price
  const price =
    typeof backendProduct.price === 'number'
      ? backendProduct.price
      : parseFloat(String(backendProduct.price).replace(/[^\d.]/g, '')) || 0;

  // 5. Parse createdAt date string (YYYY-MM-DD)
  let createdAt = new Date().toISOString().split('T')[0];
  if (backendProduct.created_at) {
    try {
      createdAt = new Date(backendProduct.created_at).toISOString().split('T')[0];
    } catch {
      // Keep default
    }
  }

  // Normalize image URL: handle relative /uploads/ paths
  let imageUrl = backendProduct.image_url || '';
  if (imageUrl && imageUrl.startsWith('/uploads/')) {
    imageUrl = `${getBackendRootUrl()}${imageUrl}`;
  }

  return {
    id: backendProduct.id,
    shop_id: backendProduct.shop_id,
    name: backendProduct.product_name,
    product_name: backendProduct.product_name,
    description: backendProduct.description || '',
    category: backendProduct.category || 'Formal',
    price,
    sizes,
    colors,
    status,
    image: imageUrl,
    image_url: imageUrl,
    stock_quantity: qty,
    is_available: available,
    createdAt,
    // Frontend UI presentation helpers
    fit: 'Regular Fit',
    fallbackBg: 'from-indigo-900 to-slate-900',
  };
}

/**
 * Converts a frontend product object (from forms or component state)
 * into a backend ProductCreate or ProductUpdate payload.
 * Supports both full creation payloads and partial field updates.
 */
export function frontendToBackendProduct(frontendProduct, fallbackShopId = null) {
  if (!frontendProduct) return null;

  const payload = {};

  // Resolve shop_id
  const resolvedShopId =
    frontendProduct.shop_id ??
    frontendProduct.shopId ??
    fallbackShopId;
  if (resolvedShopId !== undefined && resolvedShopId !== null) {
    payload.shop_id = parseInt(resolvedShopId, 10);
  }

  // Resolve product name (only include if provided and non-empty)
  const rawName = frontendProduct.product_name ?? frontendProduct.name;
  if (typeof rawName === 'string' && rawName.trim()) {
    payload.product_name = rawName.trim();
  }

  // Resolve description
  if (frontendProduct.description !== undefined) {
    payload.description = frontendProduct.description?.trim() || null;
  }

  // Resolve category
  if (frontendProduct.category !== undefined) {
    payload.category = frontendProduct.category?.trim() || null;
  }

  // Resolve price (Decimal-compatible number >= 0)
  if (frontendProduct.price !== undefined) {
    const price =
      typeof frontendProduct.price === 'number'
        ? Math.max(0, frontendProduct.price)
        : Math.max(0, parseFloat(String(frontendProduct.price).replace(/[^\d.]/g, '')) || 0);
    payload.price = price;
  }

  // Format sizes array to comma-separated string
  if (frontendProduct.sizes !== undefined || frontendProduct.size !== undefined) {
    if (Array.isArray(frontendProduct.sizes) && frontendProduct.sizes.length > 0) {
      payload.size = frontendProduct.sizes.join(', ');
    } else if (typeof frontendProduct.size === 'string' && frontendProduct.size.trim()) {
      payload.size = frontendProduct.size.trim();
    } else {
      payload.size = null;
    }
  }

  // Format colors array to string
  if (frontendProduct.colors !== undefined || frontendProduct.color !== undefined) {
    if (Array.isArray(frontendProduct.colors) && frontendProduct.colors.length > 0) {
      payload.color = frontendProduct.colors.join(', ');
    } else if (typeof frontendProduct.color === 'string' && frontendProduct.color.trim()) {
      payload.color = frontendProduct.color.trim();
    } else {
      payload.color = null;
    }
  }

  // Format image_url
  if (frontendProduct.image !== undefined || frontendProduct.image_url !== undefined) {
    payload.image_url = (frontendProduct.image ?? frontendProduct.image_url ?? '').trim() || null;
  }

  // Format stock_quantity and is_available
  let stockQuantity = frontendProduct.stock_quantity;
  let isAvailable = frontendProduct.is_available;

  if (stockQuantity === undefined && frontendProduct.status !== undefined) {
    if (frontendProduct.status === 'Out of Stock') {
      stockQuantity = 0;
    } else if (frontendProduct.status === 'Low Stock') {
      stockQuantity = 5;
    } else {
      stockQuantity = 25; // Standard inventory
    }
  }

  if (stockQuantity !== undefined && stockQuantity !== null) {
    payload.stock_quantity = Math.max(0, parseInt(stockQuantity, 10) || 0);
  }

  if (isAvailable === undefined && frontendProduct.status !== undefined) {
    isAvailable = frontendProduct.status !== 'Out of Stock';
  }

  if (isAvailable !== undefined && isAvailable !== null) {
    payload.is_available = Boolean(isAvailable);
  }

  return payload;
}

/* ==========================================================================
   SHOP REST API CLIENT
   ========================================================================== */

/**
 * Fetches registered shops with pagination and optional search filter.
 * GET /api/shops
 */
export async function fetchShops({ skip = 0, limit = 20, search = '' } = {}) {
  const params = new URLSearchParams();
  if (skip) params.append('skip', skip);
  if (limit) params.append('limit', limit);
  if (search && search.trim()) params.append('search', search.trim());

  const queryString = params.toString();
  const url = `${API_BASE_URL}/shops${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to fetch shops');
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Retrieves the primary shop from the database, or creates a default boutique if none exists.
 * This guarantees a valid shop_id is always available for product creation.
 */
export async function getOrCreateDefaultShop() {
  const token = getAuthToken();
  if (!token) {
    throw new Error('Authentication required: sign in as a shop owner to access your boutique.');
  }
  const user = await fetchCurrentUser();
  if (!user || user.role !== 'shop_owner' || !user.shop_id) {
    throw new Error('Only authenticated shop-owner accounts linked to a boutique can manage shop inventory.');
  }
  return await fetchShopById(user.shop_id);
}

/**
 * Updates details of a registered shop.
 * PUT /api/shops/{shopId}
 */
export async function updateShop(shopId, data) {
  if (!shopId) {
    throw new Error('Shop ID is required for updating.');
  }

  const payload = {
    ...(data.shop_name && { shop_name: data.shop_name.trim() }),
    ...(data.owner_name !== undefined && { owner_name: data.owner_name?.trim() || null }),
    ...(data.email !== undefined && { email: data.email?.trim() || null }),
    ...(data.phone !== undefined && { phone: data.phone?.trim() || null }),
    ...(data.address !== undefined && { address: data.address?.trim() || null }),
  };

  const response = await fetch(`${API_BASE_URL}/shops/${shopId}`, {
    method: 'PUT',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, `Failed to update shop ID ${shopId}`);
    throw new Error(errorMsg);
  }

  return await response.json();
}

/* ==========================================================================
   PRODUCT REST API CLIENT
   ========================================================================== */

/**
 * Fetches products from the backend with optional filtering.
 * GET /api/products
 * Returns array of frontend-normalized products.
 */
export async function fetchProducts({
  shop_id = null,
  shop_slug = null,
  category = null,
  search = null,
  is_available = null,
  skip = 0,
  limit = 100,
} = {}) {
  const cleanSlug = shop_slug ? String(shop_slug).trim().toLowerCase() : null;
  if (!shop_id && !cleanSlug && !getAuthToken()) {
    throw new Error('Storefront context (shop_id or shop_slug) is required to list products.');
  }

  const params = new URLSearchParams();
  if (shop_id !== null && shop_id !== undefined) params.append('shop_id', shop_id);
  if (cleanSlug) params.append('shop_slug', cleanSlug);
  if (category && category !== 'All') params.append('category', category);
  if (search && search.trim()) params.append('search', search.trim());
  if (is_available !== null && is_available !== undefined) params.append('is_available', is_available);
  if (skip) params.append('skip', skip);
  if (limit) params.append('limit', limit);

  const queryString = params.toString();
  const url = `${API_BASE_URL}/products${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url, {
    cache: 'no-store',
    headers: {
      ...getAuthHeaders(),
    },
  });
  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to fetch products');
    const err = new Error(errorMsg);
    err.status = response.status;
    throw err;
  }

  const rawProducts = await response.json();
  if (!Array.isArray(rawProducts)) {
    return [];
  }

  return rawProducts.map(backendToFrontendProduct);
}

/**
 * Creates a new garment product owned by the authenticated shop owner.
 * POST /api/products
 */
export async function createProduct(productData, fallbackShopId = null) {
  const payload = frontendToBackendProduct(productData, fallbackShopId);
  if (!payload.shop_id) {
    delete payload.shop_id;
  }

  if (!payload.product_name) {
    throw new Error('Cannot create product: Garment name cannot be empty.');
  }

  const response = await fetch(`${API_BASE_URL}/products`, {
    method: 'POST',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to create product');
    throw new Error(errorMsg);
  }

  const created = await response.json();
  return backendToFrontendProduct(created);
}

/**
 * Updates an existing product by ID.
 * PUT /api/products/{productId}
 */
export async function updateProduct(productId, productData) {
  if (!productId) {
    throw new Error('Product ID is required for updating.');
  }

  const payload = frontendToBackendProduct(productData);

  const response = await fetch(`${API_BASE_URL}/products/${productId}`, {
    method: 'PUT',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, `Failed to update product ID ${productId}`);
    throw new Error(errorMsg);
  }

  const updated = await response.json();
  return backendToFrontendProduct(updated);
}

/**
 * Deletes a product by ID.
 * DELETE /api/products/{productId}
 */
export async function deleteProduct(productId) {
  if (!productId) {
    throw new Error('Product ID is required for deletion.');
  }

  const response = await fetch(`${API_BASE_URL}/products/${productId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, `Failed to delete product ID ${productId}`);
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Uploads a garment product photo to the backend static storage.
 * POST /api/products/upload-image (multipart/form-data)
 *
 * Validates file size (max 5 MB) and extensions (JPG, JPEG, PNG, WebP) client-side
 * before dispatching to FastAPI.
 *
 * @param {File} file - Image file object selected from user's device
 * @returns {Promise<{ image_url: string, filename: string, size_bytes: number, status: string }>}
 */
export async function uploadProductImage(file) {
  if (!file) {
    throw new Error('No image file selected for upload.');
  }

  // Client-side file size validation (5 MB limit)
  const MAX_SIZE_BYTES = 5 * 1024 * 1024;
  if (file.size > MAX_SIZE_BYTES) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
    throw new Error(`Image size (${sizeMb} MB) exceeds maximum allowed limit of 5 MB.`);
  }

  // Client-side extension and MIME type validation
  const allowedExtensions = ['.jpg', '.jpeg', '.png', '.webp'];
  const allowedMimeTypes = [
    'image/jpeg',
    'image/jpg',
    'image/pjpeg',
    'image/png',
    'image/x-png',
    'image/webp',
  ];
  const nameLower = (file.name || '').toLowerCase();
  const mimeLower = (file.type || '').toLowerCase();
  const hasValidExt = allowedExtensions.some((ext) => nameLower.endsWith(ext));
  const hasValidMime = allowedMimeTypes.includes(mimeLower);
  if ((!hasValidExt && !hasValidMime) || (mimeLower && !hasValidMime)) {
    throw new Error('Invalid file format. Please upload a JPG, JPEG, PNG, or WebP image.');
  }

  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/products/upload-image`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
    // Note: Do not set Content-Type header so the browser sets multipart/form-data with boundary
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to upload image to server');
    throw new Error(errorMsg);
  }

  return await response.json();
}

/* ==========================================================================
   LEGACY / UTILITY FUNCTIONS (Preserved for compatibility)
   ========================================================================== */

/**
 * Checks backend health and connectivity (/api/health)
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
 * Fetch catalogue garments with optional category and search filters.
 * Tries the backend /api/products first, falls back gracefully to local sampleClothes.
 */
export async function fetchGarments({ shop_id = null, shop_slug = null, category = 'All', search = '' } = {}) {
  if (!shop_id && !shop_slug) {
    return { source: 'unscoped', items: [], total: 0 };
  }
  const products = shop_slug
    ? await fetchStorefrontProducts(shop_slug, {
        category: category !== 'All' ? category : '',
        search: search.trim(),
      })
    : await fetchProducts({
        shop_id,
        category: category !== 'All' ? category : null,
        search: search.trim() || null,
        is_available: true,
      });
  return { source: 'backend', items: products, total: products.length };
}

/**
 * Fetches a single garment by ID strictly scoped to a boutique storefront slug or shop ID.
 */
export async function fetchGarmentById(id, { shopSlug = null, shopId = null } = {}) {
  if (!id || (!shopSlug && !shopId)) {
    return null;
  }
  const url = shopSlug
    ? `${API_BASE_URL}/shops/slug/${encodeURIComponent(String(shopSlug).trim().toLowerCase())}/products/${id}`
    : `${API_BASE_URL}/products/${id}?shop_id=${encodeURIComponent(shopId)}`;

  const response = await fetch(url, { headers: { ...getAuthHeaders() } });
  if (!response.ok) {
    return null;
  }
  const product = await response.json();
  return backendToFrontendProduct(product);
}

/* ==========================================================================
   VIRTUAL TRY-ON REST API CLIENT
   ========================================================================== */

/**
 * Initializes a real Virtual Try-On session by uploading the customer photo
 * and target product ID via multipart/form-data.
 * POST /api/tryon
 *
 * @param {Object} params
 * @param {File} params.customerPhoto - Customer photo file object (JPEG, PNG, WebP)
 * @param {number|string} params.productId - Database ID of retail product to try on
 * @returns {Promise<{
 *   session_id: string,
 *   product_id: number,
 *   status: string,
 *   provider: string,
 *   progress_percentage: number,
 *   stage_message: string,
 *   is_simulation: boolean
 * }>}
 */
export async function startTryOnSession({
  customerPhoto,
  productId,
  shopId = null,
  shopSlug = null,
}) {
  if (!customerPhoto) {
    throw new Error('Customer photo is required. Please upload an image file.');
  }

  const numericProductId = parseInt(productId, 10);
  if (!numericProductId || isNaN(numericProductId) || numericProductId < 1) {
    throw new Error('A valid retail product ID is required for virtual try-on.');
  }

  const formData = new FormData();
  formData.append('customer_photo', customerPhoto);
  formData.append('product_id', String(numericProductId));
  if (shopId !== null && shopId !== undefined && Number(shopId) > 0) {
    formData.append('shop_id', String(shopId));
  }
  if (shopSlug && String(shopSlug).trim()) {
    formData.append('shop_slug', String(shopSlug).trim().toLowerCase());
  }

  const response = await fetch(`${API_BASE_URL}/tryon`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
    // Note: Do not set Content-Type header so browser sets multipart/form-data with boundary
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to start virtual try-on session');
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Polls the current status, progress percentage, and stage message of an active session.
 * GET /api/tryon/{sessionId}
 *
 * @param {string} sessionId - UUID session identifier
 * @param {AbortSignal} [signal] - Optional AbortSignal for unmount cleanup
 * @returns {Promise<{
 *   session_id: string,
 *   status: 'pending' | 'processing' | 'completed' | 'failed',
 *   progress_percentage: number,
 *   stage_message: string,
 *   provider: string,
 *   result_image_url: string | null,
 *   error_message: string | null,
 *   is_simulation: boolean
 * }>}
 */
export async function fetchTryOnStatus(sessionId, signal = null) {
  if (!sessionId || typeof sessionId !== 'string') {
    throw new Error('A valid session ID is required to poll try-on status.');
  }

  const response = await fetch(`${API_BASE_URL}/tryon/${encodeURIComponent(sessionId)}`, {
    headers: getAuthHeaders(),
    signal: signal || undefined,
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, `Failed to retrieve status for session '${sessionId}'`);
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Resolves the backend result image URL (e.g. "/api/tryon/{session_id}/result")
 * safely against the configured backend origin so authentication headers are only
 * ever sent to the trusted backend host.
 *
 * @param {string} sessionId
 * @param {string | null} [resultImageUrl=null]
 * @returns {string}
 */
export function resolveTryOnResultUrl(sessionId, resultImageUrl = null) {
  const backendRoot = getBackendRootUrl();
  if (resultImageUrl && typeof resultImageUrl === 'string') {
    const trimmed = resultImageUrl.trim();
    if (trimmed) {
      if (/^https?:\/\//i.test(trimmed)) {
        const targetOrigin = new URL(trimmed).origin;
        const expectedOrigin = new URL(
          backendRoot,
          typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000'
        ).origin;
        if (targetOrigin !== expectedOrigin) {
          throw new Error('Refusing to load result image from untrusted external origin.');
        }
        return trimmed;
      }
      return `${backendRoot}${trimmed.startsWith('/') ? '' : '/'}${trimmed}`;
    }
  }

  if (!sessionId || typeof sessionId !== 'string') {
    throw new Error('A valid session ID is required to retrieve the result image.');
  }

  return `${API_BASE_URL}/tryon/${encodeURIComponent(sessionId)}/result`;
}

/**
 * Retrieves the generated try-on result image as a Blob for secure, local rendering.
 * Reads result_image_url from the backend status/history payload when provided,
 * falling back to GET /api/tryon/{sessionId}/result.
 *
 * @param {string} sessionId - UUID session identifier
 * @param {AbortSignal | { signal?: AbortSignal | null, resultImageUrl?: string | null } | null} [signalOrOptions]
 * @returns {Promise<Blob>}
 */
export async function fetchTryOnResultBlob(sessionId, signalOrOptions = null) {
  let signal = null;
  let resultImageUrl = null;
  if (signalOrOptions && typeof signalOrOptions === 'object') {
    if ('aborted' in signalOrOptions && typeof signalOrOptions.addEventListener === 'function') {
      signal = signalOrOptions;
    } else {
      signal = signalOrOptions.signal || null;
      resultImageUrl = signalOrOptions.resultImageUrl || null;
    }
  }

  const url = resolveTryOnResultUrl(sessionId, resultImageUrl);
  const response = await fetch(url, {
    headers: getAuthHeaders(),
    signal: signal || undefined,
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to retrieve try-on result image');
    throw new Error(errorMsg);
  }

  const contentType = (response.headers.get('content-type') || '').toLowerCase();
  if (contentType && !contentType.startsWith('image/')) {
    throw new Error(`Expected an image response from result URL, received '${contentType}'.`);
  }

  const blob = await response.blob();
  if (!blob || blob.size === 0) {
    throw new Error('Received an empty image payload from the result URL.');
  }

  return blob;
}

/**
 * Returns the resolved backend URL for streaming the try-on result image.
 *
 * @param {string} sessionId - UUID session identifier
 * @param {string | null} [resultImageUrl=null]
 * @returns {string}
 */
export function getTryOnResultUrl(sessionId, resultImageUrl = null) {
  return resolveTryOnResultUrl(sessionId, resultImageUrl);
}

/**
 * Retrieves the session input metadata and download endpoints for manual Colab inference.
 * GET /api/tryon/{sessionId}/inputs
 *
 * @param {string} sessionId - UUID session identifier
 * @returns {Promise<{
 *   session_id: string,
 *   product_id: number,
 *   product_name: string,
 *   category: string,
 *   customer_photo_download_url: string,
 *   garment_image_url: string,
 *   created_at: string
 * }>}
 */
export async function fetchTryOnInputs(sessionId) {
  if (!sessionId || typeof sessionId !== 'string') {
    throw new Error('A valid session ID is required to retrieve session inputs.');
  }

  const response = await fetch(`${API_BASE_URL}/tryon/${encodeURIComponent(sessionId)}/inputs`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to retrieve try-on session inputs');
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Returns the direct URL for downloading the private customer photo for an active session.
 *
 * @param {string} sessionId - UUID session identifier
 * @returns {string}
 */
export function getCustomerPhotoDownloadUrl(sessionId) {
  return `${API_BASE_URL}/tryon/${encodeURIComponent(sessionId)}/customer-photo`;
}

/**
 * Imports a FASHN VTON result image generated in Colab into the active try-on session.
 * POST /api/tryon/{sessionId}/import-result
 *
 * @param {{ sessionId: string, resultFile: File | Blob, allowOverwrite?: boolean }} params
 */
export async function importTryOnResult({ sessionId, resultFile, allowOverwrite = false }) {
  if (!sessionId || typeof sessionId !== 'string') {
    throw new Error('A valid session ID is required to import the result.');
  }
  if (!resultFile) {
    throw new Error('A valid image file is required to import the try-on result.');
  }

  const formData = new FormData();
  formData.append('result_image', resultFile);

  const url = `${API_BASE_URL}/tryon/${encodeURIComponent(sessionId)}/import-result?allow_overwrite=${allowOverwrite}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to import try-on result image');
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Retrieves the authenticated user's try-on session history.
 * GET /api/tryon/history/me
 *
 * @param {number} [limit=50]
 * @returns {Promise<Array>}
 */
export async function fetchTryOnHistory(limit = 50) {
  const response = await fetch(`${API_BASE_URL}/tryon/history/me?limit=${limit}`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to retrieve try-on history');
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Permanently deletes a try-on session and its private images on demand.
 * DELETE /api/tryon/{sessionId}
 *
 * @param {string} sessionId
 * @returns {Promise<{ status: string, message: string }>}
 */
export async function deleteTryOnSession(sessionId) {
  if (!sessionId) {
    throw new Error('A valid session ID is required for deletion.');
  }

  const response = await fetch(`${API_BASE_URL}/tryon/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    const errorMsg = await parseErrorMessage(response, 'Failed to delete try-on session');
    throw new Error(errorMsg);
  }

  return await response.json();
}


/**
 * Fetch a single registered boutique shop by numeric ID.
 */
export async function fetchShopById(shopId) {
  if (!shopId) {
    throw new Error('Shop ID is required.');
  }
  const response = await fetch(`${API_BASE_URL}/shops/${shopId}`, {
    headers: {
      ...getAuthHeaders(),
    },
  });
  if (!response.ok) {
    const msg = await parseErrorMessage(response, 'Failed to load boutique details');
    throw new Error(msg);
  }
  return await response.json();
}


/**
 * Fetch a registered boutique storefront by its unique public slug.
 */
export async function fetchShopBySlug(shopSlug) {
  const cleanSlug = String(shopSlug || '').trim().toLowerCase();
  if (!cleanSlug) {
    throw new Error('Storefront slug is required.');
  }
  const response = await fetch(`${API_BASE_URL}/shops/slug/${encodeURIComponent(cleanSlug)}`, {
    headers: {
      ...getAuthHeaders(),
    },
  });
  if (!response.ok) {
    const msg = await parseErrorMessage(response, `Storefront '${cleanSlug}' not found`);
    const err = new Error(msg);
    err.status = response.status;
    throw err;
  }
  return await response.json();
}


/**
 * Fetch strictly published garments belonging to one isolated shop storefront slug.
 */
export async function fetchStorefrontProducts(
  shopSlug,
  { category = '', search = '', skip = 0, limit = 100 } = {}
) {
  const cleanSlug = String(shopSlug || '').trim().toLowerCase();
  if (!cleanSlug) {
    throw new Error('Storefront slug is required to load boutique products.');
  }
  const params = new URLSearchParams();
  if (category && category !== 'All') params.append('category', category);
  if (search) params.append('search', search);
  params.append('skip', String(skip));
  params.append('limit', String(limit));

  const response = await fetch(
    `${API_BASE_URL}/shops/slug/${encodeURIComponent(cleanSlug)}/products?${params.toString()}`,
    {
      headers: {
        ...getAuthHeaders(),
      },
    }
  );
  if (!response.ok) {
    const msg = await parseErrorMessage(response, 'Failed to fetch storefront products');
    const err = new Error(msg);
    err.status = response.status;
    throw err;
  }
  const items = await response.json();
  return Array.isArray(items) ? items.map(backendToFrontendProduct) : [];
}


/**
 * Fetch private + published inventory owned strictly by the authenticated shop owner.
 */
export async function fetchMyProducts({
  category = '',
  search = '',
  is_available = undefined,
  skip = 0,
  limit = 100,
} = {}) {
  const params = new URLSearchParams();
  if (category && category !== 'All') params.append('category', category);
  if (search) params.append('search', search);
  if (typeof is_available === 'boolean') params.append('is_available', String(is_available));
  params.append('skip', String(skip));
  params.append('limit', String(limit));

  const response = await fetch(`${API_BASE_URL}/products/my?${params.toString()}`, {
    headers: {
      ...getAuthHeaders(),
    },
  });
  if (!response.ok) {
    const msg = await parseErrorMessage(response, 'Failed to load your shop inventory');
    const err = new Error(msg);
    err.status = response.status;
    throw err;
  }
  const items = await response.json();
  return Array.isArray(items) ? items.map(backendToFrontendProduct) : [];
}



/**
 * Legacy Try-On submission adapter (preserved for backward compatibility).
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
