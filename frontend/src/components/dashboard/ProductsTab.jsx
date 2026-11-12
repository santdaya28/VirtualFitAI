import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  Shirt,
  Edit2,
  Trash2,
  Eye,
  RotateCcw,
  ToggleLeft,
  ToggleRight,
  Plus,
} from 'lucide-react';
import Button from '../Button';

export default function ProductsTab({
  products,
  onEditProduct,
  onDeleteProduct,
  onToggleAvailability,
  onAddProduct,
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedStatus, setSelectedStatus] = useState('All');

  const categories = ['All', 'Formal', 'Casual', 'Ethnic', 'Outerwear'];
  const statuses = ['All', 'In Stock', 'Low Stock', 'Out of Stock'];

  // Filter products based on search, category, and status
  const filteredProducts = products.filter((product) => {
    const matchesSearch =
      searchTerm.trim() === '' ||
      product.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      product.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      product.colors?.some((c) => c.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesCategory =
      selectedCategory === 'All' || product.category === selectedCategory;

    const matchesStatus =
      selectedStatus === 'All' || product.status === selectedStatus;

    return matchesSearch && matchesCategory && matchesStatus;
  });

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedCategory('All');
    setSelectedStatus('All');
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Header */}
      <div className="pb-3 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            Product Management
          </h2>
          <p className="text-xs sm:text-sm text-slate-500">
            View, search, edit, and organize clothing items in your retail catalogue.
          </p>
        </div>
        {onAddProduct && (
          <Button variant="primary" size="sm" leftIcon={Plus} onClick={onAddProduct}>
            Add Product
          </Button>
        )}
      </div>

      {/* Search & Filter Controls Bar */}
      <div className="rounded-2xl bg-white border border-slate-200/90 p-4 shadow-2xs space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          {/* Search Input */}
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search garments..."
              className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900 placeholder:text-slate-400"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="text-xs text-slate-400 hover:text-slate-600 absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          {/* Category Filter Pills */}
          <div className="md:col-span-5 flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all shrink-0 cursor-pointer ${
                  selectedCategory === cat
                    ? 'bg-indigo-600 text-white shadow-2xs font-semibold'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Status Dropdown Filter */}
          <div className="md:col-span-2">
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-700 cursor-pointer"
            >
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {s === 'All' ? 'All Statuses' : s}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Active Filter Summary Indicator */}
        {(searchTerm || selectedCategory !== 'All' || selectedStatus !== 'All') && (
          <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs text-slate-500">
            <span>
              Showing <strong>{filteredProducts.length}</strong> of {products.length} products
            </span>
            <button
              type="button"
              onClick={clearFilters}
              className="text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1 cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" /> Reset Filters
            </button>
          </div>
        )}
      </div>

      {/* Products Table or Empty State */}
      {filteredProducts.length === 0 ? (
        <div className="rounded-3xl bg-white border border-slate-200 p-12 text-center max-w-md mx-auto shadow-xs">
          <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-3">
            <Shirt className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-900 mb-1">No products match your criteria</h3>
          <p className="text-xs text-slate-500 mb-5">
            Try adjusting your search terms or filter selections.
          </p>
          <Button variant="outline" size="sm" leftIcon={RotateCcw} onClick={clearFilters}>
            Reset Filters
          </Button>
        </div>
      ) : (
        <div className="rounded-3xl bg-white border border-slate-200/90 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-3.5 px-4">Garment</th>
                  <th className="py-3.5 px-3">Category</th>
                  <th className="py-3.5 px-3">Price (₹)</th>
                  <th className="py-3.5 px-3">Sizes</th>
                  <th className="py-3.5 px-3">Colours</th>
                  <th className="py-3.5 px-3">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredProducts.map((garment) => {
                  const numericPrice = typeof garment.price === 'number'
                    ? garment.price
                    : parseInt(String(garment.price).replace(/[^\d]/g, ''), 10) || 0;

                  return (
                    <tr key={garment.id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Product Thumbnail & Details */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 rounded-xl overflow-hidden bg-slate-100 shrink-0 border border-slate-200">
                            {garment.image ? (
                              <img
                                src={garment.image}
                                alt={garment.name}
                                className="w-full h-full object-cover object-top"
                              />
                            ) : (
                              <div className="w-full h-full bg-indigo-50 flex items-center justify-center text-indigo-600">
                                <Shirt className="w-6 h-6" />
                              </div>
                            )}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <p className="font-bold text-slate-900 truncate max-w-[200px]">
                                {garment.name}
                              </p>
                              {typeof garment.id === 'string' &&
                                garment.id.startsWith('garment-') &&
                                !garment.id.startsWith('garment-17') && (
                                <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-500 font-semibold border border-slate-200">
                                  Demo
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-500 line-clamp-1 max-w-[240px]">
                              {garment.description || 'Premium store garment'}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* Category */}
                      <td className="py-3.5 px-3">
                        <span className="px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 font-semibold text-[11px]">
                          {garment.category}
                        </span>
                      </td>

                      {/* Price in ₹ */}
                      <td className="py-3.5 px-3 font-extrabold text-slate-900 text-sm">
                        ₹{numericPrice.toLocaleString('en-IN')}
                      </td>

                      {/* Sizes */}
                      <td className="py-3.5 px-3">
                        <div className="flex flex-wrap gap-1 max-w-[130px]">
                          {Array.isArray(garment.sizes) && garment.sizes.length > 0 ? (
                            garment.sizes.map((s) => (
                              <span
                                key={s}
                                className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px] font-mono text-slate-600"
                              >
                                {s}
                              </span>
                            ))
                          ) : (
                            <span className="text-slate-400 text-[11px]">S, M, L, XL</span>
                          )}
                        </div>
                      </td>

                      {/* Colours */}
                      <td className="py-3.5 px-3">
                        <span className="text-[11px] text-slate-600 font-medium">
                          {Array.isArray(garment.colors) ? garment.colors.join(', ') : 'Standard'}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-3">
                        <button
                          type="button"
                          onClick={() => onToggleAvailability && onToggleAvailability(garment)}
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold cursor-pointer transition-opacity hover:opacity-85 ${
                            garment.status === 'In Stock'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : garment.status === 'Low Stock'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                          title="Click to toggle availability"
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              garment.status === 'In Stock'
                                ? 'bg-emerald-500'
                                : garment.status === 'Low Stock'
                                ? 'bg-amber-500'
                                : 'bg-rose-500'
                            }`}
                          />
                          {garment.status || 'In Stock'}
                        </button>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Change Availability Action */}
                          {onToggleAvailability && (
                            <button
                              type="button"
                              onClick={() => onToggleAvailability(garment)}
                              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                                garment.is_available !== false && garment.status !== 'Out of Stock'
                                  ? 'hover:bg-emerald-50 text-emerald-600 hover:text-emerald-700'
                                  : 'hover:bg-slate-100 text-slate-400 hover:text-slate-600'
                              }`}
                              title={
                                garment.is_available !== false && garment.status !== 'Out of Stock'
                                  ? 'Change Availability: Currently Active (Click to mark Out of Stock)'
                                  : 'Change Availability: Currently Out of Stock (Click to mark Active)'
                              }
                            >
                              {garment.is_available !== false && garment.status !== 'Out of Stock' ? (
                                <ToggleRight className="w-4 h-4" />
                              ) : (
                                <ToggleLeft className="w-4 h-4" />
                              )}
                            </button>
                          )}
                          <Link
                            to={`/try-on?garment=${garment.id}`}
                            className="p-1.5 hover:bg-indigo-50 rounded-lg text-slate-500 hover:text-indigo-600 transition-colors"
                            title="Preview in Virtual Try-On Studio"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          <button
                            type="button"
                            onClick={() => onEditProduct(garment)}
                            className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
                            title="Edit Product"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => onDeleteProduct(garment.id)}
                            className="p-1.5 hover:bg-rose-50 rounded-lg text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                            title="Delete Product"
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
        </div>
      )}
    </div>
  );
}
