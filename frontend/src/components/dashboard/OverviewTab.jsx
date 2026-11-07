import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Package,
  Shirt,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  Plus,
  CheckCircle,
  Tag,
  ArrowRight,
  Eye,
  Edit2,
  Trash2,
  Search,
  Database,
  X,
} from 'lucide-react';

export default function OverviewTab({
  products,
  onNavigateTab,
  onAddProduct,
  onEditProduct,
  onDeleteProduct,
  initialSearch = '',
}) {
  const [searchQuery, setSearchQuery] = useState(initialSearch);

  // Compute summary stats dynamically from live products state
  const totalCount = products.length;
  const formalCount = products.filter((p) => p.category === 'Formal').length;
  const casualCount = products.filter((p) => p.category === 'Casual').length;
  const ethnicCount = products.filter((p) => p.category === 'Ethnic').length;
  const outerwearCount = products.filter((p) => p.category === 'Outerwear').length;
  const inStockCount = products.filter((p) => p.status === 'In Stock').length;
  const lowStockCount = products.filter((p) => p.status === 'Low Stock').length;
  const outOfStockCount = products.filter((p) => p.status === 'Out of Stock').length;

  const totalInventoryValue = products.reduce((acc, p) => {
    const numeric =
      typeof p.price === 'number'
        ? p.price
        : parseInt(String(p.price).replace(/[^\d]/g, ''), 10) || 0;
    return acc + numeric;
  }, 0);

  // Filter products for the recent section if search query is entered
  const displayedProducts = searchQuery.trim()
    ? products.filter(
        (p) =>
          p.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.category?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.colors?.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : [...products].slice(0, 5);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Welcome & Quick Actions Hero Bar */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-md border border-slate-800 space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-2.5 max-w-2xl">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Retailer Management Hub</span>
              </span>

              {/* AI Status Corrected: AI Integration Pending */}
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-400/30 text-amber-300 text-[11px] font-bold uppercase tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                AI Integration Pending
              </span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Store Catalogue & Inventory
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Manage your clothing inventory, monitor category distribution, and configure products ready for catalogue indexing and future virtual try-on.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-300 bg-slate-800/70 border border-slate-700/70 px-4 py-2.5 rounded-2xl shrink-0 self-start lg:self-center shadow-inner">
            <span className="font-semibold text-white">{totalCount} Garments</span>
            <span className="text-slate-600">•</span>
            <span className="text-emerald-400 font-medium">{inStockCount} In Stock</span>
            <span className="text-slate-600">•</span>
            <span className="font-mono text-slate-300">₹{totalInventoryValue.toLocaleString('en-IN')} Total</span>
          </div>
        </div>

        {/* Horizontal Toolbar: Wide Search Input + Large Prominent Add Product Button */}
        <div className="pt-5 border-t border-slate-800/80 flex flex-col sm:flex-row items-stretch sm:items-center gap-3.5 w-full">
          {/* Wide & Responsive Search Input */}
          <div className="relative flex-1 w-full">
            <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search products by name, category, or colour..."
              className="w-full pl-11 pr-10 py-3.5 text-sm rounded-2xl bg-slate-800/90 border border-slate-700 text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/60 focus:border-indigo-400 transition-all shadow-inner"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="p-1.5 text-slate-400 hover:text-white absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer rounded-full hover:bg-slate-700/60 transition-colors"
                aria-label="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Large, Prominent Add Product Button */}
          <button
            type="button"
            onClick={onAddProduct}
            className="group relative inline-flex items-center justify-center gap-2.5 px-6 sm:px-7 py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-sm tracking-wide shadow-lg shadow-indigo-600/30 hover:shadow-indigo-600/45 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 cursor-pointer shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <Plus className="w-5 h-5 text-white stroke-[2.5] transition-transform duration-200 group-hover:rotate-90" />
            <span>Add Product</span>
          </button>
        </div>
      </div>

      {/* Demo Data Notice Banner */}
      <div className="rounded-2xl bg-amber-50/80 border border-amber-200/90 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-amber-900 text-xs shadow-2xs">
        <div className="flex items-center gap-2.5">
          <Database className="w-4 h-4 text-amber-600 shrink-0" />
          <p>
            <strong>Demo Data Notice:</strong> You are viewing sample garment catalogue data stored in local React state. Added, edited, and deleted items update dynamically during your active session.
          </p>
        </div>
        <span className="px-2.5 py-0.5 rounded-md bg-amber-100 text-amber-800 text-[10px] font-bold uppercase tracking-wider shrink-0 border border-amber-200">
          Local React State
        </span>
      </div>

      {/* Summary Cards Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <Tag className="w-4 h-4 text-indigo-600" />
            <span>Category Breakdown & Dynamic Inventory Metrics</span>
          </h3>
          <span className="text-xs text-slate-500 font-mono">
            {totalCount} Total Items
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Total Products */}
          <div className="rounded-2xl bg-white border border-slate-200/90 p-5 shadow-2xs hover:shadow-md transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-500">Total Products</span>
              <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Package className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-slate-900">{totalCount}</span>
              <span className="text-xs font-semibold text-emerald-600 flex items-center gap-0.5">
                <CheckCircle className="w-3.5 h-3.5" /> {inStockCount} In Stock
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-2">
              Total Value: <strong className="text-slate-700">₹{totalInventoryValue.toLocaleString('en-IN')}</strong>
            </p>
          </div>

          {/* Card 2: Formal Wear */}
          <div className="rounded-2xl bg-white border border-slate-200/90 p-5 shadow-2xs hover:shadow-md transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-500">Formal Wear</span>
              <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                <Shirt className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-slate-900">{formalCount}</span>
              <span className="text-xs text-slate-500">
                {totalCount ? Math.round((formalCount / totalCount) * 100) : 0}% of inventory
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-2">Blazers, 2-piece suits, formal trousers</p>
          </div>

          {/* Card 3: Casual Wear */}
          <div className="rounded-2xl bg-white border border-slate-200/90 p-5 shadow-2xs hover:shadow-md transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-500">Casual Wear</span>
              <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-slate-900">{casualCount}</span>
              <span className="text-xs text-slate-500">
                {totalCount ? Math.round((casualCount / totalCount) * 100) : 0}% of inventory
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-2">Linen camp shirts, knit sweaters, tees</p>
          </div>

          {/* Card 4: Ethnic Wear */}
          <div className="rounded-2xl bg-white border border-slate-200/90 p-5 shadow-2xs hover:shadow-md transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-500">Ethnic Wear</span>
              <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-black text-slate-900">{ethnicCount}</span>
              <span className="text-xs text-slate-500">
                {totalCount ? Math.round((ethnicCount / totalCount) * 100) : 0}% of inventory
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-2">Embroidered kurtas, silk sherwanis</p>
          </div>
        </div>

        {/* Secondary metrics bar: Outerwear, Low Stock, Status */}
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 flex items-center justify-between">
            <span className="text-slate-600 font-medium">Outerwear:</span>
            <span className="font-bold text-slate-900">{outerwearCount} garments</span>
          </div>
          <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 flex items-center justify-between text-amber-900">
            <span className="flex items-center gap-1.5 font-medium">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> Low Stock:
            </span>
            <span className="font-bold">{lowStockCount} garments</span>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 flex items-center justify-between">
            <span className="text-slate-600 font-medium">Out of Stock:</span>
            <span className={`font-bold ${outOfStockCount > 0 ? 'text-rose-600' : 'text-slate-700'}`}>
              {outOfStockCount} garments
            </span>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 flex items-center justify-between">
            <span className="text-slate-600 font-medium">Catalogue:</span>
            <span className="inline-flex items-center gap-1.5 font-bold text-indigo-700">
              <span>Ready</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold uppercase">
                AI Pending
              </span>
            </span>
          </div>
        </div>
      </div>

      {/* Recent / Filtered Products Section */}
      <div className="rounded-3xl bg-white border border-slate-200/90 p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-slate-900">
                {searchQuery.trim() ? `Search Results for "${searchQuery}"` : 'Recently Updated Garments'}
              </h3>
              {searchQuery.trim() && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-bold border border-indigo-200">
                  {displayedProducts.length} matches
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500">
              {searchQuery.trim()
                ? 'Garments matching your search query'
                : 'Latest active items in your store catalogue'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="text-xs font-semibold text-slate-500 hover:text-slate-800 cursor-pointer"
              >
                Clear Search
              </button>
            )}
            <button
              type="button"
              onClick={() => onNavigateTab('products')}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1 cursor-pointer"
            >
              <span>Manage All ({totalCount})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {displayedProducts.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <p className="text-xs">No garments found matching "{searchQuery}".</p>
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="mt-2 text-xs font-semibold text-indigo-600 hover:underline cursor-pointer"
            >
              Show all garments
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Garment</th>
                  <th className="py-3 px-3">Category</th>
                  <th className="py-3 px-3">Price</th>
                  <th className="py-3 px-3">Sizes</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedProducts.map((garment) => {
                  const numericPrice =
                    typeof garment.price === 'number'
                      ? garment.price
                      : parseInt(String(garment.price).replace(/[^\d]/g, ''), 10) || 0;

                  const isDemoItem = garment.id?.startsWith('garment-') && !garment.id?.startsWith('garment-17');

                  return (
                    <tr key={garment.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl overflow-hidden bg-slate-100 shrink-0 border border-slate-200">
                          {garment.image ? (
                            <img
                              src={garment.image}
                              alt={garment.name}
                              className="w-full h-full object-cover object-top"
                            />
                          ) : (
                            <div className="w-full h-full bg-indigo-50 flex items-center justify-center text-indigo-600">
                              <Shirt className="w-5 h-5" />
                            </div>
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className="font-bold text-slate-900 truncate max-w-[200px]">
                              {garment.name}
                            </p>
                            {isDemoItem && (
                              <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-500 font-semibold border border-slate-200">
                                Demo
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-400 truncate max-w-[200px]">
                            {garment.fit || 'Regular Fit'} • {garment.colors?.join(', ') || 'Standard'}
                          </p>
                        </div>
                      </td>

                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-medium">
                          {garment.category}
                        </span>
                      </td>

                      <td className="py-3 px-3 font-bold text-slate-900">
                        ₹{numericPrice.toLocaleString('en-IN')}
                      </td>

                      <td className="py-3 px-3">
                        <span className="text-[11px] text-slate-500">
                          {Array.isArray(garment.sizes) ? garment.sizes.join(', ') : 'S, M, L, XL'}
                        </span>
                      </td>

                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            garment.status === 'In Stock'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : garment.status === 'Low Stock'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          {garment.status || 'In Stock'}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            to={`/try-on?garment=${garment.id}`}
                            className="p-1.5 hover:bg-indigo-50 rounded-lg text-slate-500 hover:text-indigo-600 transition-colors"
                            title="Preview in Try-On Studio"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          <button
                            type="button"
                            onClick={() => onEditProduct(garment)}
                            className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
                            title="Edit Garment"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => onDeleteProduct(garment.id)}
                            className="p-1.5 hover:bg-rose-50 rounded-lg text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                            title="Delete Garment"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
