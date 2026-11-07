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
} from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';
import { SAMPLE_CLOTHES } from '../data/sampleClothes';

export default function TryOnPage() {
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef(null);

  // Preselect garment if provided in query params (?garment=id)
  const initialGarmentId = searchParams.get('garment');
  const matchedInitial = SAMPLE_CLOTHES.find((g) => g.id === initialGarmentId);

  // States
  const [customerPhoto, setCustomerPhoto] = useState(null); // { file, previewUrl, name, size }
  const [selectedGarment, setSelectedGarment] = useState(matchedInitial || SAMPLE_CLOTHES[0]);
  const [activeCategory, setActiveCategory] = useState('All');
  const [errorMessage, setErrorMessage] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [cameraNotice, setCameraNotice] = useState(false);

  const categories = ['All', 'Formal', 'Casual', 'Ethnic', 'Outerwear'];

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

    // Validate type
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setErrorMessage('Please upload a valid image file (JPG, PNG, or WebP).');
      return;
    }

    // Validate size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      setErrorMessage('File size exceeds 10MB. Please upload a smaller photo.');
      return;
    }

    // Revoke previous URL to prevent memory leaks
    if (customerPhoto?.previewUrl) {
      URL.revokeObjectURL(customerPhoto.previewUrl);
    }

    // Create local preview object URL
    const previewUrl = URL.createObjectURL(file);
    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);

    setCustomerPhoto({
      file,
      previewUrl,
      name: file.name,
      size: `${sizeInMB} MB`,
    });
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      processFile(file);
    }
    // Reset input value so selecting the same file triggers onChange
    e.target.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
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

  const filteredGarments =
    activeCategory === 'All'
      ? SAMPLE_CLOTHES
      : SAMPLE_CLOTHES.filter((g) => g.category === activeCategory);

  return (
    <div className="py-6 sm:py-12">
      <Container>
        {/* Header */}
        <div className="mb-8 space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Interactive Fitting Studio</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            Virtual Try-On Studio
          </h1>
          <p className="text-slate-600 text-sm sm:text-base max-w-2xl leading-relaxed">
            Follow the 3-step studio workflow below to test the customer photo upload, select sample outfits from the store catalogue, and view the AI fitting canvas.
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
              onClick={() => setCameraNotice(false)}
              className="p-1 hover:bg-amber-100 rounded-md text-amber-700 transition-colors cursor-pointer"
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
                <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              {/* Drag & Drop Upload Zone or Image Preview */}
              {!customerPhoto ? (
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-2xl p-6 sm:p-8 text-center transition-all ${
                    isDragging
                      ? 'border-indigo-600 bg-indigo-50/60 scale-[1.01]'
                      : 'border-slate-300 hover:border-indigo-400 hover:bg-slate-50/60'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    id="customer-photo-input"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleFileInputChange}
                    className="hidden"
                  />

                  <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-3 shadow-2xs">
                    <Upload className="w-7 h-7" />
                  </div>

                  <h3 className="text-sm font-bold text-slate-800">
                    Drag and drop your photo here
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

                    {/* Live Camera Option Marked Coming Soon */}
                    <button
                      type="button"
                      onClick={() => setCameraNotice(true)}
                      className="px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer"
                    >
                      <Camera className="w-3.5 h-3.5 text-slate-500" />
                      <span>Live Camera</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-100 text-amber-800 font-bold uppercase">
                        Soon
                      </span>
                    </button>
                  </div>
                </div>
              ) : (
                /* Photo Preview Card */
                <div className="space-y-3">
                  <div className="relative rounded-2xl overflow-hidden border border-slate-200 bg-slate-100 aspect-3/4 max-h-72 w-full flex items-center justify-center group">
                    <img
                      src={customerPhoto.previewUrl}
                      alt="Uploaded customer silhouette"
                      className="w-full h-full object-cover object-center"
                    />

                    {/* Top overlay badge */}
                    <div className="absolute top-2.5 left-2.5 bg-slate-900/80 backdrop-blur-md text-white text-[11px] font-medium px-2.5 py-1 rounded-lg flex items-center gap-1.5">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Photo Loaded (Local Preview)</span>
                    </div>

                    {/* Remove button */}
                    <button
                      type="button"
                      onClick={handleRemovePhoto}
                      className="absolute top-2.5 right-2.5 w-8 h-8 rounded-full bg-slate-900/80 hover:bg-rose-600 text-white flex items-center justify-center transition-colors shadow-md cursor-pointer"
                      title="Remove Photo"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Metadata and change actions */}
                  <div className="flex items-center justify-between text-xs text-slate-500 px-1">
                    <span className="truncate max-w-[200px] font-medium text-slate-700">
                      {customerPhoto.name} ({customerPhoto.size})
                    </span>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1 cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3" /> Change Photo
                    </button>
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleFileInputChange}
                    className="hidden"
                  />
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
                  className="text-xs font-semibold text-indigo-600 hover:underline"
                >
                  View Full Catalogue
                </Link>
              </div>

              {/* Category Pills Filter */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-4 scrollbar-none">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setActiveCategory(cat)}
                    className={`px-3 py-1 rounded-xl text-xs font-medium transition-all shrink-0 cursor-pointer ${
                      activeCategory === cat
                        ? 'bg-indigo-600 text-white shadow-2xs'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              {/* Garments Grid */}
              <div className="grid grid-cols-2 gap-3 max-h-80 overflow-y-auto pr-1">
                {filteredGarments.map((garment) => {
                  const isSelected = selectedGarment?.id === garment.id;
                  return (
                    <button
                      key={garment.id}
                      type="button"
                      onClick={() => setSelectedGarment(garment)}
                      className={`text-left p-2.5 rounded-2xl border transition-all relative group cursor-pointer ${
                        isSelected
                          ? 'border-indigo-600 bg-indigo-50/70 ring-2 ring-indigo-500/40 shadow-xs'
                          : 'border-slate-200 hover:border-slate-300 bg-slate-50/40'
                      }`}
                    >
                      {/* Image Thumbnail with Fallback */}
                      <div className="h-24 w-full rounded-xl overflow-hidden bg-slate-100 mb-2 relative">
                        <img
                          src={garment.image}
                          alt={garment.name}
                          className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-300"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none';
                            e.currentTarget.nextElementSibling?.classList.remove('hidden');
                          }}
                        />
                        <div
                          className={`hidden w-full h-full bg-gradient-to-tr ${garment.fallbackBg} flex items-center justify-center text-white/80`}
                        >
                          <Shirt className="w-8 h-8" />
                        </div>
                        {isSelected && (
                          <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center shadow-md">
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
            <div className="rounded-3xl bg-white border border-slate-200/90 p-6 sm:p-8 shadow-sm flex flex-col justify-between min-h-[580px]">
              <div>
                {/* Header */}
                <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                  <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-black">
                      3
                    </span>
                    AI Preview Viewport
                  </span>
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-purple-50 text-purple-700 border border-purple-200">
                    Integration Coming Soon
                  </span>
                </div>

                {/* Main Canvas Viewport Area */}
                <div className="my-6 rounded-2xl bg-gradient-to-b from-slate-50 to-slate-100/70 border border-slate-200/80 p-6 sm:p-10 flex flex-col items-center justify-center text-center relative overflow-hidden">
                  {/* Subtle Background Pattern */}
                  <div className="absolute inset-0 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:16px_16px] opacity-15 pointer-events-none" />

                  {/* Icon */}
                  <div className="relative mb-5">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center shadow-lg shadow-indigo-500/25">
                      <Sparkles className="w-8 h-8" />
                    </div>
                  </div>

                  {/* Headline & Required Message */}
                  <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight mb-2">
                    AI try-on integration coming soon
                  </h3>

                  <p className="text-xs sm:text-sm text-slate-600 max-w-md leading-relaxed mb-6">
                    The frontend foundation is complete. In the upcoming phase, our AI try-on pipeline will process customer photos, align garments, and generate realistic fabric fits.
                  </p>

                  {/* Configuration Status Card */}
                  <div className="w-full max-w-sm rounded-xl bg-white border border-slate-200 p-4 text-left shadow-xs space-y-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500 font-medium">Customer Photo:</span>
                      {customerPhoto ? (
                        <span className="text-emerald-600 font-bold flex items-center gap-1">
                          <CheckCircle className="w-3.5 h-3.5" /> Ready ({customerPhoto.name})
                        </span>
                      ) : (
                        <span className="text-amber-600 font-medium">Awaiting Upload (Step 1)</span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500 font-medium">Selected Garment:</span>
                      <span className="text-indigo-600 font-bold truncate max-w-[180px]">
                        {selectedGarment?.name || 'None'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500 font-medium">Fitting Algorithm:</span>
                      <span className="text-slate-700 font-mono">Fashn / IDM-VTON API</span>
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
