import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Sparkles,
  Upload,
  Camera,
  CheckCircle,
  AlertCircle,
  X,
  RefreshCw,
  Shirt,
  ArrowRight,
  Image as ImageIcon,
} from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';
import { SAMPLE_CLOTHES } from '../data/sampleClothes';

const ALLOWED_MIME_TYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/webp',
];

const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

export default function TryOnPage() {
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef(null);
  const dragCounter = useRef(0);

  // States
  const [prevQueryGarmentId, setPrevQueryGarmentId] = useState(() => searchParams.get('garment'));
  const [customerPhoto, setCustomerPhoto] = useState(null); // { file, previewUrl, name, size }
  const [selectedGarment, setSelectedGarment] = useState(() => {
    const initialGarmentId = searchParams.get('garment');
    if (!initialGarmentId) return null;
    return SAMPLE_CLOTHES.find((g) => g.id === initialGarmentId) || null;
  });
  const [activeCategory, setActiveCategory] = useState('All');
  const [errorMessage, setErrorMessage] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [cameraNotice, setCameraNotice] = useState(false);
  const [imageErrors, setImageErrors] = useState({});

  const categories = ['All', 'Formal', 'Casual', 'Ethnic', 'Outerwear'];

  // Sync selected garment if query param changes (React 19 render-time adjustment pattern)
  const currentQueryGarmentId = searchParams.get('garment');
  if (currentQueryGarmentId !== prevQueryGarmentId) {
    setPrevQueryGarmentId(currentQueryGarmentId);
    if (currentQueryGarmentId) {
      const found = SAMPLE_CLOTHES.find((g) => g.id === currentQueryGarmentId);
      if (found) {
        setSelectedGarment(found);
        setActiveCategory('All');
      }
    }
  }

  // Cleanup object URL on unmount or file change
  useEffect(() => {
    return () => {
      if (customerPhoto?.previewUrl) {
        URL.revokeObjectURL(customerPhoto.previewUrl);
      }
    };
  }, [customerPhoto]);

  // Handle File Validation and Local Preview
  const processFile = (file) => {
    setErrorMessage('');

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
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      processFile(file);
    }
    // Reset input value so selecting the same file again triggers onChange
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
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleThumbnailError = (id) => {
    setImageErrors((prev) => ({ ...prev, [id]: true }));
  };

  const handleGarmentToggle = (garment) => {
    setSelectedGarment((prev) => (prev?.id === garment.id ? null : garment));
  };

  const filteredGarments =
    activeCategory === 'All'
      ? SAMPLE_CLOTHES
      : SAMPLE_CLOTHES.filter((g) => g.category === activeCategory);

  // Dynamic Viewport Status Calculation
  const getDynamicStatus = () => {
    if (customerPhoto && selectedGarment) {
      return {
        key: 'both',
        label: 'Ready for AI Integration',
        badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        dotColor: 'bg-emerald-500',
        headline: 'Ready for AI Integration',
        description:
          'Both customer photo and outfit are configured. The AI try-on pipeline will drape and synthesize this garment onto your photo once connected.',
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

  return (
    <div className="pt-6 pb-16 sm:pt-10 sm:pb-20">
      <Container>
        {/* Header */}
        <div className="mb-8 space-y-3 scroll-mt-28">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Interactive Fitting Studio</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            Virtual Try-On Studio
          </h1>
          <p className="text-slate-600 text-sm sm:text-base max-w-2xl leading-relaxed">
            Follow the 3-step studio workflow below: upload a customer photo, choose an outfit from the catalogue, and verify the interactive configuration preview.
          </p>
        </div>

        {/* Live Camera "Coming Soon" Notice Modal / Alert */}
        {cameraNotice && (
          <div className="mb-6 rounded-2xl bg-amber-50 border border-amber-200 p-4 flex items-center justify-between gap-3 text-amber-900 animate-fadeIn">
            <div className="flex items-center gap-2.5">
              <Camera className="w-5 h-5 text-amber-600 shrink-0" />
              <p className="text-xs sm:text-sm">
                <strong>Live Camera Capture is Coming Soon:</strong> We are optimizing real-time camera streaming for in-store tablet kiosks. Please upload a saved photo below for this version.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setCameraNotice(false)}
              className="p-1 hover:bg-amber-100 rounded-md text-amber-700 transition-colors cursor-pointer"
              aria-label="Close notification"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* 3-Step Workspace Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Step 1 & Step 2 */}
          <div className="lg:col-span-5 space-y-6">
            {/* ================= STEP 1: CUSTOMER PHOTO ================= */}
            <div className="rounded-3xl bg-white border border-slate-200/90 p-5 sm:p-6 shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-black">
                    1
                  </span>
                  Customer Photo
                </span>
                <span className="text-[11px] text-slate-400">JPG, PNG, WebP (Max 10MB)</span>
              </div>

              {/* Error Alert */}
              {errorMessage && (
                <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center justify-between gap-2 animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{errorMessage}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setErrorMessage('')}
                    className="p-0.5 hover:bg-rose-100 rounded text-rose-600 cursor-pointer"
                    aria-label="Dismiss error"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Stable Native File Input (Always in DOM) */}
              <input
                ref={fileInputRef}
                type="file"
                id="customer-photo-input"
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                onChange={handleFileInputChange}
                className="hidden"
                aria-label="Upload customer photo"
              />

              {/* Drag & Drop Upload Zone or Image Preview */}
              {!customerPhoto ? (
                <div
                  onDragEnter={handleDragEnter}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-2xl p-6 sm:p-8 text-center transition-all ${
                    isDragging
                      ? 'border-indigo-600 bg-indigo-50/70 scale-[1.01]'
                      : 'border-slate-300 hover:border-indigo-400 hover:bg-slate-50/60'
                  }`}
                >
                  <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-3 shadow-2xs">
                    <Upload className="w-7 h-7" />
                  </div>

                  <h3 className="text-sm font-bold text-slate-800">
                    {isDragging ? 'Drop photo here to upload' : 'Drag and drop your photo here'}
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                    Full-body or upper-body photo in normal posture and bright lighting works best.
                  </p>

                  <div className="mt-4 flex flex-col sm:flex-row items-center justify-center gap-2.5">
                    <Button
                      variant="primary"
                      size="sm"
                      leftIcon={Upload}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Browse Image
                    </Button>

                    {/* Live Camera Option Marked Coming Soon & Disabled */}
                    <button
                      type="button"
                      disabled
                      onClick={() => setCameraNotice(true)}
                      className="px-3 py-1.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-400 text-xs font-semibold flex items-center gap-1.5 cursor-not-allowed opacity-80"
                      title="Live camera capture is coming soon for in-store tablet kiosks"
                    >
                      <Camera className="w-3.5 h-3.5 text-slate-400" />
                      <span>Live Camera</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-100 text-amber-800 font-bold uppercase">
                        Coming Soon
                      </span>
                    </button>
                  </div>
                </div>
              ) : (
                /* Photo Preview Card with Image Inside and Clear Actions */
                <div className="space-y-4">
                  <div className="relative rounded-2xl overflow-hidden border border-slate-200 bg-slate-900/5 aspect-3/4 max-h-72 w-full flex items-center justify-center group shadow-xs">
                    <img
                      src={customerPhoto.previewUrl}
                      alt={customerPhoto.name}
                      className="w-full h-full object-contain sm:object-cover object-center"
                    />

                    {/* Top overlay badge */}
                    <div className="absolute top-2.5 left-2.5 bg-slate-900/80 backdrop-blur-md text-white text-[11px] font-medium px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-xs">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Photo Loaded (Local Preview)</span>
                    </div>

                    {/* Quick remove icon button */}
                    <button
                      type="button"
                      onClick={handleRemovePhoto}
                      className="absolute top-2.5 right-2.5 w-8 h-8 rounded-full bg-slate-900/80 hover:bg-rose-600 text-white flex items-center justify-center transition-colors shadow-md cursor-pointer"
                      title="Remove Photo"
                      aria-label="Remove photo"
                    >
                      <X className="w-4 h-4" />
                    </button>
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
                      Remove Photo
                    </Button>
                  </div>
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
                <Link
                  to="/catalogue"
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline flex items-center gap-1"
                >
                  <span>View Full Catalogue</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
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

              {/* Garments Grid */}
              <div className="grid grid-cols-2 gap-3 max-h-84 overflow-y-auto pr-1">
                {filteredGarments.map((garment) => {
                  const isSelected = selectedGarment?.id === garment.id;
                  const hasThumbError = Boolean(imageErrors[garment.id]);

                  return (
                    <button
                      key={garment.id}
                      type="button"
                      onClick={() => handleGarmentToggle(garment)}
                      className={`text-left p-2.5 rounded-2xl border transition-all relative group cursor-pointer ${
                        isSelected
                          ? 'border-indigo-600 bg-indigo-50/70 ring-2 ring-indigo-500/40 shadow-xs'
                          : 'border-slate-200 hover:border-slate-300 bg-slate-50/40'
                      }`}
                    >
                      {/* Image Thumbnail with Fallback */}
                      <div className="h-24 w-full rounded-xl overflow-hidden bg-slate-100 mb-2 relative">
                        {!hasThumbError ? (
                          <img
                            src={garment.image}
                            alt={garment.name}
                            className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-300"
                            onError={() => handleThumbnailError(garment.id)}
                          />
                        ) : (
                          <div
                            className={`w-full h-full bg-gradient-to-tr ${garment.fallbackBg} flex items-center justify-center text-white/80`}
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

                      <p className="text-xs font-bold text-slate-900 truncate">
                        {garment.name}
                      </p>
                      <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1">
                        <span>{garment.category}</span>
                        <strong className="text-indigo-600 font-semibold">{garment.price}</strong>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Column: Step 3 AI Preview Viewport */}
          <div className="lg:col-span-7">
            <div className="rounded-3xl bg-white border border-slate-200/90 p-6 sm:p-8 shadow-sm flex flex-col justify-between min-h-[600px]">
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

                {/* Main Canvas Viewport Area */}
                <div className="my-6 rounded-2xl bg-gradient-to-b from-slate-50 to-slate-100/70 border border-slate-200/80 p-6 sm:p-8 flex flex-col items-center justify-center text-center relative overflow-hidden">
                  {/* Subtle Grid Background Pattern */}
                  <div className="absolute inset-0 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:16px_16px] opacity-15 pointer-events-none" />

                  {/* Visual Preview Comparison Strip when items are selected */}
                  {(customerPhoto || selectedGarment) ? (
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
                            {!imageErrors[selectedGarment.id] ? (
                              <img
                                src={selectedGarment.image}
                                alt={selectedGarment.name}
                                className="w-full h-full object-cover object-top"
                                onError={() => handleThumbnailError(selectedGarment.id)}
                              />
                            ) : (
                              <div
                                className={`w-full h-full bg-gradient-to-tr ${selectedGarment.fallbackBg} flex items-center justify-center text-white/80`}
                              >
                                <Shirt className="w-6 h-6" />
                              </div>
                            )}
                            <div className="absolute bottom-1 inset-x-1 bg-slate-900/75 backdrop-blur-xs text-white text-[9px] font-medium py-0.5 px-1 rounded text-center truncate">
                              {selectedGarment.price}
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

                    {/* Fitting Algorithm Row: Strictly "AI Engine: Not Connected" */}
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500 font-medium">Fitting Algorithm:</span>
                      <span className="text-slate-700 font-semibold flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
                        AI Engine: Not Connected
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom Action Footer */}
              <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                <p className="text-xs text-slate-500 text-center sm:text-left">
                  No fake results are generated. Real AI output will be connected in Step 2.
                </p>

                {/* Disabled Generate Button */}
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={Sparkles}
                  disabled={true}
                  className="w-full sm:w-auto opacity-70 cursor-not-allowed"
                >
                  Generate Try-On (Coming Soon)
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Container>
    </div>
  );
}
