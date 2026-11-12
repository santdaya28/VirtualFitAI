import React, { useEffect } from 'react';
import { X, Sparkles, Shirt, Tag, CheckCircle2, AlertCircle } from 'lucide-react';
import Button from './Button';

/**
 * Formats a given price value into Indian Rupee (₹) format.
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

export default function ProductDetailsModal({ isOpen, onClose, product, shopSlug = null }) {
  // Close on Escape key press
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !product) return null;

  const formattedPrice = formatRupeePrice(product.price);
  const isInStock = product.status !== 'Out of Stock' && product.is_available !== false;
  const isLowStock = product.status === 'Low Stock';
  const tryOnPath = shopSlug
    ? `/store/${shopSlug}/try-on?garment=${product.id}`
    : `/try-on?garment=${product.id}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/70 backdrop-blur-xs animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden max-h-[90vh] flex flex-col sm:flex-row"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-2 rounded-full bg-slate-900/40 text-white hover:bg-slate-900/70 transition-colors backdrop-blur-xs cursor-pointer"
          aria-label="Close dialog"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Product Image Column */}
        <div className="sm:w-1/2 relative bg-slate-100 aspect-4/5 sm:aspect-auto overflow-hidden">
          {product.image ? (
            <img
              src={product.image}
              alt={product.name}
              className="w-full h-full object-cover object-top"
            />
          ) : (
            <div
              className={`w-full h-full bg-gradient-to-tr ${
                product.fallbackBg || 'from-indigo-900 to-slate-900'
              } flex flex-col items-center justify-center text-white/80 p-6`}
            >
              <Shirt className="w-16 h-16 mb-2 opacity-80" />
              <span className="text-xs font-semibold text-center">{product.name}</span>
            </div>
          )}

          {/* Category Badge */}
          {product.category && (
            <span className="absolute top-4 left-4 text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full bg-slate-900/80 backdrop-blur-md text-white">
              {product.category}
            </span>
          )}
        </div>

        {/* Product Details Column */}
        <div className="sm:w-1/2 p-6 sm:p-7 flex flex-col justify-between overflow-y-auto">
          <div className="space-y-4">
            {/* Header: Status and Price */}
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <span
                  className={`inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                    !isInStock
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : isLowStock
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {isInStock ? (
                    <CheckCircle2 className="w-3 h-3" />
                  ) : (
                    <AlertCircle className="w-3 h-3" />
                  )}
                  {product.status || (isInStock ? 'In Stock' : 'Out of Stock')}
                </span>
                <span className="font-mono text-xs text-slate-400">ID #{product.id}</span>
              </div>

              <h2 className="text-xl font-extrabold text-slate-900 tracking-tight leading-tight">
                {product.name}
              </h2>
              <div className="text-2xl font-black text-indigo-600 mt-1">
                {formattedPrice}
              </div>
            </div>

            {/* Description */}
            <div className="text-xs text-slate-600 leading-relaxed space-y-1">
              <p className="font-semibold text-slate-800">Description</p>
              <p>{product.description || 'Handcrafted luxury designer garment.'}</p>
            </div>

            {/* Sizes */}
            {Array.isArray(product.sizes) && product.sizes.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-slate-800">Available Sizes</p>
                <div className="flex flex-wrap gap-1.5">
                  {product.sizes.map((size) => (
                    <span
                      key={size}
                      className="px-2.5 py-1 text-xs font-bold rounded-lg border border-slate-200 bg-slate-50 text-slate-700"
                    >
                      {size}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Colors */}
            {Array.isArray(product.colors) && product.colors.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-slate-800">Available Colors</p>
                <div className="flex flex-wrap gap-1.5">
                  {product.colors.map((color) => (
                    <span
                      key={color}
                      className="px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 bg-slate-50 text-slate-700 flex items-center gap-1"
                    >
                      <Tag className="w-3 h-3 text-slate-400" />
                      {color}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Action CTAs */}
          <div className="pt-6 mt-6 border-t border-slate-100 flex flex-col gap-2.5">
            <Button
              to={tryOnPath}
              variant="primary"
              size="md"
              leftIcon={Sparkles}
              className="w-full justify-center"
              onClick={onClose}
            >
              Start Virtual Fitting
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-center"
              onClick={onClose}
            >
              Continue Browsing
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
