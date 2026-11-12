import React, { useState, useRef, useEffect } from 'react';
import {
  Upload,
  X,
  AlertCircle,
  Save,
  Shirt,
  RefreshCw,
  Undo2,
} from 'lucide-react';
import Button from '../Button';
import { uploadProductImage } from '../../services/api';

const AVAILABLE_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'Free Size'];
const CATEGORIES = ['Formal', 'Casual', 'Ethnic', 'Outerwear'];

export default function ProductFormModal({
  isOpen,
  initialData,
  onSave,
  onCancel,
}) {
  if (!isOpen) return null;

  const modalKey = initialData?.id ? `edit-${initialData.id}` : 'create-new';

  return (
    <ProductFormModalContent
      key={modalKey}
      initialData={initialData}
      onSave={onSave}
      onCancel={onCancel}
    />
  );
}

function ProductFormModalContent({
  initialData,
  onSave,
  onCancel,
}) {
  const isEditing = Boolean(initialData?.id);
  const fileInputRef = useRef(null);
  const formRef = useRef(null);
  const submitLockRef = useRef(false);

  // Form states tracking (initialized fresh on every modal open/remount)
  const [name, setName] = useState(initialData?.name || initialData?.product_name || '');
  const [description, setDescription] = useState(initialData?.description || '');
  const [category, setCategory] = useState(initialData?.category || 'Formal');
  const [price, setPrice] = useState(
    initialData
      ? String(
          typeof initialData.price === 'number'
            ? initialData.price
            : parseFloat(String(initialData.price).replace(/[^\d.]/g, '')) || ''
        )
      : ''
  );
  const [stockQuantity, setStockQuantity] = useState(
    initialData?.stock_quantity !== undefined && initialData?.stock_quantity !== null
      ? String(initialData.stock_quantity)
      : '25'
  );
  const [isAvailable, setIsAvailable] = useState(
    initialData?.is_available !== undefined
      ? Boolean(initialData.is_available)
      : initialData?.status !== 'Out of Stock'
  );
  const [sizes, setSizes] = useState(
    Array.isArray(initialData?.sizes) && initialData.sizes.length > 0
      ? initialData.sizes
      : ['S', 'M', 'L', 'XL']
  );
  const [colorsInput, setColorsInput] = useState(
    Array.isArray(initialData?.colors)
      ? initialData.colors.join(', ')
      : initialData?.color || 'Navy Blue'
  );

  // Image states
  const [originalImageUrl, setOriginalImageUrl] = useState(
    initialData?.image || initialData?.image_url || ''
  );
  const [manualImageUrl, setManualImageUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState(null);

  // Validation & Submission
  const [formErrors, setFormErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitPhase, setSubmitPhase] = useState('idle');

  // Cleanup object URLs on unmount or replacement
  useEffect(() => {
    return () => {
      if (filePreviewUrl) {
        URL.revokeObjectURL(filePreviewUrl);
      }
    };
  }, [filePreviewUrl]);

  // Toggle size pill
  const handleToggleSize = (size) => {
    setSizes((prev) =>
      prev.includes(size) ? prev.filter((s) => s !== size) : [...prev, size]
    );
  };

  // Handle local image file selection
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate type against allowed image formats
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
    if (!hasValidExt && !hasValidMime) {
      e.target.value = '';
      setFormErrors((prev) => ({
        ...prev,
        image: 'Please select a valid image file (JPG, JPEG, PNG, or WebP).',
      }));
      return;
    }
    if (mimeLower && !hasValidMime) {
      e.target.value = '';
      setFormErrors((prev) => ({
        ...prev,
        image: `Unsupported file type (${file.type}). Only JPG, JPEG, PNG, and WebP images are supported.`,
      }));
      return;
    }

    // Validate size (5 MB limit)
    const MAX_SIZE = 5 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      e.target.value = '';
      const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
      setFormErrors((prev) => ({
        ...prev,
        image: `Image size (${sizeMb} MB) exceeds maximum allowed limit of 5 MB.`,
      }));
      return;
    }

    if (filePreviewUrl) {
      URL.revokeObjectURL(filePreviewUrl);
    }

    const preview = URL.createObjectURL(file);
    setSelectedFile(file);
    setFilePreviewUrl(preview);
    setManualImageUrl('');
    setFormErrors((prev) => ({ ...prev, image: null, submit: null }));
    e.target.value = '';
  };

  // Cancel replacement and revert to original image
  const handleCancelReplacement = () => {
    if (filePreviewUrl) {
      URL.revokeObjectURL(filePreviewUrl);
    }
    setSelectedFile(null);
    setFilePreviewUrl(null);
    setFormErrors((prev) => ({ ...prev, image: null }));
  };

  // Remove all images (clear)
  const handleRemoveImage = () => {
    if (filePreviewUrl) {
      URL.revokeObjectURL(filePreviewUrl);
    }
    setSelectedFile(null);
    setFilePreviewUrl(null);
    setOriginalImageUrl('');
    setManualImageUrl('');
  };

  // Validate and submit
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitLockRef.current || isSubmitting) {
      return;
    }

    const errors = {};

    if (!name.trim()) {
      errors.name = 'Garment name is required (min 3 characters).';
    } else if (name.trim().length < 3) {
      errors.name = 'Name must be at least 3 characters.';
    }

    const parsedPrice = parseFloat(price);
    if (!price || isNaN(parsedPrice) || parsedPrice <= 0) {
      errors.price = 'Please enter a valid positive price in ₹.';
    }

    const parsedStock = parseInt(stockQuantity, 10);
    if (stockQuantity === '' || isNaN(parsedStock) || parsedStock < 0) {
      errors.stockQuantity = 'Please enter a valid stock quantity (0 or greater).';
    }

    if (!sizes || sizes.length === 0) {
      errors.sizes = 'Please select at least one available size.';
    } else if (sizes.join(', ').length > 255) {
      errors.sizes = 'Selected sizes summary exceeds 255 characters.';
    }

    // Parse colors from comma-separated input
    const parsedColors = colorsInput
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    if (parsedColors.join(', ').length > 255) {
      errors.colors = 'Available colours list must be 255 characters or fewer.';
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      formRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    // Compute status badge
    let statusBadge = 'In Stock';
    if (!isAvailable || parsedStock === 0) {
      statusBadge = 'Out of Stock';
    } else if (parsedStock <= 5) {
      statusBadge = 'Low Stock';
    } else {
      statusBadge = 'In Stock';
    }

    submitLockRef.current = true;
    setIsSubmitting(true);
    setSubmitPhase(selectedFile ? 'uploading' : 'saving');
    setFormErrors({});

    try {
      let finalImageUrl = originalImageUrl || null;

      // 1. If a new image file was selected from disk, upload to backend static storage first
      if (selectedFile) {
        setSubmitPhase('uploading');
        const uploadResult = await uploadProductImage(selectedFile);
        if (!uploadResult?.image_url) {
          throw new Error('Image upload succeeded but did not return an image URL.');
        }
        finalImageUrl = uploadResult.image_url;
      } else if (manualImageUrl.trim()) {
        finalImageUrl = manualImageUrl.trim();
      }

      // 2. Prepare complete garment payload
      const garmentData = {
        ...(initialData?.id && { id: initialData.id }),
        ...(initialData?.shop_id && { shop_id: initialData.shop_id }),
        name: name.trim(),
        product_name: name.trim(),
        description: description.trim(),
        category,
        price: parsedPrice,
        stock_quantity: parsedStock,
        is_available: Boolean(isAvailable),
        status: statusBadge,
        sizes,
        colors: parsedColors.length > 0 ? parsedColors : ['Standard'],
        image: finalImageUrl,
        image_url: finalImageUrl,
        fallbackBg: initialData?.fallbackBg || 'from-indigo-900 to-slate-900',
        createdAt: initialData?.createdAt || new Date().toISOString().split('T')[0],
      };

      // 3. Dispatch to parent onSave handler and wait for backend DB persistence
      setSubmitPhase('saving');
      await onSave(garmentData);
    } catch (err) {
      console.error('Failed to save product in modal:', err);
      setFormErrors({ submit: err?.message || 'Failed to save product to backend.' });
      formRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
      submitLockRef.current = false;
      setIsSubmitting(false);
      setSubmitPhase('idle');
    }
  };

  // Determine which image preview to show
  const hasReplacementSelected = Boolean(selectedFile && filePreviewUrl);
  const activeDisplayImage = filePreviewUrl || manualImageUrl || originalImageUrl;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto animate-fadeIn">
      <div className="relative w-full max-w-2xl bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/60">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Shirt className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {isEditing ? 'Edit Garment Details' : 'Add New Garment to Catalogue'}
              </h3>
              <p className="text-[11px] text-slate-500">
                {isEditing
                  ? `Update product attributes, stock count, and availability for #${initialData?.id || ''}.`
                  : 'Enter garment specifications to display in your store catalogue and try-on studio.'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="p-1.5 hover:bg-slate-200/70 rounded-full text-slate-500 hover:text-slate-700 transition-colors cursor-pointer disabled:opacity-50"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form ref={formRef} onSubmit={handleSubmit} className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {/* General Submit Error Banner */}
          {formErrors.submit && (
            <div
              role="alert"
              className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2.5"
            >
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{formErrors.submit}</span>
            </div>
          )}

          {/* Validation Notice Banner */}
          {Object.keys(formErrors).length > 0 && !formErrors.submit && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Please correct the highlighted fields before saving.</span>
            </div>
          )}

          {/* Row 1: Name and Category */}
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-4">
            <div className="sm:col-span-8 space-y-1">
              <label className="block text-xs font-bold text-slate-700">
                Garment Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Midnight Navy Slim Blazer"
                className={`w-full px-3.5 py-2 text-xs rounded-xl border ${
                  formErrors.name ? 'border-rose-400 bg-rose-50/30' : 'border-slate-200 bg-white'
                } focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900`}
              />
              {formErrors.name && (
                <p className="text-[11px] text-rose-600">{formErrors.name}</p>
              )}
            </div>

            <div className="sm:col-span-4 space-y-1">
              <label className="block text-xs font-bold text-slate-700">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 cursor-pointer text-slate-800"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: Price in ₹ & Stock Quantity */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-700">
                Price (in Indian Rupees ₹) <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-400">
                  ₹
                </span>
                <input
                  type="number"
                  step="1"
                  min="0"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="3499"
                  className={`w-full pl-7 pr-3 py-2 text-xs rounded-xl border ${
                    formErrors.price ? 'border-rose-400 bg-rose-50/30' : 'border-slate-200 bg-white'
                  } focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900`}
                />
              </div>
              {formErrors.price && (
                <p className="text-[11px] text-rose-600">{formErrors.price}</p>
              )}
            </div>

            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-700">
                Stock Quantity (Units) <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                step="1"
                min="0"
                value={stockQuantity}
                onChange={(e) => setStockQuantity(e.target.value)}
                placeholder="25"
                className={`w-full px-3.5 py-2 text-xs rounded-xl border ${
                  formErrors.stockQuantity ? 'border-rose-400 bg-rose-50/30' : 'border-slate-200 bg-white'
                } focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900`}
              />
              {formErrors.stockQuantity && (
                <p className="text-[11px] text-rose-600">{formErrors.stockQuantity}</p>
              )}
            </div>
          </div>

          {/* Row 3: Availability Toggle Box */}
          <div className="p-3.5 rounded-2xl border border-slate-200 bg-slate-50/60 flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-800">
                  Catalogue & Try-On Availability
                </span>
                <span
                  className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full ${
                    isAvailable && parseInt(stockQuantity, 10) > 0
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                      : 'bg-rose-100 text-rose-800 border border-rose-200'
                  }`}
                >
                  {isAvailable && parseInt(stockQuantity, 10) > 0 ? 'Active / In Stock' : 'Unavailable'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                When enabled, customers can view this garment in the catalogue and try it on in VirtualFit AI.
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={isAvailable}
                onChange={(e) => setIsAvailable(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600" />
            </label>
          </div>

          {/* Description */}
          <div className="space-y-1">
            <label className="block text-xs font-bold text-slate-700">Garment Description</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Structured lightweight wool-blend blazer tailored for modern business and evening wear."
              className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
            />
          </div>

          {/* Row 4: Available Sizes */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-slate-700">
              Available Sizes <span className="text-rose-500">*</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_SIZES.map((size) => {
                const isSelected = sizes.includes(size);
                return (
                  <button
                    key={size}
                    type="button"
                    onClick={() => handleToggleSize(size)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-600 text-white shadow-2xs'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {size}
                  </button>
                );
              })}
            </div>
            {formErrors.sizes && (
              <p className="text-[11px] text-rose-600">{formErrors.sizes}</p>
            )}
          </div>

          {/* Available Colours */}
          <div className="space-y-1">
            <label className="block text-xs font-bold text-slate-700">
              Available Colours (Comma Separated)
            </label>
            <input
              type="text"
              value={colorsInput}
              onChange={(e) => setColorsInput(e.target.value)}
              placeholder="e.g. Navy Blue, Midnight Charcoal, Slate Grey"
              className={`w-full px-3.5 py-2 text-xs rounded-xl border ${
                formErrors.colors ? 'border-rose-400 bg-rose-50/30' : 'border-slate-200 bg-white'
              } focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900`}
            />
            {formErrors.colors && (
              <p className="text-[11px] text-rose-600">{formErrors.colors}</p>
            )}
          </div>

          {/* Product Image: Upload, Preview, Replace, Cancel Replacement */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-bold text-slate-700">
                Product Image <span className="text-slate-400 font-normal">(Optional)</span>
              </label>
              <span className="text-[10px] text-slate-400">JPG, JPEG, PNG, WebP • Max 5 MB</span>
            </div>

            {/* Hidden native file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileChange}
              className="hidden"
            />

            {/* Active image preview card if image is available */}
            {activeDisplayImage ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 space-y-3">
                <div className="flex items-center gap-3.5">
                  <div className="w-18 h-18 rounded-xl overflow-hidden bg-white border border-slate-200 shrink-0 shadow-2xs">
                    <img
                      src={activeDisplayImage}
                      alt="Garment Preview"
                      className="w-full h-full object-cover object-top"
                    />
                  </div>

                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900 truncate">
                        {hasReplacementSelected
                          ? 'New Image Selected'
                          : isEditing
                          ? 'Current Database Photo'
                          : 'Product Photo Ready'}
                      </span>
                      {hasReplacementSelected && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 border border-indigo-200">
                          Pending Save
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500">
                      {hasReplacementSelected
                        ? `${selectedFile?.name || 'File'} (${((selectedFile?.size || 0) / 1024).toFixed(0)} KB)`
                        : 'Saved in backend static uploads storage'}
                    </p>
                  </div>
                </div>

                {/* Replacement Action Buttons */}
                <div className="flex items-center gap-2 pt-2 border-t border-slate-200/80">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 transition-colors flex items-center gap-1.5 cursor-pointer shadow-2xs"
                  >
                    <Upload className="w-3.5 h-3.5 text-indigo-600" />
                    <span>{hasReplacementSelected ? 'Choose Different Image' : 'Replace Image'}</span>
                  </button>

                  {/* Cancel Replacement: Keeps original image */}
                  {hasReplacementSelected && originalImageUrl && (
                    <button
                      type="button"
                      onClick={handleCancelReplacement}
                      className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors flex items-center gap-1.5 cursor-pointer"
                      title="Discard selected file and keep current image"
                    >
                      <Undo2 className="w-3.5 h-3.5 text-slate-500" />
                      <span>Cancel Replacement</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={handleRemoveImage}
                    className="p-1.5 hover:bg-rose-100 rounded-xl text-rose-600 transition-colors cursor-pointer ml-auto"
                    title="Remove Image"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2.5">
                {/* Drag & Drop / Click Upload Box */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-2xl p-5 text-center cursor-pointer transition-all bg-slate-50/60 hover:bg-indigo-50/20 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-indigo-50 group-hover:bg-indigo-100 text-indigo-600 flex items-center justify-center mx-auto mb-2 transition-colors">
                    <Upload className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-bold text-slate-800">
                    Click to browse garment photo from computer
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    JPG, JPEG, PNG, or WebP (Maximum 5 MB)
                  </p>
                </div>

                {/* Alternative URL Input */}
                <div className="relative">
                  <input
                    type="url"
                    value={manualImageUrl}
                    onChange={(e) => setManualImageUrl(e.target.value)}
                    placeholder="Or enter web image URL (https://...)"
                    className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                  />
                </div>
              </div>
            )}

            {formErrors.image && (
              <p className="text-[11px] text-rose-600">{formErrors.image}</p>
            )}
          </div>

          {/* Inline Footer Error Summary so errors stay visible near Action Buttons without scrolling */}
          {(formErrors.submit ||
            formErrors.name ||
            formErrors.price ||
            formErrors.stockQuantity ||
            formErrors.sizes ||
            formErrors.colors ||
            formErrors.image) && (
            <div
              role="alert"
              data-testid="product-form-footer-error"
              className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2"
            >
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600 mt-0.5" />
              <span>
                {formErrors.submit ||
                  formErrors.name ||
                  formErrors.price ||
                  formErrors.stockQuantity ||
                  formErrors.sizes ||
                  formErrors.colors ||
                  formErrors.image}
              </span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              leftIcon={isSubmitting ? RefreshCw : Save}
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-1.5">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>
                    {submitPhase === 'uploading'
                      ? 'Uploading Image...'
                      : 'Saving to Database...'}
                  </span>
                </span>
              ) : isEditing ? (
                'Save Changes'
              ) : (
                'Add to Catalogue'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
