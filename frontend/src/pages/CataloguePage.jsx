import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  Shirt,
  Store,
  Sparkles,
  Filter,
  Database,
  RotateCcw,
  PackageSearch,
  RefreshCw,
  AlertCircle,
  Search,
  X,
  Eye,
  ArrowLeftRight,
} from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';
import ProductDetailsModal from '../components/ProductDetailsModal';
import ShopSelector from '../components/ShopSelector';
import { fetchShopBySlug, fetchStorefrontProducts } from '../services/api';

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

export default function CataloguePage() {
  const { shopSlug: routeShopSlug } = useParams();
  const [searchParams] = useSearchParams();
  const activeShopSlug = (routeShopSlug || searchParams.get('shop') || '').trim().toLowerCase();

  // Category & Search filter states
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [imageErrors, setImageErrors] = useState({});

  // Dynamic Backend Data States (strictly isolated to activeShopSlug)
  const [activeShop, setActiveShop] = useState(null);
  const [shopNotFound, setShopNotFound] = useState(false);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalProduct, setModalProduct] = useState(null);

  const categories = [
    'All',
    'Formal',
    'Casual',
    'Ethnic',
    'Outerwear',
  ];

  // Fetch products strictly for the current shop storefront slug
  const loadProducts = useCallback(async () => {
    if (!activeShopSlug) {
      setActiveShop(null);
      setShopNotFound(false);
      setProducts([]);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    setShopNotFound(false);
    setActiveCategory('All');
    setSearchQuery('');
    setModalProduct(null);

    try {
      const [shopInfo, shopProducts] = await Promise.all([
        fetchShopBySlug(activeShopSlug),
        fetchStorefrontProducts(activeShopSlug, { limit: 100 }),
      ]);
      setActiveShop(shopInfo);
      setProducts(shopProducts);
    } catch (err) {
      console.error('Failed to load storefront catalogue from backend:', err);
      setActiveShop(null);
      setProducts([]);
      if (err.status === 404) {
        setShopNotFound(true);
      }
      setError(
        err.message || 'Unable to load storefront inventory from FastAPI backend.'
      );
    } finally {
      setLoading(false);
    }
  }, [activeShopSlug]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // No storefront context selected -> show Storefront Chooser (never merge global products)
  if (!activeShopSlug) {
    return <ShopSelector mode="catalogue" />;
  }

  const resolvedSlug = activeShop?.slug || activeShopSlug;
  const storeDisplayName = activeShop?.shop_name || activeShopSlug;

  const handleImageError = (id) => {
    setImageErrors((prev) => ({ ...prev, [id]: true }));
  };

  // Filter products dynamically based on category selection and search query
  const filteredClothes = products.filter((item) => {
    const matchesCategory =
      activeCategory === 'All' || item.category === activeCategory;

    const matchesSearch =
      !searchQuery.trim() ||
      item.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (Array.isArray(item.colors) &&
        item.colors.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase())));

    return matchesCategory && matchesSearch;
  });

  return (
    <div className="pt-6 pb-16 sm:pt-10 sm:pb-20">
      <Container>
        {/* Header Section */}
        <div className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6 scroll-mt-28">
          <div className="space-y-3 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2">
              <div
                data-testid="storefront-badge"
                className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold"
              >
                <Store className="w-3.5 h-3.5" />
                <span>{storeDisplayName}</span>
              </div>
              <Link
                to="/catalogue"
                data-testid="switch-store-link"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white border border-slate-200 hover:border-indigo-300 text-slate-600 hover:text-indigo-700 text-xs font-semibold transition-colors"
              >
                <ArrowLeftRight className="w-3 h-3" />
                <span>All Stores</span>
              </Link>
            </div>
            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
              {activeShop?.shop_name ? `${activeShop.shop_name} Catalogue` : 'Boutique Collection'}
            </h1>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
              Showing only garments curated and published by <strong>{storeDisplayName}</strong>.
              Click <strong>"Try On"</strong> on any garment to launch this store&apos;s Virtual Try-On studio.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Button
              to={`/store/${resolvedSlug}/try-on`}
              variant="primary"
              size="md"
              leftIcon={Sparkles}
            >
              Open Try-On Studio
            </Button>
          </div>
        </div>

        {/* Database Status Notice */}
        <div className="mb-8 rounded-2xl bg-slate-900 text-slate-300 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border border-slate-800 shadow-md">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs text-indigo-300 font-semibold tracking-wide uppercase">
                Isolated Boutique Storefront Live
              </p>
              <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                Scoped exclusively to storefront <code className="text-indigo-300 font-mono text-[11px]">/api/shops/slug/{resolvedSlug}/products</code>. All prices are in ₹ INR.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadProducts}
              disabled={loading}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer border border-slate-700"
              title="Refresh catalogue from database"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            </button>
            <span className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 font-mono border border-slate-700 shrink-0">
              {loading ? 'Syncing...' : `${products.length} live garments`}
            </span>
          </div>
        </div>

        {/* Search & Category Filter Bar */}
        <div className="mb-8 space-y-3">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            {/* Category Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
              <span className="text-xs font-semibold text-slate-500 flex items-center gap-1 mr-1 shrink-0">
                <Filter className="w-3.5 h-3.5" /> Category:
              </span>
              {categories.map((category) => {
                const isActive = activeCategory === category;
                return (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setActiveCategory(category)}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 cursor-pointer ${
                      isActive
                        ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-xs'
                        : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {category}
                  </button>
                );
              })}
            </div>

            {/* Search Input */}
            <div className="relative md:w-64">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search catalogue..."
                className="w-full pl-8 pr-7 py-1.5 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900 placeholder:text-slate-400"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="text-xs text-slate-400 hover:text-slate-600 absolute right-2.5 top-1/2 -translate-y-1/2 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Active Filter Indicator */}
          {(activeCategory !== 'All' || searchQuery) && (
            <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
              <span>
                Showing <strong>{filteredClothes.length}</strong> of {products.length} products
              </span>
              <button
                type="button"
                onClick={() => {
                  setActiveCategory('All');
                  setSearchQuery('');
                }}
                className="text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" /> Reset Filters
              </button>
            </div>
          )}
        </div>

        {/* Dynamic State Views: Loading | Error | Empty | Product Grid */}
        {loading ? (
          /* Loading Skeletons Grid */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 animate-pulse">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
              <div
                key={n}
                className="rounded-3xl bg-white border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col justify-between"
              >
                <div>
                  <div className="aspect-3/4 bg-slate-200" />
                  <div className="p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="h-4 bg-slate-200 rounded-md w-3/5" />
                      <div className="h-4 bg-indigo-100 rounded-md w-1/4" />
                    </div>
                    <div className="space-y-1.5">
                      <div className="h-3 bg-slate-100 rounded-md w-full" />
                      <div className="h-3 bg-slate-100 rounded-md w-4/5" />
                    </div>
                  </div>
                </div>
                <div className="p-5 pt-0 grid grid-cols-2 gap-2">
                  <div className="h-8 bg-slate-100 rounded-xl" />
                  <div className="h-8 bg-indigo-100 rounded-xl" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          /* Error / Storefront Not Found State */
          <div className="rounded-3xl bg-white border border-rose-200 p-8 text-center max-w-lg mx-auto shadow-xs space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {shopNotFound ? 'Boutique Storefront Not Found' : 'Unable to Load Catalogue'}
              </h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                {error}
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button
                to="/catalogue"
                variant="outline"
                size="sm"
              >
                Browse All Stores
              </Button>
              {!shopNotFound && (
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={RefreshCw}
                  onClick={loadProducts}
                >
                  Retry Connection
                </Button>
              )}
            </div>
          </div>
        ) : products.length === 0 ? (
          /* Storefront Empty State */
          <div
            data-testid="empty-storefront-catalogue"
            className="rounded-3xl bg-white border border-slate-200/90 p-12 text-center max-w-lg mx-auto shadow-xs"
          >
            <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-4">
              <PackageSearch className="w-7 h-7" />
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">
              {storeDisplayName} Has No Published Garments Yet
            </h3>
            <p className="text-xs text-slate-500 mb-6 leading-relaxed">
              This boutique storefront currently has 0 garments in its catalogue. The shop owner can add items via Shop Dashboard.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button
                to="/catalogue"
                variant="outline"
                size="sm"
              >
                Switch Boutique
              </Button>
              <Button
                to="/shop-dashboard"
                variant="primary"
                size="sm"
              >
                Go to Shop Dashboard
              </Button>
              <Button
                variant="outline"
                size="sm"
                leftIcon={RefreshCw}
                onClick={loadProducts}
              >
                Refresh
              </Button>
            </div>
          </div>
        ) : filteredClothes.length === 0 ? (
          /* Filter Empty State */
          <div className="rounded-3xl bg-white border border-slate-200/90 p-12 text-center max-w-lg mx-auto shadow-xs">
            <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-4">
              <PackageSearch className="w-7 h-7" />
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">
              No garments match your filters
            </h3>
            <p className="text-xs text-slate-500 mb-6 leading-relaxed">
              {searchQuery
                ? `No items match "${searchQuery}" in category "${activeCategory}".`
                : `There are currently no items available in the "${activeCategory}" category.`}
            </p>
            <Button
              variant="outline"
              size="sm"
              leftIcon={RotateCcw}
              onClick={() => {
                setActiveCategory('All');
                setSearchQuery('');
              }}
            >
              Reset Filters
            </Button>
          </div>
        ) : (
          /* Garments Product Card Grid */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {filteredClothes.map((garment) => {
              const hasError = Boolean(imageErrors[garment.id]);
              const formattedPrice = formatRupeePrice(garment.price);

              return (
                <div
                  key={garment.id}
                  className="group rounded-3xl bg-white border border-slate-200/90 shadow-xs hover:shadow-xl hover:border-indigo-300 transition-all flex flex-col justify-between overflow-hidden"
                >
                  <div>
                    {/* Product Image with Fallback and Badges */}
                    <div
                      className="relative aspect-3/4 overflow-hidden bg-slate-100 cursor-pointer"
                      onClick={() => setModalProduct(garment)}
                      title="Click to view garment details"
                    >
                      {garment.image && !hasError ? (
                        <img
                          src={garment.image}
                          alt={garment.name}
                          className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-500"
                          loading="lazy"
                          onError={() => handleImageError(garment.id)}
                        />
                      ) : (
                        <div
                          className={`w-full h-full bg-gradient-to-tr ${garment.fallbackBg || 'from-indigo-900 to-slate-900'} flex flex-col items-center justify-center text-white/80 p-4`}
                        >
                          <Shirt className="w-16 h-16 mb-2" />
                          <span className="text-xs font-semibold text-white/90 text-center line-clamp-2">
                            {garment.name}
                          </span>
                        </div>
                      )}

                      {/* Category Pill */}
                      {garment.category && (
                        <span className="absolute top-3 left-3 text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full bg-slate-900/80 backdrop-blur-md text-white">
                          {garment.category}
                        </span>
                      )}

                      {/* Status / Inventory Badge */}
                      <span
                        className={`absolute top-3 right-3 text-[10px] font-bold px-2 py-0.5 rounded-full shadow-xs ${
                          garment.status === 'In Stock'
                            ? 'bg-emerald-600 text-white'
                            : garment.status === 'Low Stock'
                            ? 'bg-amber-600 text-white'
                            : 'bg-rose-600 text-white'
                        }`}
                      >
                        {garment.status || 'In Stock'}
                      </span>

                      {/* Bottom Image Tint: Colors & Sizes */}
                      <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-slate-950/60 to-transparent flex items-end p-3">
                        <span className="text-xs text-white/95 font-medium truncate">
                          {Array.isArray(garment.colors) && garment.colors.length > 0
                            ? garment.colors.join(', ')
                            : 'Standard'}{' '}
                          • {Array.isArray(garment.sizes) ? garment.sizes.join(', ') : 'All Sizes'}
                        </span>
                      </div>
                    </div>

                    {/* Card Details */}
                    <div
                      className="p-5 space-y-2 cursor-pointer"
                      onClick={() => setModalProduct(garment)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-bold text-base text-slate-900 group-hover:text-indigo-600 transition-colors leading-snug">
                          {garment.name}
                        </h3>
                        <span className="font-black text-indigo-600 text-lg shrink-0">
                          {formattedPrice}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                        {garment.description || 'Handcrafted luxury garment.'}
                      </p>
                    </div>
                  </div>

                  {/* Action Buttons: View Details & Try On */}
                  <div className="p-5 pt-0 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setModalProduct(garment)}
                      className="px-3 py-2 text-xs font-semibold rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                      title="View product details"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Details
                    </button>
                    <Button
                      to={`/store/${resolvedSlug}/try-on?garment=${garment.id}`}
                      variant="primary"
                      size="sm"
                      leftIcon={Sparkles}
                      className="w-full justify-center"
                    >
                      Try On
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Product Details Modal */}
        <ProductDetailsModal
          isOpen={Boolean(modalProduct)}
          onClose={() => setModalProduct(null)}
          product={modalProduct}
          shopSlug={resolvedSlug}
        />
      </Container>
    </div>
  );
}
