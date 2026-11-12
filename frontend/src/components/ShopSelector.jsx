import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Store,
  Sparkles,
  ShoppingBag,
  ArrowRight,
  Search,
  RefreshCw,
  AlertCircle,
  MapPin,
} from 'lucide-react';
import { fetchShops } from '../services/api';

/**
 * Reusable Storefront Picker rendered whenever a user visits /catalogue or /try-on
 * without an active :shopSlug context. Never fetches cross-shop products globally.
 */
export default function ShopSelector({
  mode = 'catalogue',
  title,
  subtitle,
}) {
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const loadShops = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const list = await fetchShops({ limit: 100 });
      setShops(Array.isArray(list) ? list : []);
    } catch (err) {
      setError(err.message || 'Could not load registered boutiques.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadShops();
  }, [loadShops]);

  const filteredShops = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return shops;
    return shops.filter(
      (s) =>
        (s.shop_name || '').toLowerCase().includes(q) ||
        (s.slug || '').toLowerCase().includes(q) ||
        (s.address || '').toLowerCase().includes(q)
    );
  }, [shops, searchTerm]);

  const headingTitle =
    title ||
    (mode === 'try-on'
      ? 'Select a Boutique to Enter Its Virtual Fitting Room'
      : 'Select a Boutique Storefront');

  const headingSubtitle =
    subtitle ||
    'Each boutique maintains its own private garment inventory. Choose a store below to explore only its published collection.';

  return (
    <div className="min-h-screen bg-slate-50/70 pt-24 pb-16">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Header */}
        <div className="bg-white rounded-3xl border border-slate-200/80 p-6 sm:p-8 shadow-xs space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
            <Store className="w-3.5 h-3.5" />
            <span>Isolated Boutique Storefronts</span>
          </div>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div className="space-y-2 max-w-2xl">
              <h1 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                {headingTitle}
              </h1>
              <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                {headingSubtitle}
              </p>
            </div>
            <div className="relative w-full md:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Find boutique by name..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="rounded-3xl bg-white border border-slate-200 p-6 h-52 animate-pulse flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="h-5 w-40 bg-slate-200 rounded" />
                  <div className="h-3 w-28 bg-slate-100 rounded" />
                </div>
                <div className="h-10 w-full bg-slate-100 rounded-xl" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="rounded-3xl bg-white border border-rose-200 p-8 text-center max-w-lg mx-auto space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-slate-900">Unable to load boutiques</h2>
              <p className="text-sm text-slate-600">{error}</p>
            </div>
            <button
              type="button"
              onClick={loadShops}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Retry</span>
            </button>
          </div>
        ) : filteredShops.length === 0 ? (
          <div className="rounded-3xl bg-white border border-slate-200 p-10 text-center max-w-lg mx-auto space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center mx-auto">
              <Store className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-slate-900">
              {shops.length === 0 ? 'No Boutiques Registered Yet' : 'No Matching Boutiques'}
            </h2>
            <p className="text-sm text-slate-600">
              {shops.length === 0
                ? 'Register a boutique account in Shop Studio to launch your isolated catalogue and fitting room.'
                : 'Try clearing your boutique search filter to see all registered stores.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredShops.map((shop) => {
              const slug = shop.slug || String(shop.id);
              const cataloguePath = `/store/${slug}/catalogue`;
              const tryOnPath = `/store/${slug}/try-on`;
              const count = Number(shop.product_count ?? 0);

              return (
                <div
                  key={shop.id}
                  data-testid={`shop-card-${slug}`}
                  className="rounded-3xl bg-white border border-slate-200/90 p-6 shadow-xs hover:shadow-md hover:border-indigo-200 transition-all flex flex-col justify-between gap-6"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="w-11 h-11 rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center shrink-0">
                        <Store className="w-5 h-5" />
                      </div>
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                        {count} {count === 1 ? 'garment' : 'garments'}
                      </span>
                    </div>

                    <div>
                      <h2 className="text-lg font-bold text-slate-900 line-clamp-1">
                        {shop.shop_name}
                      </h2>
                      <p className="text-xs font-mono text-indigo-600 mt-0.5 truncate">
                        /store/{slug}
                      </p>
                    </div>

                    {shop.address && (
                      <p className="text-xs text-slate-500 flex items-center gap-1.5 line-clamp-1">
                        <MapPin className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                        <span>{shop.address}</span>
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2.5 pt-2 border-t border-slate-100">
                    {mode === 'try-on' ? (
                      <>
                        <Link
                          to={tryOnPath}
                          className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-colors"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Enter Fitting Room</span>
                        </Link>
                        <Link
                          to={cataloguePath}
                          className="inline-flex items-center justify-center gap-1 px-3 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
                        >
                          <span>Catalogue</span>
                        </Link>
                      </>
                    ) : (
                      <>
                        <Link
                          to={cataloguePath}
                          className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors"
                        >
                          <ShoppingBag className="w-3.5 h-3.5" />
                          <span>Browse Catalogue</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                        <Link
                          to={tryOnPath}
                          className="inline-flex items-center justify-center gap-1 px-3 py-2.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold transition-colors"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Try-On</span>
                        </Link>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

