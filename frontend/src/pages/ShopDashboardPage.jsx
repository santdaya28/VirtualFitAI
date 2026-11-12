import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  Store,
  Settings,
  Sparkles,
  ExternalLink,
  Menu,
  X,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Trash2,
  LogIn,
  LogOut,
  ShieldAlert,
} from 'lucide-react';
import Container from '../components/Container';
import OverviewTab from '../components/dashboard/OverviewTab';
import ProductsTab from '../components/dashboard/ProductsTab';
import ProductFormModal from '../components/dashboard/ProductFormModal';
import ShopProfileTab from '../components/dashboard/ShopProfileTab';
import SettingsTab from '../components/dashboard/SettingsTab';
import AuthModal from '../components/AuthModal';
import { SAMPLE_CLOTHES } from '../data/sampleClothes';
import {
  fetchMyProducts,
  fetchShopById,
  createProduct,
  updateProduct,
  deleteProduct,
  updateShop,
} from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function ShopDashboardPage() {
  const { user, isAuthenticated, isCustomer, isLoading: authLoading, logout } = useAuth();
  const isShopOwner = Boolean(isAuthenticated && user && !isCustomer && user.role !== 'customer');
  const shopId = user?.shop_id;
  // Top-level Dashboard Navigation & UI States
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'products' | 'profile' | 'settings'
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('register'); // 'login' | 'register'

  const openShopAuth = (mode = 'register') => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  };
  const [editingProduct, setEditingProduct] = useState(null);
  const [productToDelete, setProductToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notification, setNotification] = useState(null); // { type: 'success' | 'info' | 'error', message }

  // Backend Integration States
  const [shop, setShop] = useState(null); // Backend Shop entity ({ id, shop_name, ... })
  const [products, setProducts] = useState([]); // Loaded from FastAPI backend
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Shop Profile State (synced with authenticated backend shop)
  const [shopProfile, setShopProfile] = useState({
    name: 'VirtualFit Boutique Portal',
    description:
      'Boutique inventory and catalog portal connected to PostgreSQL.',
    email: '',
    phone: '',
    address: '',
    logo: null,
  });

  // Auto-dismiss notification after 4 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  // Load authenticated shop and products from the FastAPI backend
  const loadDashboardData = useCallback(async () => {
    if (authLoading) {
      return;
    }

    setLoading(true);
    setError(null);

    // Never fall back to another shop or auto-create a default shop for guests/customers
    if (!isShopOwner) {
      setShop(null);
      setProducts([]);
      setShopProfile({
        name: 'VirtualFit Boutique Portal',
        description:
          'Sign in with a Shop Owner account to manage your boutique inventory and store profile.',
        email: '',
        phone: '',
        address: '',
        logo: null,
      });
      setLoading(false);
      return;
    }

    if (!shopId) {
      setShop(null);
      setProducts([]);
      setError(
        'No boutique shop is linked to your account. Register or sign in as a Shop Owner to manage inventory.'
      );
      setLoading(false);
      return;
    }

    try {
      const currentShop = await fetchShopById(shopId);
      setShop(currentShop);

      // Synchronize shopProfile with backend data
      setShopProfile((prev) => ({
        ...prev,
        name: currentShop.shop_name,
        owner_name: currentShop.owner_name || '',
        email: currentShop.email || '',
        phone: currentShop.phone || '',
        address: currentShop.address || '',
      }));

      // Fetch ONLY products owned by the authenticated shop owner via server-scoped /api/products/my
      const shopProducts = await fetchMyProducts({ limit: 100 });
      setProducts(shopProducts);
    } catch (err) {
      console.error('Failed to load dashboard data from backend:', err);
      const errorMsg =
        err.message || 'Unable to connect to FastAPI backend at http://localhost:8000/api.';
      setShop(null);
      setProducts([]);
      setError(errorMsg);
      setNotification({
        type: 'error',
        message: `Backend Connection Notice: ${errorMsg}`,
      });
    } finally {
      setLoading(false);
    }
  }, [authLoading, isShopOwner, shopId]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Sidebar navigation menu items (strictly the 4 core sections)
  const menuItems = [
    { id: 'overview', label: 'Dashboard Overview', icon: LayoutDashboard },
    { id: 'products', label: 'Products', icon: Package, badge: products.length },
    { id: 'profile', label: 'Shop Profile', icon: Store },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  // Tab switching handler
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setMobileSidebarOpen(false);
  };

  // Guarded Add Product trigger
  const handleOpenAddProduct = () => {
    if (!isShopOwner) {
      setNotification({
        type: 'error',
        message: 'Please register or sign in as a Shop Owner before adding garments to your catalogue.',
      });
      openShopAuth('register');
      return;
    }
    if (!shop?.id) {
      setNotification({
        type: 'error',
        message: 'Loading your boutique profile. Please wait a moment and try again.',
      });
      loadDashboardData();
      return;
    }
    setEditingProduct(null);
    setIsFormModalOpen(true);
  };

  // Add or Update Product Handler (Connected to FastAPI)
  const handleSaveProduct = async (garmentData) => {
    if (!isShopOwner || !shop?.id) {
      const msg = 'Shop Owner authentication is required before saving garments.';
      setNotification({
        type: 'error',
        message: msg,
      });
      throw new Error(msg);
    }

    try {
      let savedProduct;
      if (editingProduct) {
        // Update existing product in backend
        savedProduct = await updateProduct(editingProduct.id, garmentData);
      } else {
        // Create new product in backend associated with active shop.id
        savedProduct = await createProduct(garmentData, shop.id);
      }

      // Reload authoritative product list from PostgreSQL after confirmed persistence
      const freshProducts = await fetchMyProducts({ limit: 100 });
      setProducts(freshProducts);

      setNotification({
        type: 'success',
        message: editingProduct
          ? `Garment "${savedProduct.name}" updated successfully in database.`
          : `New garment "${savedProduct.name}" added to catalogue database.`,
      });

      setIsFormModalOpen(false);
      setEditingProduct(null);
    } catch (err) {
      console.error('Error saving garment:', err);
      setNotification({
        type: 'error',
        message: `Failed to save product: ${err.message}`,
      });
      throw err;
    }
  };

  // Trigger Edit
  const handleEditProduct = (product) => {
    if (!isShopOwner || !shop?.id) {
      setIsAuthModalOpen(true);
      return;
    }
    setEditingProduct(product);
    setIsFormModalOpen(true);
  };

  // Delete Product Handler (Opens modern confirmation modal with product details)
  const handleDeleteProduct = (productId) => {
    if (!isShopOwner || !shop?.id) {
      setIsAuthModalOpen(true);
      return;
    }
    const target = products.find((p) => p.id === productId);
    if (target) {
      setProductToDelete(target);
    }
  };

  // Confirmed Delete execution (Connected to FastAPI DELETE /api/products/{id})
  const handleConfirmDelete = async () => {
    if (!productToDelete || !shop?.id) return;
    setIsDeleting(true);

    try {
      await deleteProduct(productToDelete.id);
      const freshProducts = await fetchMyProducts({ limit: 100 });
      setProducts(freshProducts);
      setNotification({
        type: 'info',
        message: `Garment "${productToDelete.name}" removed from inventory and database.`,
      });
      setProductToDelete(null);
    } catch (err) {
      console.error('Error deleting garment:', err);
      setNotification({
        type: 'error',
        message: `Failed to delete product: ${err.message}`,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Toggle Availability Handler (Connected to FastAPI PUT /api/products/{id})
  const handleToggleAvailability = async (product) => {
    if (!isShopOwner || !shop?.id || !product?.id) {
      if (!isShopOwner) openShopAuth('register');
      return;
    }

    const currentAvailable = product.is_available !== false && product.status !== 'Out of Stock';
    const newAvailable = !currentAvailable;
    const currentStock = Number(product.stock_quantity ?? 0);
    const newStock = newAvailable && currentStock === 0 ? 10 : currentStock;
    const newStatus = !newAvailable
      ? 'Out of Stock'
      : newStock <= 5
      ? 'Low Stock'
      : 'In Stock';

    try {
      const updated = await updateProduct(product.id, {
        is_available: newAvailable,
        stock_quantity: newStock,
        status: newStatus,
      });

      setProducts((prev) =>
        prev.map((item) =>
          item.id === product.id
            ? {
                ...item,
                ...updated,
                is_available: newAvailable,
                status: newStatus,
                stock_quantity: newStock,
              }
            : item
        )
      );

      setNotification({
        type: 'success',
        message: `"${product.name}" is now marked as ${
          newAvailable ? 'Available (Active)' : 'Unavailable (Out of Stock)'
        }.`,
      });
    } catch (err) {
      console.error('Failed to change availability:', err);
      setNotification({
        type: 'error',
        message: `Failed to change availability: ${err.message}`,
      });
    }
  };

  // Save Shop Profile (Connected to FastAPI PUT /api/shops/{shop_id})
  const handleSaveProfile = async (updatedProfile) => {
    if (!isShopOwner) {
      openShopAuth('register');
      setNotification({
        type: 'error',
        message: 'Sign in as a Shop Owner to update shop profile details.',
      });
      return;
    }
    if (!shop?.id) {
      loadDashboardData();
      setNotification({
        type: 'error',
        message: 'Boutique profile is still loading. Please try again in a moment.',
      });
      return;
    }
    try {
      const updatedShop = await updateShop(shop.id, {
        shop_name: updatedProfile.name,
        owner_name: updatedProfile.owner_name || null,
        email: updatedProfile.email || null,
        phone: updatedProfile.phone || null,
        address: updatedProfile.address || null,
      });
      setShop(updatedShop);
      setShopProfile(updatedProfile);
      setNotification({
        type: 'success',
        message: 'Shop profile successfully saved to database.',
      });
    } catch (err) {
      console.error('Failed to update shop profile:', err);
      setNotification({
        type: 'error',
        message: `Failed to update shop profile: ${err.message}`,
      });
    }
  };

  // Reset to default sample catalogue in database
  const handleResetToDefaults = async () => {
    if (!isShopOwner) {
      openShopAuth('register');
      setNotification({
        type: 'error',
        message: 'Sign in as a Shop Owner before modifying boutique inventory.',
      });
      return;
    }
    if (!shop?.id) {
      loadDashboardData();
      setNotification({
        type: 'error',
        message: 'Boutique profile is still loading. Please try again in a moment.',
      });
      return;
    }

    setLoading(true);
    try {
      // Populate demo sample clothes into backend for the active shop
      for (const item of SAMPLE_CLOTHES) {
        await createProduct(
          {
            name: item.name,
            category: item.category,
            price: parseInt(String(item.price).replace(/[^\d]/g, ''), 10) || 2999,
            description: item.description,
            sizes: ['S', 'M', 'L', 'XL'],
            colors: [item.color || 'Navy Blue'],
            image: item.image,
            status: 'In Stock',
          },
          shop.id
        );
      }
      const freshProducts = await fetchMyProducts({ limit: 100 });
      setProducts(freshProducts);
      setNotification({
        type: 'success',
        message: `Demo inventory populated with ${SAMPLE_CLOTHES.length} sample garments in PostgreSQL.`,
      });
    } catch (err) {
      console.error('Error resetting inventory:', err);
      setNotification({
        type: 'error',
        message: `Failed to reset inventory: ${err.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="pt-4 pb-16 bg-slate-50 min-h-[calc(100vh-4rem)]">
      <Container>
        {/* Guest or Customer Advisory Banners */}
        {!authLoading && !isAuthenticated && (
          <div className="mb-6 rounded-2xl bg-indigo-50/80 border border-indigo-200 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-indigo-950 shadow-2xs">
            <div className="flex items-start gap-3">
              <Store className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-bold text-indigo-950">Retailer Portal — Shop Authentication Required</p>
                <p className="text-xs text-indigo-800 mt-0.5">
                  Create a Shop Owner account to launch your boutique, upload garments, and sync directly with Virtual Try-On, or sign in to an existing shop account.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => openShopAuth('register')}
                data-testid="banner-shop-signup"
                className="px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-colors cursor-pointer"
              >
                Shop Sign Up
              </button>
              <button
                type="button"
                onClick={() => openShopAuth('login')}
                data-testid="banner-shop-signin"
                className="px-4 py-2 rounded-xl text-xs font-bold bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-2xs transition-colors cursor-pointer"
              >
                Shop Owner Sign In
              </button>
            </div>
          </div>
        )}
        {!authLoading && isAuthenticated && !isShopOwner && (
          <div className="mb-6 rounded-2xl bg-blue-50 border border-blue-200 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-blue-900 shadow-2xs">
            <div className="flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-bold text-blue-950">Customer Account Active ({user?.email})</p>
                <p className="text-xs text-blue-800 mt-0.5">
                  Customer accounts cannot create or manage shop products. Browse the catalogue, use Virtual Try-On, or register a Shop Owner account.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => openShopAuth('register')}
                data-testid="customer-banner-shop-signup"
                className="px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition-colors cursor-pointer"
              >
                Shop Sign Up
              </button>
              <button
                type="button"
                onClick={logout}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 transition-colors cursor-pointer"
              >
                Sign Out
              </button>
            </div>
          </div>
        )}

        {/* Top Shop Banner / Breadcrumb */}
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white rounded-2xl p-4 border border-slate-200/90 shadow-2xs">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center font-bold text-sm shadow-xs shrink-0">
              {shopProfile.logo ? (
                <img
                  src={shopProfile.logo}
                  alt="Shop Logo"
                  className="w-full h-full object-cover rounded-xl"
                />
              ) : (
                <Store className="w-5 h-5" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-extrabold text-slate-900 tracking-tight truncate max-w-xs sm:max-w-md">
                  {shopProfile.name}
                </h1>
                <span className="hidden sm:inline-block px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                  {shop
                    ? `Live Retailer (ID: #${shop.id})`
                    : authLoading
                    ? 'Checking Session...'
                    : isAuthenticated && isCustomer
                    ? 'Customer Account'
                    : 'Sign In Required'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                Garment Shop Admin Portal •{' '}
                {loading
                  ? 'Loading...'
                  : shop
                  ? `${products.length} Products in Database`
                  : 'Retailer Sign-In Required'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Refresh / Sync Button */}
            <button
              type="button"
              onClick={loadDashboardData}
              disabled={loading}
              className="p-2 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-600 transition-colors cursor-pointer"
              title="Sync with database"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
            </button>

            {/* Mobile menu trigger */}
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
              className="lg:hidden p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-100 cursor-pointer"
              aria-label="Toggle dashboard menu"
            >
              {mobileSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            {/* Customer Storefront Links */}
            {shop?.slug && (
              <Link
                to={`/store/${shop.slug}/try-on`}
                data-testid="shop-storefront-tryon-link"
                className="px-3.5 py-2 rounded-xl border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-2xs"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Store Try-On</span>
              </Link>
            )}
            <Link
              to={shop?.slug ? `/store/${shop.slug}/catalogue` : '/catalogue'}
              data-testid="shop-storefront-catalogue-link"
              className="px-3.5 py-2 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-2xs"
            >
              <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
              <span>View Customer Catalogue</span>
            </Link>
          </div>
        </div>

        {/* Global Floating Toast / Notification */}
        {notification && (
          <div
            className={`mb-6 p-4 rounded-2xl border text-xs flex items-center justify-between gap-3 shadow-xs animate-fadeIn ${
              notification.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : notification.type === 'error'
                ? 'bg-rose-50 border-rose-200 text-rose-800'
                : 'bg-indigo-50 border-indigo-200 text-indigo-800'
            }`}
          >
            <div className="flex items-center gap-2">
              {notification.type === 'error' ? (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              ) : (
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
              )}
              <span>{notification.message}</span>
            </div>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="p-1 hover:bg-black/5 rounded cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Main Dashboard Workspace (Sidebar + Content) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Sidebar Navigation (Desktop) */}
          <aside className="hidden lg:block lg:col-span-3 space-y-4 sticky top-22">
            <div className="bg-white rounded-3xl border border-slate-200/90 p-4 shadow-xs space-y-1">
              <p className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Dashboard Menu
              </p>

              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;

                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleTabChange(item.id)}
                    className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-2xs font-bold'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className="w-4 h-4 shrink-0" />
                      <span>{item.label}</span>
                    </div>
                    {item.badge !== undefined && (
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold ${
                          isActive
                            ? 'bg-white/20 text-white'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Catalogue Status Card in Sidebar */}
            <div className="bg-gradient-to-tr from-indigo-50/70 to-purple-50/70 rounded-3xl border border-indigo-100/90 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
                  <Sparkles className="w-3.5 h-3.5" />
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold uppercase tracking-wider border border-amber-200">
                  AI Integration Pending
                </span>
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">Catalogue Ready</h4>
                <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                  Store garments are synchronized live with PostgreSQL and structured for virtual try-on.
                </p>
              </div>
            </div>
          </aside>

          {/* Mobile Drawer Navigation (When Open) */}
          {mobileSidebarOpen && (
            <div className="lg:hidden col-span-12 bg-white rounded-3xl border border-slate-200 p-4 shadow-md space-y-1 animate-fadeIn">
              <p className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Menu
              </p>
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleTabChange(item.id)}
                    className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold cursor-pointer ${
                      isActive
                        ? 'bg-indigo-600 text-white font-bold'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </div>
                    {item.badge !== undefined && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-white/20">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* Main Dashboard Workspace View */}
          <main className="lg:col-span-9 min-h-[600px]">
            {(authLoading || (isShopOwner && loading)) ? (
              <div className="rounded-3xl bg-white border border-slate-200/90 p-12 text-center shadow-xs flex flex-col items-center justify-center min-h-[400px]">
                <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
                  <RefreshCw className="w-6 h-6 animate-spin" />
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-1">
                  Connecting to PostgreSQL Database...
                </h3>
                <p className="text-xs text-slate-500 max-w-sm">
                  Loading boutique profile and syncing live garment inventory from the FastAPI backend.
                </p>
              </div>
            ) : error ? (
              <div className="rounded-3xl bg-white border border-rose-200 p-8 shadow-xs space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                    <AlertCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      Backend Connection Notice
                    </h3>
                    <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                      {error}
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1 font-mono">
                      FastAPI service: http://127.0.0.1:8000/api
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={loadDashboardData}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer shadow-xs"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Retry Connection</span>
                  </button>
                </div>
              </div>
            ) : !isAuthenticated ? (
              <div className="rounded-3xl bg-white border border-slate-200/90 p-8 sm:p-10 shadow-xs text-center space-y-5">
                <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto border border-indigo-100">
                  <Store className="w-7 h-7" />
                </div>
                <div className="space-y-2 max-w-md mx-auto">
                  <h2 className="text-xl font-extrabold text-slate-900">
                    Shop Owner Dashboard
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                    Register a new boutique with <strong>Shop Sign Up</strong> to start uploading garments, or sign in with your existing Shop Owner credentials.
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => openShopAuth('register')}
                    data-testid="portal-shop-signup"
                    className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm font-bold shadow-sm transition-colors flex items-center gap-2 cursor-pointer"
                  >
                    <Store className="w-4 h-4" />
                    <span>Shop Sign Up</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => openShopAuth('login')}
                    data-testid="portal-shop-signin"
                    className="px-5 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs sm:text-sm font-semibold shadow-2xs transition-colors flex items-center gap-2 cursor-pointer"
                  >
                    <LogIn className="w-4 h-4 text-slate-500" />
                    <span>Shop Owner Sign In</span>
                  </button>
                </div>
                <p className="text-[11px] text-slate-400">
                  Looking to browse or try on outfits?{' '}
                  <Link to="/try-on" className="text-indigo-600 font-semibold hover:underline">
                    Open Virtual Try-On Studio
                  </Link>
                </p>
              </div>
            ) : !isShopOwner ? (
              <div
                data-testid="customer-role-restriction"
                className="rounded-3xl bg-white border border-blue-200 p-8 sm:p-10 shadow-xs text-center space-y-5"
              >
                <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto border border-blue-100">
                  <ShieldAlert className="w-7 h-7" />
                </div>
                <div className="space-y-2 max-w-md mx-auto">
                  <h2 className="text-xl font-extrabold text-slate-900">
                    Shop Owner Account Required
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                    You are currently signed in as a <strong>Customer / Shopper</strong> ({user?.email}). Customer accounts cannot create or manage shop products.
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
                  <Link
                    to="/catalogue"
                    className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-xs transition-colors flex items-center gap-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Browse Garment Catalogue</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => openShopAuth('register')}
                    data-testid="restricted-shop-signup"
                    className="px-4 py-2.5 rounded-xl bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <Store className="w-3.5 h-3.5" />
                    <span>Shop Sign Up</span>
                  </button>
                  <button
                    type="button"
                    onClick={logout}
                    className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            ) : !shop ? (
              <div className="rounded-3xl bg-white border border-amber-200 p-8 shadow-xs text-center space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <div className="space-y-1 max-w-md mx-auto">
                  <h3 className="text-base font-bold text-slate-900">
                    Loading Boutique Profile
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Your shop owner session is active, but the boutique profile is not loaded yet. Click retry to fetch your boutique details.
                  </p>
                </div>
                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={loadDashboardData}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer shadow-xs"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Load My Boutique</span>
                  </button>
                </div>
              </div>
            ) : (
              <>
                {activeTab === 'overview' && (
                  <OverviewTab
                    products={products}
                    onNavigateTab={handleTabChange}
                    onAddProduct={handleOpenAddProduct}
                    onEditProduct={handleEditProduct}
                    onDeleteProduct={handleDeleteProduct}
                    onToggleAvailability={handleToggleAvailability}
                  />
                )}

                {activeTab === 'products' && (
                  <ProductsTab
                    products={products}
                    onEditProduct={handleEditProduct}
                    onDeleteProduct={handleDeleteProduct}
                    onToggleAvailability={handleToggleAvailability}
                    onAddProduct={handleOpenAddProduct}
                  />
                )}

                {activeTab === 'profile' && (
                  <ShopProfileTab
                    shopProfile={shopProfile}
                    onSaveProfile={handleSaveProfile}
                  />
                )}

                {activeTab === 'settings' && (
                  <SettingsTab onResetToDefaults={handleResetToDefaults} />
                )}
              </>
            )}
          </main>
        </div>

        {/* Add / Edit Product Modal */}
        <ProductFormModal
          isOpen={isFormModalOpen}
          initialData={editingProduct}
          onSave={handleSaveProduct}
          onCancel={() => {
            setIsFormModalOpen(false);
            setEditingProduct(null);
          }}
        />

        {/* Delete Confirmation Modal */}
        {productToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fadeIn">
            <div className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden p-6 space-y-4">
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0 border border-rose-100">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-slate-900">Delete Garment Product</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Are you sure you want to permanently delete{' '}
                    <strong className="text-slate-900 font-semibold">{productToDelete.name}</strong>{' '}
                    (ID: #{productToDelete.id}) from your retail store inventory?
                  </p>
                  <p className="text-[11px] text-rose-600 font-medium pt-1">
                    This action cannot be undone and will remove it permanently from your PostgreSQL database and customer catalogue.
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setProductToDelete(null)}
                  disabled={isDeleting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmDelete}
                  disabled={isDeleting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-xs"
                >
                  {isDeleting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Deleting...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete Product</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Auth Modal for Retailer Sign-In / Registration */}
        <AuthModal
          isOpen={isAuthModalOpen}
          onClose={() => setIsAuthModalOpen(false)}
          initialMode={authModalMode}
          initialRole="shop_owner"
        />
      </Container>
    </div>
  );
}
