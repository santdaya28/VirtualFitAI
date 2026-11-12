import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  Sparkles,
  Store,
  ArrowLeftRight,
  Upload,
  Camera,
  CheckCircle,
  AlertCircle,
  X,
  RefreshCw,
  Shirt,
  ArrowRight,
  Image as ImageIcon,
  Download,
  AlertTriangle,
  RotateCcw,
  History,
  Trash2,
  Clock,
  ShieldAlert,
} from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';
import AuthModal from '../components/AuthModal';
import ShopSelector from '../components/ShopSelector';
import { useAuth } from '../context/AuthContext';
import {
  fetchShopBySlug,
  fetchStorefrontProducts,
  startTryOnSession,
  fetchTryOnStatus,
  fetchTryOnResultBlob,
  fetchTryOnHistory,
  deleteTryOnSession,
} from '../services/api';

const ALLOWED_MIME_TYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/webp',
];

const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

/**
 * Format price to ensure Indian Rupee (₹) symbol and proper formatting
 */
function formatRupeePrice(price) {
  if (!price && price !== 0) return '₹0';
  if (typeof price === 'string') {
    if (price.startsWith('₹')) return price;
    if (price.startsWith('$')) {
      const num = parseFloat(price.replace('$', ''));
      return isNaN(num) ? `₹${price.slice(1)}` : `₹${Math.round(num * 25).toLocaleString('en-IN')}`;
    }
    return `₹${price}`;
  }
  return `₹${Number(price).toLocaleString('en-IN')}`;
}

/**
 * Formats retry wait seconds into a compact human-readable countdown label.
 */
function formatCooldown(seconds) {
  const total = Math.max(0, Math.ceil(Number(seconds) || 0));
  if (total < 60) return `${total}s`;
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function isMockSession(data) {
  return Boolean(
    data?.isSimulation ||
      data?.is_simulation ||
      data?.provider === 'mock' ||
      data?.provenance === 'mock_simulation'
  );
}

function isManualImportSession(data) {
  return Boolean(
    data?.provenance === 'manual_import' || data?.provider === 'fashn_manual'
  );
}

function isGenuineInferenceSession(data) {
  return (
    !isMockSession(data) &&
    !isManualImportSession(data) &&
    Boolean(
      data?.provenance === 'genuine_zerogpu' ||
        data?.provenance === 'genuine_inference' ||
        data?.provider === 'zerogpu' ||
        data?.provider === 'fashn'
    )
  );
}

function mapStatusResponseToSessionData(resp, prev = {}) {
  const mock = isMockSession(resp);
  return {
    sessionId: resp.session_id || prev.sessionId || null,
    productId: resp.product_id ?? prev.productId ?? null,
    status: resp.status || prev.status || 'pending',
    progress: resp.progress_percentage ?? prev.progress ?? 0,
    stageMessage: resp.stage_message || resp.message || prev.stageMessage || '',
    provider: resp.provider || prev.provider || 'fashn',
    provenance:
      resp.provenance ||
      prev.provenance ||
      (mock ? 'mock_simulation' : 'genuine_inference'),
    isSimulation: mock,
    errorMessage: resp.error_message || null,
    errorCategory: resp.error_category || null,
    retryAfterSeconds: resp.retry_after_seconds ?? null,
    quotaResetsAt: resp.quota_resets_at || null,
    resultImageUrl: resp.result_image_url || null,
  };
}

/**
 * Categorizes backend error metadata and messages into safe, customer-friendly guidance
 * without exposing raw stack traces, internal URLs, or inaccurate fixed reset schedules.
 */
function categorizeError(errorInput) {
  const payload =
    typeof errorInput === 'object' && errorInput !== null
      ? errorInput
      : { errorCategory: null, errorMessage: errorInput, quotaResetsAt: null };

  const category = payload.errorCategory ? String(payload.errorCategory).toLowerCase() : null;
  const rawError = payload.errorMessage ? String(payload.errorMessage) : '';
  const quotaResetsAt = payload.quotaResetsAt || null;

  if (category === 'quota_exhausted') {
    const resetDetail = quotaResetsAt
      ? ` Estimated reset time: ${quotaResetsAt}.`
      : '';
    return {
      title: 'AI Compute Quota Temporarily Exhausted',
      description: `Free-tier Hugging Face ZeroGPU compute quota is currently exhausted.${resetDetail}`,
      hint: 'ZeroGPU enforces a rolling 24-hour usage window based on recent compute activity (not fixed to 00:00 UTC). Please wait for quota to replenish before retrying.',
    };
  }

  if (category === 'space_sleeping') {
    return {
      title: 'AI Fitting Service Starting Up',
      description: 'The AI fitting Space on Hugging Face is waking up or restarting from idle state.',
      hint: 'Cold startup typically takes 30–60 seconds. Wait for the retry timer and click Retry AI Fitting.',
    };
  }

  if (category === 'worker_overload') {
    return {
      title: 'AI Queue Temporarily Busy',
      description: 'The shared ZeroGPU inference queue is currently busy handling other requests.',
      hint: 'Please wait briefly for the queue to clear and retry.',
    };
  }

  if (category === 'upload_failed') {
    return {
      title: 'Image Upload Staging Failed',
      description: 'Your photo or garment reference image could not be transferred cleanly to the AI worker.',
      hint: 'Ensure your photo is a clear JPG, PNG, or WebP file under 10 MB, then try again.',
    };
  }

  if (category === 'invalid_inputs') {
    return {
      title: 'Unsupported Input Photo or Garment',
      description: 'The uploaded customer photo or selected garment category could not be processed.',
      hint: 'Upload a clear front-facing JPG, PNG, or WebP portrait and select a supported top, bottom, or one-piece garment.',
    };
  }

  if (category === 'network_timeout') {
    return {
      title: 'Connection Timed Out',
      description: 'The request timed out or the connection to the AI worker was interrupted.',
      hint: 'Wait a few seconds and click Retry AI Fitting.',
    };
  }

  if (category === 'worker_unavailable') {
    return {
      title: 'AI Generation Unavailable',
      description: 'The AI inference worker is temporarily unreachable or not connected.',
      hint: 'Please try again shortly once the AI worker service is available.',
    };
  }

  if (category === 'session_access_error') {
    return {
      title: 'Session Access Unavailable',
      description: rawError || 'Unable to access this try-on session.',
      hint: 'Private try-on sessions require signing in as the account that created the session.',
    };
  }

  if (category === 'inference_exception') {
    return {
      title: 'AI Processing Error',
      description: 'The AI model encountered an unexpected processing error or aborted image synthesis.',
      hint: 'Please wait a moment and try again, or try a different clear front-facing photo.',
    };
  }

  if (!rawError) {
    return {
      title: 'Inference Failure',
      description: 'An unexpected error occurred during virtual try-on generation.',
      hint: 'Please try again shortly or choose another garment.',
    };
  }

  const lower = rawError.toLowerCase();

  if (lower.includes('already in progress')) {
    return {
      title: 'Generation Already in Progress',
      description: 'An AI fitting for this garment is already running for your account.',
      hint: 'Please wait for the active fitting session to complete before starting another.',
    };
  }

  if (
    lower.includes('quota') ||
    lower.includes('429') ||
    lower.includes('rate limit')
  ) {
    return {
      title: 'AI Compute Quota Temporarily Exhausted',
      description: 'The free-tier Hugging Face ZeroGPU compute quota is currently exhausted.',
      hint: 'ZeroGPU uses a rolling 24-hour usage window (not fixed to 00:00 UTC). Please try again later once quota replenishes.',
    };
  }

  if (
    lower.includes('sleeping') ||
    lower.includes('waking up') ||
    lower.includes('cold boot')
  ) {
    return {
      title: 'AI Fitting Service Starting Up',
      description: 'The AI fitting Space on Hugging Face is waking up from sleep.',
      hint: 'Wait ~30–60 seconds for startup to finish, then click Retry AI Fitting.',
    };
  }

  if (
    lower.includes('overloaded') ||
    lower.includes('queue is full') ||
    lower.includes('temporarily busy')
  ) {
    return {
      title: 'AI Queue Temporarily Busy',
      description: 'The AI inference queue is experiencing high traffic right now.',
      hint: 'Please wait a moment and retry.',
    };
  }

  if (
    lower.includes('timeout') ||
    lower.includes('timed out') ||
    lower.includes('interrupted')
  ) {
    return {
      title: 'Connection Timed Out',
      description: 'The connection to the AI fitting service timed out before finishing.',
      hint: 'Please retry once the countdown finishes.',
    };
  }

  if (
    lower.includes('no inference worker is connected') ||
    lower.includes('temporarily unavailable') ||
    lower.includes('no zerogpu inference worker is connected') ||
    lower.includes('no inference worker') ||
    lower.includes('503')
  ) {
    return {
      title: 'AI Generation Unavailable',
      description: 'AI generation is temporarily unavailable because no inference worker is reachable.',
      hint: 'Please try again shortly once an authorized GPU worker is connected.',
    };
  }

  if (
    lower.includes('unambiguously resolve') ||
    lower.includes('expected tops, bottoms, or one-pieces') ||
    lower.includes('unsupported garment category')
  ) {
    return {
      title: 'Unsupported Garment Category',
      description: 'The selected garment category is not supported for AI virtual try-on.',
      hint: 'Supported categories are single garments: Tops (shirts, t-shirts, jackets), Bottoms (trousers, jeans, skirts), and One-Pieces (dresses, jumpsuits).',
    };
  }

  if (
    lower.includes('magic byte') ||
    lower.includes('unsupported or invalid image format') ||
    lower.includes('too small to be a valid image') ||
    lower.includes('failed to read uploaded photo')
  ) {
    return {
      title: 'Invalid Customer Photo',
      description: 'The uploaded file could not be read as a valid JPEG, PNG, or WebP photo.',
      hint: 'Please upload a clear portrait photo in JPG, PNG, or WebP format under 10 MB.',
    };
  }

  if (
    lower.includes('network') ||
    lower.includes('failed to fetch') ||
    lower.includes('connection refused') ||
    lower.includes('connection lost')
  ) {
    return {
      title: 'Network Connection Error',
      description: 'Unable to communicate with the VirtualFit AI service.',
      hint: 'Check your network connection and click Retry AI Fitting.',
    };
  }

  return {
    title: 'Virtual Try-On Failed',
    description: 'The AI fitting request could not be completed at this time.',
    hint: 'Please wait briefly and try again, or test with a different garment or portrait photo.',
  };
}

export default function TryOnPage() {
  const { shopSlug: routeShopSlug } = useParams();
  const [searchParams] = useSearchParams();
  const [sessionResolvedSlug, setSessionResolvedSlug] = useState('');
  const querySessionId = searchParams.get('session');
  const activeShopSlug = (
    routeShopSlug ||
    searchParams.get('shop') ||
    sessionResolvedSlug ||
    ''
  ).trim().toLowerCase();

  const fileInputRef = useRef(null);
  const dragCounter = useRef(0);
  const isSubmittingRef = useRef(false);

  // Storefront Isolation States
  const [activeShop, setActiveShop] = useState(null);
  const [shopNotFound, setShopNotFound] = useState(false);
  const [garmentMismatchError, setGarmentMismatchError] = useState('');

  // Photo & Canvas States
  const [customerPhoto, setCustomerPhoto] = useState(null); // { file, previewUrl, name, size }
  const [errorMessage, setErrorMessage] = useState('');
  const [validationError, setValidationError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [cameraNotice, setCameraNotice] = useState(false);
  const [imageErrors, setImageErrors] = useState({});

  // Backend Products & Selection States
  const [garments, setGarments] = useState([]);
  const [loadingGarments, setLoadingGarments] = useState(true);
  const [garmentsError, setGarmentsError] = useState(null);
  const [selectedGarment, setSelectedGarment] = useState(null);
  const [selectedColor, setSelectedColor] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');

  const { isAuthenticated } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyItems, setHistoryItems] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [deletingSessionId, setDeletingSessionId] = useState(null);
  const [sessionToDelete, setSessionToDelete] = useState(null); // { id, garmentName }
  const [deleteError, setDeleteError] = useState(null);

  // Real Try-On Pipeline States
  // tryOnState: 'idle' | 'submitting' | 'polling' | 'completed' | 'failed'
  const [tryOnState, setTryOnState] = useState('idle');
  const [sessionData, setSessionData] = useState({
    sessionId: null,
    productId: null,
    status: 'pending',
    progress: 0,
    stageMessage: '',
    provider: 'fashn',
    provenance: 'mock_simulation',
    isSimulation: false,
    errorMessage: null,
    errorCategory: null,
    retryAfterSeconds: null,
    quotaResetsAt: null,
    resultImageUrl: null,
  });
  const [retryCooldown, setRetryCooldown] = useState(0);
  const [resultBlobUrl, setResultBlobUrl] = useState(null);
  const [loadingResultImage, setLoadingResultImage] = useState(false);
  const [resultFetchError, setResultFetchError] = useState(null);
  const [viewMode, setViewMode] = useState('result'); // 'result' | 'split' | 'original'

  const applyLoadedResultBlob = useCallback((blob) => {
    const objectUrl = URL.createObjectURL(blob);
    setResultBlobUrl(objectUrl);
    setResultFetchError(null);
  }, []);

  const handleResultImageRenderError = useCallback(() => {
    setResultBlobUrl(null);
    setResultFetchError('The generated result image could not be decoded or displayed by the browser.');
  }, []);

  // Live retry countdown timer
  useEffect(() => {
    if (retryCooldown <= 0) return undefined;
    const timer = setTimeout(() => {
      setRetryCooldown((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => clearTimeout(timer);
  }, [retryCooldown]);

  const categories = ['All', 'Formal', 'Casual', 'Ethnic', 'Outerwear'];

  // Fetch published garments strictly belonging to the active storefront slug
  const loadGarments = useCallback(async () => {
    setSelectedGarment(null);
    setSelectedColor('');
    setActiveCategory('All');
    setGarmentMismatchError('');

    if (!activeShopSlug) {
      setActiveShop(null);
      setShopNotFound(false);
      setGarments([]);
      setGarmentsError(null);
      setLoadingGarments(false);
      return;
    }

    setLoadingGarments(true);
    setGarmentsError(null);
    setShopNotFound(false);
    try {
      const [shopInfo, data] = await Promise.all([
        fetchShopBySlug(activeShopSlug),
        fetchStorefrontProducts(activeShopSlug, { limit: 100 }),
      ]);
      setActiveShop(shopInfo);
      const activeGarments = Array.isArray(data)
        ? data.filter((g) => g.is_available !== false)
        : [];
      setGarments(activeGarments);
    } catch (err) {
      console.error('Failed to load storefront garments for Try-On:', err);
      setActiveShop(null);
      setGarments([]);
      if (err.status === 404) {
        setShopNotFound(true);
      }
      setGarmentsError(
        err.message || 'Unable to load garments for this storefront.'
      );
    } finally {
      setLoadingGarments(false);
    }
  }, [activeShopSlug]);

  useEffect(() => {
    loadGarments();
  }, [loadGarments]);

  // Synchronize garment selection with URL query parameter (?garment=ID)
  // or product_id restored from an existing session (?session=UUID).
  const queryGarmentId = searchParams.get('garment');
  const targetGarmentId = queryGarmentId || sessionData.productId;
  useEffect(() => {
    if (!targetGarmentId || loadingGarments || !activeShop) return;

    const matched = garments.find((g) => String(g.id) === String(targetGarmentId));
    if (matched) {
      setSelectedGarment(matched);
      setSelectedColor(
        Array.isArray(matched.colors) && matched.colors.length > 0 ? matched.colors[0] : ''
      );
      setActiveCategory('All');
      setGarmentMismatchError('');
    } else if (queryGarmentId) {
      setSelectedGarment(null);
      setGarmentMismatchError(
        `Garment #${queryGarmentId} does not belong to ${activeShop.shop_name}'s storefront or is unpublished.`
      );
    }
  }, [targetGarmentId, queryGarmentId, garments, loadingGarments, activeShop]);

  // Restore an existing try-on session (?session=UUID) without triggering new AI inference
  useEffect(() => {
    if (!querySessionId) return;

    let isMounted = true;
    const abortController = new AbortController();

    const restoreSession = async () => {
      try {
        const statusResp = await fetchTryOnStatus(querySessionId, abortController.signal);
        if (!isMounted || abortController.signal.aborted) return;

        if (statusResp.shop_slug && !routeShopSlug) {
          setSessionResolvedSlug(statusResp.shop_slug);
        }
        setSessionData(mapStatusResponseToSessionData(statusResp));
        setViewMode('result');
        setResultFetchError(null);
        setResultBlobUrl(null);

        if (statusResp.status === 'completed') {
          if (!isMockSession(statusResp)) {
            if (!statusResp.result_image_url) {
              setResultFetchError('Backend completed inference, but no result image URL was provided.');
            } else {
              setLoadingResultImage(true);
              try {
                const blob = await fetchTryOnResultBlob(statusResp.session_id, {
                  signal: abortController.signal,
                  resultImageUrl: statusResp.result_image_url,
                });
                if (!isMounted || abortController.signal.aborted) return;
                applyLoadedResultBlob(blob);
              } catch (blobErr) {
                if (!isMounted || abortController.signal.aborted) return;
                console.error('Failed to load existing session result image:', blobErr);
                setResultFetchError(blobErr.message || 'Failed to load generated result image.');
              } finally {
                if (isMounted && !abortController.signal.aborted) {
                  setLoadingResultImage(false);
                }
              }
            }
          }
          if (isMounted && !abortController.signal.aborted) {
            setTryOnState('completed');
          }
          return;
        }

        if (statusResp.status === 'failed') {
          setTryOnState('failed');
          return;
        }

        // Still pending or processing -> resume polling without creating a new job
        setTryOnState('polling');
      } catch (err) {
        if (!isMounted || abortController.signal.aborted) return;
        console.error('Failed to restore existing try-on session:', err);
        setLoadingResultImage(false);
        setResultBlobUrl(null);
        setSessionData((prev) => ({
          ...prev,
          sessionId: querySessionId,
          status: 'failed',
          errorCategory: 'session_access_error',
          errorMessage: err.message || 'Failed to load the requested try-on session.',
          stageMessage: 'Unable to open try-on session.',
        }));
        setTryOnState('failed');
      }
    };

    restoreSession();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [querySessionId, routeShopSlug, isAuthenticated, applyLoadedResultBlob]);

  // Cleanup customer photo object URL on unmount or file change
  useEffect(() => {
    return () => {
      if (customerPhoto?.previewUrl) {
        URL.revokeObjectURL(customerPhoto.previewUrl);
      }
    };
  }, [customerPhoto]);

  // Cleanup result blob object URL on unmount or when replaced
  useEffect(() => {
    return () => {
      if (resultBlobUrl) {
        URL.revokeObjectURL(resultBlobUrl);
      }
    };
  }, [resultBlobUrl]);

  // =========================================================================
  // STATUS POLLING EFFECT (Cleaned up on unmount, handles errors gracefully)
  // =========================================================================
  useEffect(() => {
    if (tryOnState !== 'polling' || !sessionData.sessionId) {
      return;
    }

    let isMounted = true;
    const abortController = new AbortController();
    let pollTimerId = null;
    let networkFailuresCount = 0;

    const pollStatus = async () => {
      try {
        const statusResp = await fetchTryOnStatus(sessionData.sessionId, abortController.signal);
        if (!isMounted) return;

        networkFailuresCount = 0;

        // Display the actual backend progress and stage_message (never invent numbers)
        setSessionData((prev) => mapStatusResponseToSessionData(statusResp, prev));

        // 1. Session Completed
        if (statusResp.status === 'completed') {
          if (!isMockSession(statusResp)) {
            if (!statusResp.result_image_url) {
              setResultFetchError('Backend completed inference, but no result image URL was provided.');
              if (isMounted) {
                setLoadingResultImage(false);
                setRetryCooldown(0);
                setTryOnState('completed');
              }
              return;
            }

            // Retrieve the result blob BEFORE transitioning tryOnState out of 'polling':
            // changing tryOnState runs this effect's cleanup and aborts abortController.
            setLoadingResultImage(true);
            try {
              const blob = await fetchTryOnResultBlob(sessionData.sessionId, {
                signal: abortController.signal,
                resultImageUrl: statusResp.result_image_url,
              });
              if (!isMounted || abortController.signal.aborted) return;
              applyLoadedResultBlob(blob);
            } catch (blobErr) {
              if (!isMounted || abortController.signal.aborted) return;
              console.error('Failed to retrieve result image blob:', blobErr);
              setResultFetchError(blobErr.message || 'Failed to download generated result image.');
            } finally {
              if (isMounted && !abortController.signal.aborted) {
                setLoadingResultImage(false);
                setRetryCooldown(0);
                setTryOnState('completed');
              }
            }
          } else if (isMounted) {
            setResultFetchError(null);
            setLoadingResultImage(false);
            setRetryCooldown(0);
            setTryOnState('completed');
          }
          return; // Stop polling
        }

        // 2. Session Failed
        if (statusResp.status === 'failed') {
          setTryOnState('failed');
          const serverWait = Number(statusResp.retry_after_seconds);
          if (Number.isFinite(serverWait) && serverWait > 0) {
            setRetryCooldown(serverWait);
          } else if (
            statusResp.error_category &&
            statusResp.error_category !== 'invalid_inputs' &&
            statusResp.error_category !== 'upload_failed'
          ) {
            setRetryCooldown(15);
          } else if (!statusResp.error_category) {
            setRetryCooldown(10);
          }
          return; // Stop polling
        }

        // 3. Session Still In Progress (pending or processing)
        pollTimerId = setTimeout(pollStatus, 1500);

      } catch (err) {
        if (!isMounted || abortController.signal.aborted) return;

        networkFailuresCount += 1;
        console.warn(`[Polling] Attempt failed (${networkFailuresCount}/5):`, err.message);

        if (networkFailuresCount >= 5) {
          setTryOnState('failed');
          setRetryCooldown(15);
          setSessionData((prev) => ({
            ...prev,
            status: 'failed',
            errorCategory: 'network_timeout',
            errorMessage: 'Connection lost while polling try-on status. Please try again.',
            stageMessage: 'Network polling failed.',
          }));
          return;
        }

        // Retry with backoff
        pollTimerId = setTimeout(pollStatus, 2500);
      }
    };

    // Trigger initial poll after 800ms
    pollTimerId = setTimeout(pollStatus, 800);

    return () => {
      isMounted = false;
      abortController.abort();
      if (pollTimerId) clearTimeout(pollTimerId);
    };
  }, [tryOnState, sessionData.sessionId, applyLoadedResultBlob]);

  // Handle File Validation and Local Preview
  const processFile = (file) => {
    setErrorMessage('');
    setValidationError('');

    if (!file) return;

    const fileName = file.name || '';
    const lastDotIndex = fileName.lastIndexOf('.');
    const fileExtension = lastDotIndex !== -1 ? fileName.substring(lastDotIndex).toLowerCase() : '';
    const fileMime = (file.type || '').toLowerCase();

    const isValidType =
      ALLOWED_MIME_TYPES.includes(fileMime) ||
      ALLOWED_EXTENSIONS.includes(fileExtension);

    if (!isValidType) {
      setErrorMessage(
        `Invalid file type (${fileExtension || file.type || 'unknown'}). Please upload a JPG, JPEG, PNG, or WebP photo.`
      );
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      const sizeInMB = (file.size / (1024 * 1024)).toFixed(1);
      setErrorMessage(
        `File size (${sizeInMB} MB) exceeds the 10 MB limit. Please upload a smaller photo.`
      );
      return;
    }

    if (file.size === 0) {
      setErrorMessage('The selected file appears to be empty. Please choose a valid image.');
      return;
    }

    // Revoke previous URL to prevent memory leaks
    if (customerPhoto?.previewUrl) {
      URL.revokeObjectURL(customerPhoto.previewUrl);
    }

    // Create local preview object URL
    const previewUrl = URL.createObjectURL(file);
    const sizeFormatted =
      file.size >= 1024 * 1024
        ? `${(file.size / (1024 * 1024)).toFixed(2)} MB`
        : `${Math.round(file.size / 1024)} KB`;

    setCustomerPhoto({
      file,
      previewUrl,
      name: file.name,
      size: sizeFormatted,
    });

    // Reset previous generation results if any
    if (tryOnState === 'completed' || tryOnState === 'failed') {
      setTryOnState('idle');
      if (resultBlobUrl) {
        URL.revokeObjectURL(resultBlobUrl);
        setResultBlobUrl(null);
      }
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      processFile(file);
    }
    e.target.value = '';
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (e.dataTransfer?.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      processFile(file);
    }
  };

  const handleRemovePhoto = () => {
    if (customerPhoto?.previewUrl) {
      URL.revokeObjectURL(customerPhoto.previewUrl);
    }
    setCustomerPhoto(null);
    setErrorMessage('');
    setValidationError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (tryOnState === 'completed' || tryOnState === 'failed') {
      setTryOnState('idle');
      if (
        sessionData.errorCategory === 'invalid_inputs' ||
        sessionData.errorCategory === 'upload_failed'
      ) {
        setRetryCooldown(0);
      }
      if (resultBlobUrl) {
        URL.revokeObjectURL(resultBlobUrl);
        setResultBlobUrl(null);
      }
    }
  };

  const handleThumbnailError = (id) => {
    setImageErrors((prev) => ({ ...prev, [id]: true }));
  };

  const handleGarmentToggle = (garment) => {
    setValidationError('');
    const isDeselecting = String(selectedGarment?.id) === String(garment.id);
    setSelectedGarment(isDeselecting ? null : garment);
    setSelectedColor(
      isDeselecting
        ? ''
        : Array.isArray(garment.colors) && garment.colors.length > 0
        ? garment.colors[0]
        : ''
    );
    if (tryOnState === 'completed' || tryOnState === 'failed') {
      setTryOnState('idle');
      if (
        sessionData.errorCategory === 'invalid_inputs' ||
        sessionData.errorCategory === 'upload_failed'
      ) {
        setRetryCooldown(0);
      }
      if (resultBlobUrl) {
        URL.revokeObjectURL(resultBlobUrl);
        setResultBlobUrl(null);
      }
    }
  };

  // =========================================================================
  // SUBMIT TRY-ON REQUEST
  // =========================================================================
  const handleStartTryOn = async () => {
    if (isSubmittingRef.current || retryCooldown > 0) {
      return;
    }

    setValidationError('');
    setErrorMessage('');

    // Input validation
    if (!customerPhoto?.file) {
      setValidationError('Please upload a customer photo in Step 1 before generating.');
      return;
    }

    if (!selectedGarment?.id) {
      setValidationError('Please select a catalogue garment in Step 2 before generating.');
      return;
    }

    // Synchronous duplicate-submission lock before async state transition
    isSubmittingRef.current = true;

    // Clean up previous result
    if (resultBlobUrl) {
      URL.revokeObjectURL(resultBlobUrl);
      setResultBlobUrl(null);
    }
    setLoadingResultImage(false);
    setResultFetchError(null);
    setViewMode('result');

    setTryOnState('submitting');
    setSessionData({
      sessionId: null,
      productId: selectedGarment.id,
      status: 'pending',
      progress: 5,
      stageMessage: 'Preparing your fitting...',
      provider: 'fashn',
      provenance: 'mock_simulation',
      isSimulation: false,
      errorMessage: null,
      errorCategory: null,
      retryAfterSeconds: null,
      quotaResetsAt: null,
      resultImageUrl: null,
    });

    try {
      const resp = await startTryOnSession({
        customerPhoto: customerPhoto.file,
        productId: selectedGarment.id,
        shopId: activeShop?.id || null,
        shopSlug: activeShop?.slug || activeShopSlug || null,
      });

      setSessionData(mapStatusResponseToSessionData({
        ...resp,
        product_id: resp.product_id ?? selectedGarment.id,
      }));

      // Advance to active polling
      setTryOnState('polling');

    } catch (err) {
      console.error('Failed to start try-on:', err);
      const rawMsg = err?.message || 'Failed to submit try-on request.';
      const lowerMsg = rawMsg.toLowerCase();
      let cooldown = 10;
      if (lowerMsg.includes('quota') || lowerMsg.includes('429')) {
        cooldown = 300;
      } else if (lowerMsg.includes('sleeping') || lowerMsg.includes('503') || lowerMsg.includes('unavailable')) {
        cooldown = 30;
      } else if (lowerMsg.includes('overload') || lowerMsg.includes('busy')) {
        cooldown = 45;
      } else if (lowerMsg.includes('magic byte') || lowerMsg.includes('format') || lowerMsg.includes('unsupported garment')) {
        cooldown = 0;
      }
      setRetryCooldown(cooldown);
      setTryOnState('failed');
      setSessionData((prev) => ({
        ...prev,
        status: 'failed',
        errorMessage: rawMsg,
        errorCategory: null,
        retryAfterSeconds: cooldown || null,
        quotaResetsAt: null,
        stageMessage: 'Submission could not start.',
      }));
    } finally {
      isSubmittingRef.current = false;
    }
  };

  const handleRetryLoadResult = async () => {
    if (!sessionData.sessionId || isMockSession(sessionData)) return;
    setLoadingResultImage(true);
    setResultFetchError(null);
    try {
      const blob = await fetchTryOnResultBlob(sessionData.sessionId, {
        resultImageUrl: sessionData.resultImageUrl,
      });
      applyLoadedResultBlob(blob);
    } catch (err) {
      console.error('Failed to reload result image:', err);
      setResultFetchError(err.message || 'Failed to download generated result image.');
    } finally {
      setLoadingResultImage(false);
    }
  };

  const handleCancelTryOn = () => {
    setTryOnState('idle');
    setLoadingResultImage(false);
    setResultFetchError(null);
    setSessionData({
      sessionId: null,
      productId: null,
      status: 'pending',
      progress: 0,
      stageMessage: '',
      provider: 'fashn',
      provenance: 'mock_simulation',
      isSimulation: false,
      errorMessage: null,
      errorCategory: null,
      retryAfterSeconds: null,
      quotaResetsAt: null,
      resultImageUrl: null,
    });
    if (resultBlobUrl) {
      URL.revokeObjectURL(resultBlobUrl);
      setResultBlobUrl(null);
    }
  };

  const handleDownloadResult = () => {
    if (!resultBlobUrl) return;
    const a = document.createElement('a');
    a.href = resultBlobUrl;
    a.download = `virtualfit_tryon_${sessionData.sessionId || 'result'}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleResetAll = () => {
    handleRemovePhoto();
    setSelectedGarment(null);
    setSelectedColor('');
    handleCancelTryOn();
  };

  const loadHistory = async () => {
    if (!isAuthenticated) return;
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const items = await fetchTryOnHistory();
      setHistoryItems(items);
    } catch (err) {
      setHistoryError(err.message || 'Failed to load try-on history.');
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleDeleteSession = (sessionId, garmentName = 'Garment Try-On') => {
    setDeleteError(null);
    setSessionToDelete({ id: sessionId, garmentName });
  };

  const confirmDeleteSession = async () => {
    if (!sessionToDelete?.id) return;
    const targetId = sessionToDelete.id;
    setDeletingSessionId(targetId);
    setDeleteError(null);
    try {
      await deleteTryOnSession(targetId);
      setHistoryItems((prev) => prev.filter((item) => item.session_id !== targetId));
      if (sessionData.sessionId === targetId) {
        handleResetAll();
      }
      setSessionToDelete(null);
    } catch (err) {
      setDeleteError(err.message || 'Failed to delete try-on session.');
    } finally {
      setDeletingSessionId(null);
    }
  };


  const filteredGarments =
    activeCategory === 'All'
      ? garments
      : garments.filter((g) => g.category === activeCategory);

  const canGenerate = Boolean(
    customerPhoto?.file &&
    selectedGarment?.id &&
    tryOnState !== 'submitting' &&
    tryOnState !== 'polling' &&
    retryCooldown <= 0
  );

  const categorizedError = tryOnState === 'failed' ? categorizeError(sessionData) : null;
  const isMockResult = isMockSession(sessionData);
  const isManualImport = isManualImportSession(sessionData);
  const isGenuineInference = isGenuineInferenceSession(sessionData);
  const hasDisplayableResult = Boolean(resultBlobUrl) && !resultFetchError;

  // Dynamic Viewport Status Calculation
  const getDynamicStatus = () => {
    if (tryOnState === 'submitting' || tryOnState === 'polling') {
      return {
        key: 'processing',
        label: isMockResult ? 'Simulating Try-On' : 'Synthesizing (FASHN AI)',
        badgeColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
        dotColor: 'bg-indigo-600',
        headline: isMockResult ? 'Running Try-On Simulation...' : 'Synthesizing AI Virtual Fitting...',
        description: sessionData.stageMessage || 'Processing neural diffusion models...',
      };
    }
    if (tryOnState === 'completed') {
      if (isMockResult) {
        return {
          key: 'completed',
          label: 'Simulation Completed',
          badgeColor: 'bg-slate-100 text-slate-700 border-slate-300',
          dotColor: 'bg-slate-500',
          headline: 'Simulation Completed',
          description:
            sessionData.stageMessage ||
            'Simulation completed. (Development mock provider does not produce AI images).',
        };
      }
      if (loadingResultImage) {
        return {
          key: 'completed',
          label: 'Loading AI Result',
          badgeColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
          dotColor: 'bg-indigo-600',
          headline: 'Downloading Generated Image...',
          description: 'Retrieving generated fitting image from private backend storage.',
        };
      }
      if (hasDisplayableResult && isGenuineInference) {
        return {
          key: 'completed',
          label: 'AI Fitting Complete',
          badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
          dotColor: 'bg-emerald-500',
          headline: 'AI Fitting Complete',
          description:
            sessionData.stageMessage ||
            'Genuine FASHN VTON v1.5 neural try-on image ready.',
        };
      }
      if (hasDisplayableResult) {
        return {
          key: 'completed',
          label: 'Imported Fitting Ready',
          badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
          dotColor: 'bg-amber-500',
          headline: 'Imported Fitting Loaded',
          description: 'External fitting image loaded into viewport (unverified manual import).',
        };
      }
      return {
        key: 'completed',
        label: 'Result Image Error',
        badgeColor: 'bg-rose-50 text-rose-700 border-rose-200',
        dotColor: 'bg-rose-500',
        headline: 'Unable to Load Generated Image',
        description:
          resultFetchError ||
          'Inference completed on the backend, but no readable result image could be loaded.',
      };
    }
    if (tryOnState === 'failed') {
      return {
        key: 'failed',
        label: 'Generation Failed',
        badgeColor: 'bg-rose-50 text-rose-700 border-rose-200',
        dotColor: 'bg-rose-500',
        headline: categorizedError?.title || 'Virtual Try-On Encountered an Error',
        description: categorizedError?.description || 'Virtual try-on could not be completed.',
      };
    }
    if (customerPhoto && selectedGarment) {
      return {
        key: 'both',
        label: 'Ready to Generate',
        badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        dotColor: 'bg-emerald-500',
        headline: 'Inputs Ready — Click Generate AI Fitting',
        description:
          'Both customer photo and outfit are configured. Click "Generate AI Fitting" below to synthesize this garment onto your photo.',
      };
    }
    if (customerPhoto && !selectedGarment) {
      return {
        key: 'photo_only',
        label: 'Photo Ready',
        badgeColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
        dotColor: 'bg-indigo-500',
        headline: 'Photo Ready — Select a Garment',
        description:
          'Your customer photo is loaded. Now choose an outfit from Step 2 to configure the try-on preview.',
      };
    }
    if (!customerPhoto && selectedGarment) {
      return {
        key: 'garment_only',
        label: 'Garment Selected',
        badgeColor: 'bg-purple-50 text-purple-700 border-purple-200',
        dotColor: 'bg-purple-500',
        headline: 'Garment Selected — Upload Your Photo',
        description: `You selected "${selectedGarment.name}". Upload a customer photo in Step 1 to prepare the fitting preview.`,
      };
    }
    return {
      key: 'none',
      label: 'Awaiting Photo Upload',
      badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
      dotColor: 'bg-amber-500',
      headline: 'Awaiting Photo Upload',
      description:
        'Upload your customer photo in Step 1 and choose an outfit in Step 2 to configure the virtual fitting canvas.',
    };
  };

  const statusInfo = getDynamicStatus();

  if (!activeShopSlug && !querySessionId) {
    return (
      <ShopSelector
        mode="try-on"
        title="Choose a Boutique Virtual Fitting Room"
        subtitle="Each shop has its own isolated Virtual Try-On room with only its published garments. Select a boutique below to begin."
      />
    );
  }

  if (shopNotFound) {
    return (
      <div className="pt-12 pb-20">
        <Container>
          <div className="rounded-3xl bg-white border border-rose-200 p-8 sm:p-10 text-center max-w-lg mx-auto shadow-xs space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Boutique Storefront Not Found</h2>
            <p className="text-xs sm:text-sm text-slate-600">
              {garmentsError || `No boutique storefront matches '${activeShopSlug}'.`}
            </p>
            <Button to="/try-on" variant="primary" size="sm">
              Choose Another Boutique
            </Button>
          </div>
        </Container>
      </div>
    );
  }

  const storeDisplayName = activeShop?.shop_name || activeShopSlug;

  return (
    <div className="pt-6 pb-16 sm:pt-10 sm:pb-20">
      <Container>
        {/* Header */}
        <div className="mb-8 space-y-3 scroll-mt-28">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <div
                  data-testid="tryon-storefront-badge"
                  className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold"
                >
                  <Store className="w-3.5 h-3.5" />
                  <span>{storeDisplayName ? `${storeDisplayName} Fitting Room` : 'Virtual Try-On Studio'}</span>
                </div>
                <Link
                  to="/try-on"
                  data-testid="tryon-switch-store"
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white border border-slate-200 hover:border-indigo-300 text-slate-600 hover:text-indigo-700 text-xs font-semibold transition-colors"
                >
                  <ArrowLeftRight className="w-3 h-3" />
                  <span>Switch Store</span>
                </Link>
              </div>
              <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
                {activeShop?.shop_name ? `${activeShop.shop_name} — Virtual Try-On` : 'AI Virtual Fitting Room'}
              </h1>
              <p className="text-slate-600 text-sm sm:text-base leading-relaxed max-w-3xl">
                Upload a clear customer photo and select a published garment from <strong>{storeDisplayName || 'this boutique'}</strong> to synthesize personalized fittings.
              </p>
            </div>

            {/* Try-On History Action */}
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  if (isAuthenticated) {
                    setHistoryModalOpen(true);
                    loadHistory();
                  } else {
                    setAuthModalOpen(true);
                  }
                }}
                leftIcon={History}
              >
                My Try-On History
              </Button>
            </div>
          </div>
        </div>

        {/* Studio Workspace 2-Column Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Step 1 (Upload Photo) + Step 2 (Select Garment) */}
          <div className="lg:col-span-5 space-y-6">
            {/* ================= STEP 1: UPLOAD PHOTO ================= */}
            <div className="rounded-3xl bg-white border border-slate-200/90 p-5 sm:p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-black">
                    1
                  </span>
                  Customer Photo
                </span>
                <span className="text-[11px] text-slate-400 font-medium">JPG, PNG, WebP (Max 10 MB)</span>
              </div>

              {/* Hidden File Input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                onChange={handleFileInputChange}
                className="hidden"
                disabled={tryOnState === 'submitting' || tryOnState === 'polling'}
              />

              {/* Error Message Alert */}
              {errorMessage && (
                <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2 animate-fadeIn">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-500" />
                  <div className="flex-1">
                    <p className="font-semibold">Upload failed</p>
                    <p className="text-[11px] text-rose-600">{errorMessage}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setErrorMessage('')}
                    className="p-1 hover:bg-rose-100 rounded text-rose-500 cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Dropzone Container or Preview */}
              {!customerPhoto ? (
                <div className="space-y-3">
                  <div
                    onDragEnter={handleDragEnter}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-3xl p-6 sm:p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3 ${
                      isDragging
                        ? 'border-indigo-600 bg-indigo-50/70 scale-[0.99] ring-4 ring-indigo-500/10'
                        : 'border-slate-300 hover:border-indigo-400 bg-slate-50/60 hover:bg-slate-50'
                    }`}
                  >
                    <div
                      className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all ${
                        isDragging ? 'bg-indigo-600 text-white scale-110' : 'bg-indigo-50 text-indigo-600'
                      }`}
                    >
                      <Upload className="w-6 h-6" />
                    </div>

                    <div>
                      <p className="text-xs sm:text-sm font-bold text-slate-800">
                        {isDragging ? 'Drop your photo here' : 'Click to upload or drag & drop'}
                      </p>
                      <p className="text-[11px] text-slate-500 mt-1">
                        High-resolution front-facing portrait or full-body photo
                      </p>
                    </div>

                    <div className="pt-1">
                      <span className="px-3 py-1 rounded-full bg-white border border-slate-200 text-slate-600 text-[11px] font-semibold shadow-2xs">
                        Browse Files
                      </span>
                    </div>
                  </div>

                  {/* Secondary Live Camera Button */}
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={() => setCameraNotice(true)}
                      className="w-full py-2.5 px-3 rounded-2xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-2xs"
                    >
                      <Camera className="w-4 h-4 text-slate-500" />
                      <span>Use Device Camera</span>
                    </button>
                  </div>

                  {/* Camera Notice Message */}
                  {cameraNotice && (
                    <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-800 space-y-1 animate-fadeIn">
                      <div className="flex items-center justify-between">
                        <span className="font-bold flex items-center gap-1.5">
                          <Camera className="w-3.5 h-3.5 text-amber-600" />
                          Live Camera Capture
                        </span>
                        <button
                          type="button"
                          onClick={() => setCameraNotice(false)}
                          className="p-1 hover:bg-black/5 rounded cursor-pointer"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-[11px] text-amber-700 leading-relaxed">
                        Live camera access will be integrated with webcams. Please upload an image file above for now.
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                /* Customer Photo Active Preview Container */
                <div className="space-y-3">
                  <div className="relative aspect-3/4 w-full rounded-2xl overflow-hidden bg-slate-900 border border-slate-200 shadow-inner group">
                    <img
                      src={customerPhoto.previewUrl}
                      alt="Customer Preview"
                      className="w-full h-full object-cover object-center"
                    />

                    {/* Gradient Overlay & Badge */}
                    <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-center justify-between text-white text-xs">
                      <div className="flex items-center gap-1.5">
                        <CheckCircle className="w-4 h-4 text-emerald-400" />
                        <span className="font-semibold text-[11px]">Photo Configured</span>
                      </div>
                      <span className="text-[10px] bg-white/20 backdrop-blur-xs px-2 py-0.5 rounded-full font-mono">
                        {customerPhoto.size}
                      </span>
                    </div>

                    {/* Remove Photo Top-Right Pill */}
                    {tryOnState !== 'submitting' && tryOnState !== 'polling' && (
                      <button
                        type="button"
                        onClick={handleRemovePhoto}
                        className="absolute top-2.5 right-2.5 p-1.5 rounded-full bg-black/60 text-white hover:bg-black/90 transition-colors cursor-pointer"
                        title="Remove Photo"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* Metadata line */}
                  <div className="text-xs text-slate-600 px-1 flex items-center justify-between">
                    <span className="truncate max-w-[220px] font-medium text-slate-700">
                      {customerPhoto.name}
                    </span>
                    <span className="text-slate-400 text-[11px] shrink-0 font-mono">
                      {customerPhoto.size}
                    </span>
                  </div>

                  {/* Dedicated Action Buttons: Change Photo & Remove Photo */}
                  {tryOnState !== 'submitting' && tryOnState !== 'polling' && (
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={RefreshCw}
                        onClick={() => fileInputRef.current?.click()}
                        className="flex-1 justify-center text-xs"
                      >
                        Change Photo
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={X}
                        onClick={handleRemovePhoto}
                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 border border-rose-200 text-xs px-3"
                      >
                        Remove
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ================= STEP 2: SELECT GARMENT ================= */}
            <div className="rounded-3xl bg-white border border-slate-200/90 p-5 sm:p-6 shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-black">
                    2
                  </span>
                  Select Garment
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={loadGarments}
                    disabled={loadingGarments}
                    className="text-xs text-slate-600 hover:text-indigo-600 flex items-center gap-1 cursor-pointer font-semibold disabled:opacity-50"
                    title="Refresh active garments from catalogue"
                  >
                    <RefreshCw className={`w-3 h-3 ${loadingGarments ? 'animate-spin' : ''}`} />
                    <span>{garmentsError ? 'Retry' : 'Sync'}</span>
                  </button>
                  <Link
                    to={activeShopSlug ? `/store/${activeShopSlug}/catalogue` : '/catalogue'}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline flex items-center gap-1"
                  >
                    <span>View Full Catalogue</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>

              {/* Category Pills Filter */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-4 scrollbar-none">
                {categories.map((cat) => {
                  const isActive = activeCategory === cat;
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setActiveCategory(cat)}
                      disabled={tryOnState === 'submitting' || tryOnState === 'polling'}
                      className={`px-3 py-1 rounded-xl text-xs font-medium transition-all shrink-0 cursor-pointer ${
                        isActive
                          ? 'bg-indigo-600 text-white shadow-2xs'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {cat}
                    </button>
                  );
                })}
              </div>

              {garmentMismatchError && (
                <div
                  data-testid="garment-mismatch-alert"
                  className="mb-3 p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-start gap-2"
                >
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
                  <span className="flex-1">{garmentMismatchError}</span>
                  <button
                    type="button"
                    onClick={() => setGarmentMismatchError('')}
                    className="p-0.5 rounded hover:bg-amber-100 cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Garments Content Area: Loading | Error | Empty | Grid */}
              {loadingGarments ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-pulse">
                  {[1, 2, 3, 4].map((n) => (
                    <div
                      key={n}
                      className="rounded-2xl border border-slate-200/90 bg-white p-2.5 space-y-2 shadow-2xs"
                    >
                      <div className="aspect-3/4 rounded-xl bg-slate-200" />
                      <div className="h-3.5 bg-slate-200 rounded-md w-3/4" />
                      <div className="h-3 bg-indigo-100 rounded-md w-1/2" />
                    </div>
                  ))}
                </div>
              ) : garmentsError ? (
                <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-center space-y-2">
                  <div className="flex items-center justify-center gap-1.5 text-rose-700 font-semibold text-xs">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>Failed to load garments</span>
                  </div>
                  <p className="text-[11px] text-rose-600 leading-relaxed max-w-xs mx-auto">
                    {garmentsError}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    leftIcon={RefreshCw}
                    onClick={loadGarments}
                    className="mt-1 text-xs mx-auto"
                  >
                    Retry Connection
                  </Button>
                </div>
              ) : garments.length === 0 ? (
                <div
                  data-testid="tryon-empty-storefront"
                  className="py-10 px-4 rounded-2xl bg-slate-50 border border-slate-200/80 text-center space-y-2"
                >
                  <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-1">
                    <Shirt className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-bold text-slate-800">
                    {storeDisplayName || 'This Boutique'} Has No Garments Available
                  </p>
                  <p className="text-[11px] text-slate-500 max-w-xs mx-auto">
                    This boutique currently has 0 published garments in its inventory. Switch stores or ask the shop owner to add items via Shop Dashboard.
                  </p>
                  <div className="flex items-center justify-center gap-3 pt-1">
                    <Link
                      to="/try-on"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-slate-700 hover:text-indigo-700 hover:underline"
                    >
                      Switch Boutique
                    </Link>
                    <Link
                      to="/shop-dashboard"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline"
                    >
                      Go to Shop Dashboard <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              ) : filteredGarments.length === 0 ? (
                <div className="py-8 px-4 rounded-2xl bg-slate-50 border border-slate-200/80 text-center space-y-2">
                  <p className="text-xs font-bold text-slate-700">No garments match "{activeCategory}"</p>
                  <button
                    type="button"
                    onClick={() => setActiveCategory('All')}
                    className="text-xs text-indigo-600 font-semibold hover:underline cursor-pointer"
                  >
                    Reset to All Categories
                  </button>
                </div>
              ) : (
                /* Garments Grid */
                <div className="grid grid-cols-2 gap-3 max-h-84 overflow-y-auto pr-1">
                  {filteredGarments.map((garment) => {
                    const isSelected = String(selectedGarment?.id) === String(garment.id);
                    const hasThumbError = Boolean(imageErrors[garment.id]);

                    return (
                      <button
                        key={garment.id}
                        type="button"
                        onClick={() => handleGarmentToggle(garment)}
                        disabled={tryOnState === 'submitting' || tryOnState === 'polling'}
                        className={`text-left p-2.5 rounded-2xl border transition-all relative group cursor-pointer ${
                          isSelected
                            ? 'border-indigo-600 bg-indigo-50/70 ring-2 ring-indigo-500/40 shadow-xs'
                            : 'border-slate-200 hover:border-slate-300 bg-slate-50/40'
                        }`}
                      >
                        {/* Image Thumbnail with Fallback */}
                        <div className="h-24 w-full rounded-xl overflow-hidden bg-slate-100 mb-2 relative">
                          {garment.image && !hasThumbError ? (
                            <img
                              src={garment.image}
                              alt={garment.name}
                              className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-300"
                              onError={() => handleThumbnailError(garment.id)}
                            />
                          ) : (
                            <div
                              className={`w-full h-full bg-gradient-to-tr ${garment.fallbackBg || 'from-indigo-900 to-slate-900'} flex items-center justify-center text-white/80 p-2 text-center`}
                            >
                              <Shirt className="w-8 h-8" />
                            </div>
                          )}
                          {isSelected && (
                            <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center shadow-md animate-scaleIn">
                              <CheckCircle className="w-3.5 h-3.5" />
                            </div>
                          )}
                        </div>

                        <p className="text-xs font-bold text-slate-900 truncate" title={garment.name}>
                          {garment.name}
                        </p>
                        <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1">
                          <span>{garment.category}</span>
                          <strong className="text-indigo-600 font-semibold">{formatRupeePrice(garment.price)}</strong>
                        </div>
                        {Array.isArray(garment.colors) && garment.colors.length > 0 && (
                          <div
                            className="flex flex-wrap gap-1 mt-1.5"
                            data-testid={`garment-colors-${garment.id}`}
                          >
                            {garment.colors.slice(0, 3).map((color) => (
                              <span
                                key={color}
                                className="px-1.5 py-0.5 text-[10px] font-medium rounded-md bg-white text-slate-600 border border-slate-200 truncate max-w-[85px]"
                                title={color}
                              >
                                {color}
                              </span>
                            ))}
                            {garment.colors.length > 3 && (
                              <span className="px-1.5 py-0.5 text-[10px] font-medium rounded-md bg-slate-100 text-slate-500">
                                +{garment.colors.length - 3}
                              </span>
                            )}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Step 3 AI Preview Viewport */}
          <div className="lg:col-span-7">
            <div className="rounded-3xl bg-white border border-slate-200/90 p-6 sm:p-8 shadow-sm flex flex-col justify-between min-h-[640px]">
              <div>
                {/* Header with Dynamic Status Badge */}
                <div className="flex items-center justify-between pb-4 border-b border-slate-100 gap-2 flex-wrap">
                  <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-black">
                      3
                    </span>
                    AI Preview Viewport
                  </span>

                  {/* Dynamic Studio Status Pill */}
                  <div
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-bold transition-all ${statusInfo.badgeColor}`}
                  >
                    <span className={`w-2 h-2 rounded-full ${statusInfo.dotColor} animate-pulse`} />
                    <span>{statusInfo.label}</span>
                  </div>
                </div>

                {/* Validation Error Alert */}
                {validationError && (
                  <div className="mt-4 p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center justify-between animate-fadeIn">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                      <span>{validationError}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setValidationError('')}
                      className="p-1 hover:bg-amber-100 rounded text-amber-600 cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                {/* =========================================================
                    VIEWPORT CANVAS SWITCH: IDLE / PROCESSING / COMPLETED / FAILED
                    ========================================================= */}

                {/* 1. PROCESSING & POLLING STATE */}
                {(tryOnState === 'submitting' || tryOnState === 'polling') && (
                  <div className="my-6 rounded-2xl bg-gradient-to-b from-indigo-50/50 via-slate-50 to-purple-50/40 border border-indigo-100 p-8 sm:p-10 flex flex-col items-center justify-center text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:16px_16px] opacity-20 pointer-events-none" />

                    {/* High-tech pulsing indicator */}
                    <div className="relative mb-6 z-10">
                      <div className="w-20 h-20 rounded-3xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 text-white flex items-center justify-center shadow-xl shadow-indigo-500/30 animate-pulse">
                        <Sparkles className="w-10 h-10 animate-spin" style={{ animationDuration: '6s' }} />
                      </div>
                      <div className="absolute -inset-2 rounded-3xl border-2 border-indigo-400/40 animate-ping" style={{ animationDuration: '3s' }} />
                    </div>

                    {/* Dynamic Progress Percentage Counter */}
                    <div className="relative z-10 mb-2">
                      <span className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight font-mono">
                        {sessionData.progress}%
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="relative z-10 w-full max-w-md bg-slate-200 rounded-full h-3 mb-4 overflow-hidden p-0.5">
                      <div
                        className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 h-full rounded-full transition-all duration-700 ease-out shadow-xs"
                        style={{ width: `${Math.max(sessionData.progress, 5)}%` }}
                      />
                    </div>

                    {/* Actual Stage Message from Backend */}
                    <p className="relative z-10 text-sm font-bold text-slate-800 max-w-md leading-relaxed mb-1">
                      {sessionData.stageMessage || 'Synthesizing neural virtual try-on...'}
                    </p>

                    <p className="relative z-10 text-xs text-slate-500 max-w-sm mb-6">
                      {sessionData.isSimulation
                        ? 'Running development simulation engine (mock mode).'
                        : 'Neural diffusion synthesis in progress. This ensures accurate garment drape and realistic skin preservation.'}
                    </p>

                    {/* Session Metadata Tag */}
                    <div className="relative z-10 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-slate-200 text-xs text-slate-600 font-medium shadow-2xs mb-2">
                      <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse" />
                      <span>Provider: <strong className="uppercase">{sessionData.provider}</strong></span>
                      {sessionData.sessionId && (
                        <span className="text-slate-400 font-mono text-[10px]">
                          (ID: {sessionData.sessionId.slice(0, 8)}...)
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* 2. COMPLETED STATE */}
                {tryOnState === 'completed' && (
                  <div className="my-6 space-y-4">
                    {/* View Mode Tabs (if result image is present and loaded cleanly) */}
                    {hasDisplayableResult && (
                      <div className="flex items-center justify-between gap-2 flex-wrap bg-slate-100 p-1.5 rounded-2xl">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setViewMode('result')}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                              viewMode === 'result'
                                ? 'bg-white text-indigo-700 shadow-xs'
                                : 'text-slate-600 hover:text-slate-900'
                            }`}
                          >
                            Generated Fitting
                          </button>
                          <button
                            type="button"
                            onClick={() => setViewMode('split')}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                              viewMode === 'split'
                                ? 'bg-white text-indigo-700 shadow-xs'
                                : 'text-slate-600 hover:text-slate-900'
                            }`}
                          >
                            Side-by-Side
                          </button>
                          <button
                            type="button"
                            onClick={() => setViewMode('original')}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                              viewMode === 'original'
                                ? 'bg-white text-indigo-700 shadow-xs'
                                : 'text-slate-600 hover:text-slate-900'
                            }`}
                          >
                            Original Photo
                          </button>
                        </div>

                        {isGenuineInference ? (
                          <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span>AI Fitting Complete</span>
                          </span>
                        ) : (
                          <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                            <ShieldAlert className="w-3.5 h-3.5" />
                            <span>Imported Fitting Ready</span>
                          </span>
                        )}
                      </div>
                    )}

                    {/* Result Viewport Canvas */}
                    <div className="rounded-2xl bg-slate-950 border border-slate-200 p-4 sm:p-6 flex flex-col items-center justify-center relative overflow-hidden">
                      {hasDisplayableResult ? (
                        <>
                          {/* Mode: Result Only */}
                          {viewMode === 'result' && (
                            <div className="relative w-full max-w-md aspect-3/4 rounded-xl overflow-hidden bg-slate-900 shadow-2xl">
                              <img
                                src={resultBlobUrl}
                                alt="Virtual Try-On Result"
                                onError={handleResultImageRenderError}
                                className="w-full h-full object-cover object-center animate-fadeIn"
                              />
                              {isManualImport ? (
                                <div className="absolute top-3 left-3 bg-amber-950/80 backdrop-blur-xs text-amber-200 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5 border border-amber-500/30 shadow-xs">
                                  <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                                  <span>Manual Colab Import (Unverified)</span>
                                </div>
                              ) : isGenuineInference ? (
                                <div className="absolute top-3 left-3 bg-emerald-950/80 backdrop-blur-xs text-emerald-200 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5 border border-emerald-500/30 shadow-xs">
                                  <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                                  <span>Verified FASHN VTON Output</span>
                                </div>
                              ) : (
                                <div className="absolute top-3 left-3 bg-slate-900/80 backdrop-blur-xs text-slate-300 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5 border border-slate-700 shadow-xs">
                                  <span>Mock Simulation</span>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Mode: Side-by-Side Comparison */}
                          {viewMode === 'split' && (
                            <div className="w-full grid grid-cols-2 gap-3 sm:gap-4 max-w-lg animate-fadeIn">
                              {/* Original */}
                              <div className="flex flex-col items-center">
                                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-2">
                                  Customer Photo
                                </span>
                                <div className="relative w-full aspect-3/4 rounded-xl overflow-hidden bg-slate-800 border border-slate-700 flex items-center justify-center">
                                  {customerPhoto?.previewUrl ? (
                                    <img
                                      src={customerPhoto.previewUrl}
                                      alt="Original Customer"
                                      className="w-full h-full object-cover object-center"
                                    />
                                  ) : (
                                    <div className="p-4 text-center text-xs text-slate-400">
                                      <ImageIcon className="w-6 h-6 mx-auto mb-2 text-slate-500" />
                                      <span>Customer portrait is stored privately on the server.</span>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* AI Fitting */}
                              <div className="flex flex-col items-center">
                                <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                                  {isManualImport ? (
                                    <>
                                      <ShieldAlert className="w-3 h-3 text-amber-400" /> Manual Colab Fitting
                                    </>
                                  ) : (
                                    <>
                                      <Sparkles className="w-3 h-3 text-emerald-400" /> AI Virtual Try-On
                                    </>
                                  )}
                                </span>
                                <div className="relative w-full aspect-3/4 rounded-xl overflow-hidden bg-slate-800 border border-emerald-500/50 ring-2 ring-emerald-500/20 shadow-lg">
                                  <img
                                    src={resultBlobUrl}
                                    alt="AI Result"
                                    onError={handleResultImageRenderError}
                                    className="w-full h-full object-cover object-center"
                                  />
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Mode: Original Customer Photo */}
                          {viewMode === 'original' && (
                            <div className="relative w-full max-w-md aspect-3/4 rounded-xl overflow-hidden bg-slate-900 shadow-2xl animate-fadeIn flex items-center justify-center">
                              {customerPhoto?.previewUrl ? (
                                <>
                                  <img
                                    src={customerPhoto.previewUrl}
                                    alt="Original Customer"
                                    className="w-full h-full object-cover object-center"
                                  />
                                  <div className="absolute top-3 left-3 bg-black/70 backdrop-blur-xs text-white text-xs font-semibold px-2.5 py-1 rounded-full border border-white/10 shadow-xs">
                                    <span>Original Portrait</span>
                                  </div>
                                </>
                              ) : (
                                <div className="p-6 text-center text-xs text-slate-400 space-y-2">
                                  <ImageIcon className="w-8 h-8 mx-auto text-slate-500" />
                                  <p>Original portrait is stored privately on the server and was not uploaded in this browser tab.</p>
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      ) : loadingResultImage ? (
                        <div className="py-12 px-4 sm:px-6 text-center space-y-3 max-w-md w-full animate-fadeIn">
                          <div className="w-14 h-14 rounded-2xl bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 flex items-center justify-center mx-auto">
                            <RefreshCw className="w-7 h-7 text-indigo-400 animate-spin" />
                          </div>
                          <div>
                            <h4 className="text-base sm:text-lg font-bold text-white mb-1">
                              Loading Generated Try-On Image...
                            </h4>
                            <p className="text-xs text-slate-400 leading-relaxed">
                              Fetching the completed fitting image from private backend storage.
                            </p>
                          </div>
                        </div>
                      ) : isMockResult ? (
                        /* Simulation Completed Viewport Panel (Strictly for Mock Provider) */
                        <div className="py-10 px-4 sm:px-6 text-center space-y-3 max-w-md w-full animate-fadeIn">
                          <div className="w-14 h-14 rounded-2xl bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 flex items-center justify-center mx-auto shadow-inner">
                            <Sparkles className="w-7 h-7 text-indigo-400" />
                          </div>
                          <div>
                            <h4 className="text-base sm:text-lg font-bold text-white mb-1">
                              Simulation Completed
                            </h4>
                            <p className="text-xs text-slate-400 leading-relaxed">
                              {sessionData.stageMessage || 'Virtual try-on simulation finished. The development mock provider does not synthesize neural AI images.'}
                            </p>
                          </div>
                          <div className="pt-2">
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 text-slate-300 text-xs border border-slate-700">
                              <span>Provider: {sessionData.provider?.toUpperCase()}</span>
                            </span>
                          </div>
                        </div>
                      ) : (
                        /* Genuine Result Load Error Panel (Never mislabel as Simulation Completed) */
                        <div className="py-10 px-4 sm:px-6 text-center space-y-3 max-w-md w-full animate-fadeIn">
                          <div className="w-14 h-14 rounded-2xl bg-rose-500/20 border border-rose-400/30 text-rose-300 flex items-center justify-center mx-auto">
                            <AlertCircle className="w-7 h-7 text-rose-400" />
                          </div>
                          <div>
                            <h4 className="text-base sm:text-lg font-bold text-white mb-1">
                              Unable to Load Generated Image
                            </h4>
                            <p className="text-xs text-rose-200/90 leading-relaxed">
                              {resultFetchError || 'The AI inference completed, but the generated image could not be loaded into the viewport.'}
                            </p>
                          </div>
                          {sessionData.resultImageUrl && (
                            <p className="text-[11px] font-mono text-slate-400 break-all">
                              {sessionData.resultImageUrl}
                            </p>
                          )}
                          <div className="pt-2 flex items-center justify-center gap-2">
                            {sessionData.sessionId && sessionData.resultImageUrl && (
                              <button
                                type="button"
                                onClick={handleRetryLoadResult}
                                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors cursor-pointer"
                              >
                                <RefreshCw className="w-3.5 h-3.5" />
                                <span>Retry Loading Image</span>
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Honest Provenance Notice for Manual Imports */}
                    {hasDisplayableResult && isManualImport && (
                      <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs flex items-start gap-2.5">
                        <ShieldAlert className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                        <div>
                          <strong className="font-bold">Provenance Notice:</strong> This fitting was imported from an external environment (Google Colab). While the neural inference was performed with FASHN VTON v1.5 weights, the backend cannot cryptographically verify client-side upload authenticity.
                        </div>
                      </div>
                    )}

                    {/* Result Fetch Error Notice if any */}
                    {resultFetchError && (
                      <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{resultFetchError}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* 3. FAILED STATE */}
                {tryOnState === 'failed' && (
                  <div className="my-6 rounded-2xl bg-rose-50/70 border border-rose-200 p-6 sm:p-8 space-y-4 animate-fadeIn">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                        <AlertTriangle className="w-5 h-5" />
                      </div>
                      <div className="flex-1 space-y-1">
                        <h4 className="text-sm sm:text-base font-bold text-rose-900">
                          {categorizedError?.title || 'Virtual Try-On Failed'}
                        </h4>
                        <p className="text-xs text-rose-700 leading-relaxed">
                          {categorizedError?.description || 'The AI fitting request could not be completed at this time.'}
                        </p>
                      </div>
                    </div>

                    {/* Actionable Solution Hint */}
                    {categorizedError?.hint && (
                      <div className="p-3.5 rounded-xl bg-white/80 border border-rose-200/80 text-xs text-slate-700 space-y-1 shadow-2xs">
                        <p className="font-bold text-rose-800 flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-indigo-600" /> Recommended Resolution:
                        </p>
                        <p className="text-[11px] text-slate-600 leading-relaxed">
                          {categorizedError.hint}
                        </p>
                      </div>
                    )}

                    {/* Rate-limit / Cooldown Notice */}
                    {retryCooldown > 0 && (
                      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] font-semibold">
                        <Clock className="w-3.5 h-3.5 shrink-0" />
                        <span>Retry available in {formatCooldown(retryCooldown)}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* 4. IDLE / CONFIGURED STATE */}
                {tryOnState === 'idle' && (
                  <div className="my-6 rounded-2xl bg-gradient-to-b from-slate-50 to-slate-100/70 border border-slate-200/80 p-6 sm:p-8 flex flex-col items-center justify-center text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:16px_16px] opacity-15 pointer-events-none" />

                    {/* Visual Preview Comparison Strip when items are selected */}
                    {customerPhoto || selectedGarment ? (
                      <div className="relative z-10 w-full max-w-md mb-6 grid grid-cols-2 gap-3 sm:gap-4 items-stretch">
                        {/* Customer Photo Preview Card */}
                        <div className="rounded-2xl border border-slate-200/90 bg-white p-2.5 shadow-2xs flex flex-col items-center">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                            Customer Photo
                          </span>
                          {customerPhoto ? (
                            <div className="relative w-full aspect-3/4 rounded-xl overflow-hidden bg-slate-100">
                              <img
                                src={customerPhoto.previewUrl}
                                alt="Customer Preview"
                                className="w-full h-full object-cover object-center"
                              />
                              <div className="absolute bottom-1 inset-x-1 bg-slate-900/75 backdrop-blur-xs text-white text-[9px] font-medium py-0.5 px-1 rounded text-center truncate">
                                Photo Ready
                              </div>
                            </div>
                          ) : (
                            <div className="w-full aspect-3/4 rounded-xl border border-dashed border-slate-200 bg-slate-50 flex flex-col items-center justify-center p-2 text-center text-slate-400">
                              <ImageIcon className="w-6 h-6 mb-1 text-slate-300" />
                              <span className="text-[10px]">Awaiting Photo</span>
                            </div>
                          )}
                        </div>

                        {/* Selected Garment Preview Card */}
                        <div className="rounded-2xl border border-slate-200/90 bg-white p-2.5 shadow-2xs flex flex-col items-center">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                            Selected Garment
                          </span>
                          {selectedGarment ? (
                            <div className="relative w-full aspect-3/4 rounded-xl overflow-hidden bg-slate-100">
                              {selectedGarment.image && !imageErrors[selectedGarment.id] ? (
                                <img
                                  src={selectedGarment.image}
                                  alt={selectedGarment.name}
                                  className="w-full h-full object-cover object-top"
                                  onError={() => handleThumbnailError(selectedGarment.id)}
                                />
                              ) : (
                                <div
                                  className={`w-full h-full bg-gradient-to-tr ${selectedGarment.fallbackBg || 'from-indigo-900 to-slate-900'} flex flex-col items-center justify-center text-white/80 p-3 text-center`}
                                >
                                  <Shirt className="w-8 h-8 mb-1" />
                                  <span className="text-[10px] font-semibold text-white/90 line-clamp-2">
                                    {selectedGarment.name}
                                  </span>
                                </div>
                              )}
                              <div className="absolute bottom-1 inset-x-1 bg-slate-900/75 backdrop-blur-xs text-white text-[9px] font-medium py-0.5 px-1 rounded text-center truncate">
                                {formatRupeePrice(selectedGarment.price)}
                              </div>
                            </div>
                          ) : (
                            <div className="w-full aspect-3/4 rounded-xl border border-dashed border-slate-200 bg-slate-50 flex flex-col items-center justify-center p-2 text-center text-slate-400">
                              <Shirt className="w-6 h-6 mb-1 text-slate-300" />
                              <span className="text-[10px]">None Selected</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      /* Default Icon when nothing is selected */
                      <div className="relative mb-5 z-10">
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center shadow-lg shadow-indigo-500/25">
                          <Sparkles className="w-8 h-8" />
                        </div>
                      </div>
                    )}

                    {/* Headline & Dynamic Context Description */}
                    <h3 className="relative z-10 text-lg sm:text-xl font-extrabold text-slate-900 tracking-tight mb-2">
                      {statusInfo.headline}
                    </h3>

                    <p className="relative z-10 text-xs sm:text-sm text-slate-600 max-w-md leading-relaxed mb-6">
                      {statusInfo.description}
                    </p>

                    {/* Configuration Status Card */}
                    <div className="relative z-10 w-full max-w-sm rounded-xl bg-white border border-slate-200 p-4 text-left shadow-xs space-y-2.5">
                      {/* Dynamic Status Row */}
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Studio Status:</span>
                        <span className={`font-bold px-2 py-0.5 rounded-full border text-[11px] flex items-center gap-1.5 ${statusInfo.badgeColor}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${statusInfo.dotColor}`} />
                          {statusInfo.label}
                        </span>
                      </div>

                      {/* Customer Photo Row */}
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Customer Photo:</span>
                        {customerPhoto ? (
                          <span className="text-emerald-600 font-bold flex items-center gap-1 truncate max-w-[180px]">
                            <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                            <span className="truncate">Photo Ready ({customerPhoto.name})</span>
                          </span>
                        ) : (
                          <span className="text-amber-600 font-medium">Awaiting Photo Upload</span>
                        )}
                      </div>

                      {/* Selected Garment Row */}
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Selected Garment:</span>
                        {selectedGarment ? (
                          <span className="text-indigo-600 font-bold truncate max-w-[180px]" title={selectedGarment.name}>
                            {selectedGarment.name}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">None Selected</span>
                        )}
                      </div>

                      {/* Available Colours Row */}
                      {selectedGarment && Array.isArray(selectedGarment.colors) && selectedGarment.colors.length > 0 && (
                        <div className="flex items-start justify-between gap-2 text-xs">
                          <span className="text-slate-500 font-medium shrink-0">Available Colours:</span>
                          <div
                            className="flex flex-wrap justify-end gap-1"
                            data-testid="selected-garment-colors"
                          >
                            {selectedGarment.colors.map((color) => {
                              const isColorActive = selectedColor === color;
                              return (
                                <button
                                  key={color}
                                  type="button"
                                  onClick={() => setSelectedColor(color)}
                                  className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border transition-colors cursor-pointer ${
                                    isColorActive
                                      ? 'bg-indigo-600 text-white border-indigo-600'
                                      : 'bg-slate-50 text-slate-700 border-slate-200 hover:border-indigo-300'
                                  }`}
                                >
                                  {color}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Fitting Algorithm Row */}
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Fitting Algorithm:</span>
                        <span className="text-indigo-700 font-semibold flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-indigo-600 inline-block animate-pulse" />
                          FASHN VTON v1.5 Engine
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* =========================================================
                  BOTTOM ACTION FOOTER (Contextual according to state)
                  ========================================================= */}
              <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                {/* Status / Notice text */}
                <p className="text-xs text-slate-500 text-center sm:text-left">
                  {tryOnState === 'completed' && hasDisplayableResult && isGenuineInference
                    ? 'AI virtual try-on generated using FASHN VTON v1.5.'
                    : tryOnState === 'completed' && resultFetchError
                    ? 'Result image failed to load. Use Retry Loading Image above.'
                    : tryOnState === 'failed'
                    ? 'Inference failed. Check resolution advice above.'
                    : tryOnState === 'submitting' || tryOnState === 'polling'
                    ? 'Neural diffusion synthesis in progress. Do not refresh.'
                    : 'Customer photo is processed privately and never shared publicly.'}
                </p>

                {/* State-Specific Action Buttons */}
                <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                  {/* COMPLETED ACTIONS */}
                  {tryOnState === 'completed' && (
                    <>
                      {hasDisplayableResult && (
                        <Button
                          variant="primary"
                          size="md"
                          leftIcon={Download}
                          onClick={handleDownloadResult}
                          className="flex-1 sm:flex-none justify-center text-xs"
                        >
                          Download Image
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="md"
                        leftIcon={Shirt}
                        onClick={() => {
                          setTryOnState('idle');
                          setLoadingResultImage(false);
                          setResultFetchError(null);
                          if (resultBlobUrl) {
                            URL.revokeObjectURL(resultBlobUrl);
                            setResultBlobUrl(null);
                          }
                        }}
                        className="flex-1 sm:flex-none justify-center text-xs"
                      >
                        Try Another Garment
                      </Button>
                      <Button
                        variant="ghost"
                        size="md"
                        leftIcon={RotateCcw}
                        onClick={handleResetAll}
                        className="text-slate-500 hover:text-slate-700 text-xs px-2.5"
                        title="Reset Studio"
                      >
                        Reset
                      </Button>
                    </>
                  )}

                  {/* FAILED ACTIONS */}
                  {tryOnState === 'failed' && (
                    <>
                      <Button
                        variant="primary"
                        size="md"
                        leftIcon={RefreshCw}
                        onClick={handleStartTryOn}
                        disabled={!canGenerate}
                        className="flex-1 sm:flex-none justify-center text-xs"
                      >
                        {retryCooldown > 0 ? `Retry in ${formatCooldown(retryCooldown)}` : 'Retry AI Fitting'}
                      </Button>
                      <Button
                        variant="outline"
                        size="md"
                        onClick={handleResetAll}
                        className="flex-1 sm:flex-none justify-center text-xs"
                      >
                        Reset Studio
                      </Button>
                    </>
                  )}

                  {/* PROCESSING ACTIONS */}
                  {(tryOnState === 'submitting' || tryOnState === 'polling') && (
                    <Button
                      variant="outline"
                      size="md"
                      leftIcon={X}
                      onClick={handleCancelTryOn}
                      className="text-rose-600 border-rose-200 hover:bg-rose-50 w-full sm:w-auto text-xs"
                    >
                      Cancel
                    </Button>
                  )}

                  {/* IDLE ACTIONS (Generate AI Fitting Button) */}
                  {tryOnState === 'idle' && (
                    <Button
                      variant="primary"
                      size="md"
                      leftIcon={Sparkles}
                      disabled={!canGenerate}
                      onClick={handleStartTryOn}
                      className={`w-full sm:w-auto transition-all text-xs font-bold ${
                        canGenerate
                          ? 'bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-700 hover:from-indigo-700 hover:to-purple-700 text-white shadow-md shadow-indigo-500/20 cursor-pointer scale-100 hover:scale-[1.02]'
                          : 'opacity-50 cursor-not-allowed'
                      }`}
                    >
                      {retryCooldown > 0
                        ? `Wait ${formatCooldown(retryCooldown)} before retrying`
                        : 'Generate AI Fitting'}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Try-On History Modal */}
        {historyModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
            <div
              className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden max-h-[85vh] flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/60">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center">
                    <History className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">My Try-On History</h3>
                    <p className="text-xs text-slate-500">Your past virtual fitting sessions and saved items</p>
                  </div>
                </div>
                <button
                  onClick={() => setHistoryModalOpen(false)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
                  aria-label="Close"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Content */}
              <div className="p-6 overflow-y-auto space-y-4 flex-1">
                {!isAuthenticated ? (
                  <div className="text-center py-8 space-y-3">
                    <Shirt className="w-10 h-10 text-slate-300 mx-auto" />
                    <p className="text-sm font-semibold text-slate-800">Sign in to view your history</p>
                    <p className="text-xs text-slate-500 max-w-xs mx-auto">
                      Create an account or sign in to save your fittings and access them anytime.
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        setHistoryModalOpen(false);
                        setAuthModalOpen(true);
                      }}
                    >
                      Sign In / Register
                    </Button>
                  </div>
                ) : loadingHistory ? (
                  <div className="text-center py-12 text-slate-400 flex flex-col items-center gap-2">
                    <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
                    <span className="text-xs font-medium">Loading your try-on history...</span>
                  </div>
                ) : historyError ? (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{historyError}</span>
                  </div>
                ) : historyItems.length === 0 ? (
                  <div className="text-center py-10 space-y-2 text-slate-400">
                    <Shirt className="w-10 h-10 text-slate-300 mx-auto" />
                    <p className="text-sm font-semibold text-slate-700">No fitting sessions yet</p>
                    <p className="text-xs text-slate-500">
                      Upload your photo and select a garment to generate your first virtual try-on!
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {historyItems.map((item) => (
                      <div
                        key={item.session_id}
                        className="py-3.5 flex items-center justify-between gap-4 hover:bg-slate-50/70 p-2 rounded-xl transition-colors"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          {item.garment_image_url ? (
                            <img
                              src={item.garment_image_url}
                              alt={item.product_name || item.garment_name || 'Garment Try-On'}
                              className="w-12 h-14 object-cover rounded-lg border border-slate-200 shrink-0 bg-slate-100"
                            />
                          ) : (
                            <div className="w-12 h-14 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0 text-slate-400">
                              <Shirt className="w-5 h-5" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <h4 className="text-xs font-bold text-slate-800 truncate">
                              {item.product_name || item.garment_name || 'Garment Try-On'}
                            </h4>
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              <span className="text-[10px] text-slate-400 font-medium flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent'}
                              </span>
                              {/* Provenance Badge */}
                              {item.provenance === 'manual_import' ? (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                                  Manual Colab
                                </span>
                              ) : (item.provenance === 'genuine_inference' || item.provenance === 'genuine_zerogpu') ? (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  FASHN AI
                                </span>
                              ) : (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                                  Simulation
                                </span>
                              )}
                              <span
                                className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                                  item.status === 'completed'
                                    ? 'text-emerald-700 bg-emerald-50'
                                    : item.status === 'failed'
                                    ? 'text-red-700 bg-red-50'
                                    : 'text-indigo-700 bg-indigo-50'
                                }`}
                              >
                                {item.status}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {item.status === 'completed' && item.result_image_url && (
                            <button
                              type="button"
                              onClick={async () => {
                                if (item.shop_slug && !routeShopSlug) {
                                  setSessionResolvedSlug(item.shop_slug);
                                }
                                setLoadingResultImage(true);
                                setResultFetchError(null);
                                setSessionData(mapStatusResponseToSessionData({
                                  ...item,
                                  stage_message: 'Loaded from try-on history.',
                                }));
                                setViewMode('result');
                                setTryOnState('completed');
                                setHistoryModalOpen(false);
                                try {
                                  const blob = await fetchTryOnResultBlob(item.session_id, {
                                    resultImageUrl: item.result_image_url,
                                  });
                                  applyLoadedResultBlob(blob);
                                } catch (err) {
                                  console.error('Could not load session result from history:', err);
                                  setResultBlobUrl(null);
                                  setResultFetchError(err.message || 'Could not load session result image.');
                                } finally {
                                  setLoadingResultImage(false);
                                }
                              }}
                              className="px-2.5 py-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100/70 rounded-lg transition-colors cursor-pointer"
                            >
                              View
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDeleteSession(item.session_id, item.product_name || item.garment_name)}
                            disabled={deletingSessionId === item.session_id}
                            className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors cursor-pointer"
                            title="Purge session & photos"
                          >
                            {deletingSessionId === item.session_id ? (
                              <RefreshCw className="w-4 h-4 animate-spin text-rose-500" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <span>{historyItems.length} saved {historyItems.length === 1 ? 'session' : 'sessions'}</span>
                <button
                  type="button"
                  onClick={() => setHistoryModalOpen(false)}
                  className="font-medium text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* In-App Try-On Session Deletion Confirmation Modal */}
        {sessionToDelete && (
          <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fadeIn">
            <div className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden p-6 space-y-4">
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0 border border-rose-100">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-slate-900">Purge Try-On Session</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Permanently delete session for{' '}
                    <strong className="text-slate-900 font-semibold">{sessionToDelete.garmentName}</strong>{' '}
                    (ID: #{sessionToDelete.id.slice(0, 8)})?
                  </p>
                  <p className="text-[11px] text-rose-600 font-medium pt-1">
                    Customer portrait photo and AI-generated fitting images will be permanently erased from disk and PostgreSQL to protect user privacy.
                  </p>
                </div>
              </div>

              {deleteError && (
                <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{deleteError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSessionToDelete(null)}
                  disabled={Boolean(deletingSessionId)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={confirmDeleteSession}
                  disabled={Boolean(deletingSessionId)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-xs"
                >
                  {deletingSessionId ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Purging...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Permanently Purge</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Auth Modal */}
        <AuthModal
          isOpen={authModalOpen}
          onClose={() => setAuthModalOpen(false)}
          initialMode="login"
        />
      </Container>
    </div>
  );
}
