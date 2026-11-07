import React, { useState, useRef, useEffect } from 'react';
import {
  Upload,
  X,
  AlertCircle,
  Save,
  Shirt,
} from 'lucide-react';
import Button from '../Button';

const AVAILABLE_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'Free Size'];
const CATEGORIES = ['Formal', 'Casual', 'Ethnic', 'Outerwear'];
const STATUSES = ['In Stock', 'Low Stock', 'Out of Stock'];

export default function ProductFormModal({
  isOpen,
  initialData,
  onSave,
  onCancel,
}) {
  const isEditing = Boolean(initialData?.id);
  const fileInputRef = useRef(null);

  // Form states initialized directly
  const [prevInitialData, setPrevInitialData] = useState(initialData);
  const [name, setName] = useState(initialData?.name || '');
  const [description, setDescription] = useState(initialData?.description || '');
  const [category, setCategory] = useState(initialData?.category || 'Formal');
  const [price, setPrice] = useState(
    initialData
      ? String(
          typeof initialData.price === 'number'
            ? initialData.price
            : parseInt(String(initialData.price).replace(/[^\d]/g, ''), 10) || ''
        )
      : ''
  );
  const [sizes, setSizes] = useState(
    Array.isArray(initialData?.sizes) ? initialData.sizes : ['S', 'M', 'L', 'XL']
  );
  const [colorsInput, setColorsInput] = useState(
    Array.isArray(initialData?.colors)
      ? initialData.colors.join(', ')
      : initialData?.color || 'Navy Blue'
  );
  const [status, setStatus] = useState(initialData?.status || 'In Stock');
  const [imageUrl, setImageUrl] = useState(initialData?.image || '');
  const [uploadedImagePreview, setUploadedImagePreview] = useState(null);
  const [formErrors, setFormErrors] = useState({});

  // Sync state during render when initialData changes (React 19 recommended pattern)
  if (initialData !== prevInitialData) {
    setPrevInitialData(initialData);
    if (initialData) {
      setName(initialData.name || '');
      setDescription(initialData.description || '');
      setCategory(initialData.category || 'Formal');
      const numericPrice =
        typeof initialData.price === 'number'
          ? initialData.price
          : parseInt(String(initialData.price).replace(/[^\d]/g, ''), 10) || '';
      setPrice(String(numericPrice));
      setSizes(Array.isArray(initialData.sizes) ? initialData.sizes : ['M', 'L']);
      setColorsInput(
        Array.isArray(initialData.colors)
          ? initialData.colors.join(', ')
          : initialData.color || 'Standard'
      );
      setStatus(initialData.status || 'In Stock');
      setImageUrl(initialData.image || '');
      setUploadedImagePreview(null);
    } else {
      setName('');
      setDescription('');
      setCategory('Formal');
      setPrice('');
      setSizes(['S', 'M', 'L', 'XL']);
      setColorsInput('Navy Blue');
      setStatus('In Stock');
      setImageUrl('');
      setUploadedImagePreview(null);
    }
    setFormErrors({});
  }

  // Clean up created object URL on unmount or change
  useEffect(() => {
    return () => {
      if (uploadedImagePreview) {
        URL.revokeObjectURL(uploadedImagePreview);
      }
    };
  }, [uploadedImagePreview]);

  if (!isOpen) return null;

  // Toggle size pill
  const handleToggleSize = (size) => {
    setSizes((prev) =>
      prev.includes(size) ? prev.filter((s) => s !== size) : [...prev, size]
    );
  };

  // Handle local image file upload
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      setFormErrors((prev) => ({
        ...prev,
        image: 'Please upload a valid image file (JPG, PNG, or WebP).',
      }));
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setFormErrors((prev) => ({
        ...prev,
        image: 'Image size exceeds 10 MB limit.',
      }));
      return;
    }

    if (uploadedImagePreview) {
      URL.revokeObjectURL(uploadedImagePreview);
    }

    const preview = URL.createObjectURL(file);
    setUploadedImagePreview(preview);
    setImageUrl('');
    setFormErrors((prev) => ({ ...prev, image: null }));
    e.target.value = '';
  };

  const handleRemoveImage = () => {
    if (uploadedImagePreview) {
      URL.revokeObjectURL(uploadedImagePreview);
    }
    setUploadedImagePreview(null);
    setImageUrl('');
  };

  // Validate and submit
  const handleSubmit = (e) => {
    e.preventDefault();
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

    if (!sizes || sizes.length === 0) {
      errors.sizes = 'Please select at least one available size.';
    }

    const activeImage = uploadedImagePreview || imageUrl;
    if (!activeImage) {
      errors.image = 'Please upload a garment photo or provide an image URL.';
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    // Parse colors from comma-separated input
    const parsedColors = colorsInput
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    const garmentData = {
      id: initialData?.id || `garment-${Date.now()}`,
      name: name.trim(),
      description: description.trim(),
      category,
      price: parsedPrice,
      sizes,
      colors: parsedColors.length > 0 ? parsedColors : ['Multi-Color'],
      status,
      image: activeImage,
      fallbackBg: initialData?.fallbackBg || 'from-indigo-900 to-slate-900',
      createdAt: initialData?.createdAt || new Date().toISOString().split('T')[0],
    };

    onSave(garmentData);
  };

  const currentDisplayImage = uploadedImagePreview || imageUrl;

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
                  ? 'Update product attributes, sizes, and pricing.'
                  : 'Enter garment specifications to display in your store and try-on studio.'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="p-1.5 hover:bg-slate-200/70 rounded-full text-slate-500 hover:text-slate-700 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {/* General Errors Banner */}
          {Object.keys(formErrors).length > 0 && (
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
                } focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500`}
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

          {/* Row 2: Price in ₹ & Product Status */}
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
                  } focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500`}
                />
              </div>
              {formErrors.price && (
                <p className="text-[11px] text-rose-600">{formErrors.price}</p>
              )}
            </div>

            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-700">Inventory Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 cursor-pointer text-slate-800"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-1">
            <label className="block text-xs font-bold text-slate-700">Garment Description</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Structured lightweight wool-blend blazer tailored for modern business and evening wear."
              className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>

          {/* Row 3: Available Sizes */}
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
              className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>

          {/* Product Image Upload with Preview */}
          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700">
              Product Image <span className="text-rose-500">*</span>
            </label>

            {currentDisplayImage ? (
              <div className="relative rounded-2xl border border-slate-200 bg-slate-100 p-2 max-w-sm flex items-center gap-3">
                <div className="w-16 h-16 rounded-xl overflow-hidden bg-slate-200 shrink-0">
                  <img
                    src={currentDisplayImage}
                    alt="Preview"
                    className="w-full h-full object-cover object-top"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-slate-900 truncate">
                    {uploadedImagePreview ? 'Local Image Loaded' : 'Web URL Linked'}
                  </p>
                  <p className="text-[11px] text-slate-500">Preview ready for catalogue & try-on</p>
                </div>
                <button
                  type="button"
                  onClick={handleRemoveImage}
                  className="p-1.5 hover:bg-rose-100 rounded-lg text-rose-600 transition-colors cursor-pointer"
                  title="Remove Image"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Drag & Drop Upload Zone */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-300 hover:border-indigo-400 rounded-2xl p-4 text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-indigo-50/20"
                >
                  <Upload className="w-6 h-6 text-indigo-600 mx-auto mb-1.5" />
                  <p className="text-xs font-bold text-slate-800">
                    Click to browse photo from computer
                  </p>
                  <p className="text-[11px] text-slate-500">JPG, PNG, or WebP (Max 10 MB)</p>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {/* Alternative URL Input */}
                <div className="relative">
                  <input
                    type="url"
                    value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                    placeholder="Or paste an image URL (https://...)"
                    className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              </div>
            )}
            {formErrors.image && (
              <p className="text-[11px] text-rose-600">{formErrors.image}</p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
            <Button variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" leftIcon={Save} type="submit">
              {isEditing ? 'Save Changes' : 'Add to Catalogue'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
