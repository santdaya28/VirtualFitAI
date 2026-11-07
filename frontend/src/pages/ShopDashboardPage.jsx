import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import Container from '../components/Container';
import OverviewTab from '../components/dashboard/OverviewTab';
import ProductsTab from '../components/dashboard/ProductsTab';
import ProductFormModal from '../components/dashboard/ProductFormModal';
import ShopProfileTab from '../components/dashboard/ShopProfileTab';
import SettingsTab from '../components/dashboard/SettingsTab';
import { SAMPLE_CLOTHES } from '../data/sampleClothes';

// Initial structured products converted from SAMPLE_CLOTHES
const INITIAL_PRODUCTS = SAMPLE_CLOTHES.map((item, idx) => ({
  id: item.id,
  name: item.name,
  category: item.category,
  price: parseInt(String(item.price).replace(/[^\d]/g, ''), 10) || 2999,
  description: item.description,
  sizes: ['S', 'M', 'L', 'XL'],
  colors: [item.color || 'Navy Blue'],
  image: item.image,
  status: idx % 3 === 0 ? 'In Stock' : idx % 3 === 1 ? 'Low Stock' : 'In Stock',
  fit: item.fit,
  badge: item.badge,
  fallbackBg: item.fallbackBg,
  createdAt: new Date(Date.now() - idx * 86400000 * 2).toISOString().split('T')[0],
}));

export default function ShopDashboardPage() {
  // Top-level Dashboard States
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'products' | 'profile' | 'settings'
  const [products, setProducts] = useState(INITIAL_PRODUCTS);
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [notification, setNotification] = useState(null); // { type: 'success' | 'info' | 'error', message }
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Shop Profile State
  const [shopProfile, setShopProfile] = useState({
    name: 'Royal Heritage Garments & Boutiques',
    description:
      'Premier boutique specializing in bespoke formal blazers, handcrafted royal silk ethnic wear, and luxury contemporary attire.',
    email: 'contact@royalheritage.in',
    phone: '+91 98765 43210',
    address: '42 Commercial Street, Fashion District, Bengaluru, Karnataka 560001',
    logo: null,
  });

  // Auto-dismiss notification after 4 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

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

  // Add or Update Product Handler
  const handleSaveProduct = (garmentData) => {
    if (editingProduct) {
      // Update existing
      setProducts((prev) =>
        prev.map((item) => (item.id === garmentData.id ? garmentData : item))
      );
      setNotification({
        type: 'success',
        message: `Garment "${garmentData.name}" updated successfully.`,
      });
    } else {
      // Add new
      setProducts((prev) => [garmentData, ...prev]);
      setNotification({
        type: 'success',
        message: `New garment "${garmentData.name}" added to catalogue.`,
      });
    }

    setIsFormModalOpen(false);
    setEditingProduct(null);
    setActiveTab('overview');
  };

  // Trigger Edit
  const handleEditProduct = (product) => {
    setEditingProduct(product);
    setIsFormModalOpen(true);
  };

  // Delete Product
  const handleDeleteProduct = (productId) => {
    const target = products.find((p) => p.id === productId);
    const confirmed = window.confirm(
      `Are you sure you want to delete "${target?.name || 'this item'}" from the store catalogue?`
    );
    if (!confirmed) return;

    setProducts((prev) => prev.filter((p) => p.id !== productId));
    setNotification({
      type: 'info',
      message: `Garment "${target?.name || ''}" removed from inventory.`,
    });
  };

  // Reset to default sample catalogue
  const handleResetToDefaults = () => {
    setProducts(INITIAL_PRODUCTS);
    setNotification({
      type: 'info',
      message: 'Demo inventory reset to default sample products.',
    });
  };

  return (
    <div className="pt-4 pb-16 bg-slate-50 min-h-[calc(100vh-4rem)]">
      <Container>
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
                  Live Retailer
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                Garment Shop Admin Portal • {products.length} Products in Catalogue
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Mobile menu trigger */}
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
              className="lg:hidden p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-100 cursor-pointer"
              aria-label="Toggle dashboard menu"
            >
              {mobileSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            {/* Customer Catalogue Access */}
            <Link
              to="/catalogue"
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
                : 'bg-indigo-50 border-indigo-200 text-indigo-800'
            }`}
          >
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
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
                  Store garments are structured for retailer management and customer catalogue browsing.
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
            {activeTab === 'overview' && (
              <OverviewTab
                products={products}
                onNavigateTab={handleTabChange}
                onAddProduct={() => {
                  setEditingProduct(null);
                  setIsFormModalOpen(true);
                }}
                onEditProduct={handleEditProduct}
                onDeleteProduct={handleDeleteProduct}
              />
            )}

            {activeTab === 'products' && (
              <ProductsTab
                products={products}
                onEditProduct={handleEditProduct}
                onDeleteProduct={handleDeleteProduct}
              />
            )}

            {activeTab === 'profile' && (
              <ShopProfileTab
                shopProfile={shopProfile}
                onSaveProfile={(updatedProfile) => {
                  setShopProfile(updatedProfile);
                  setNotification({
                    type: 'success',
                    message: 'Shop profile successfully saved.',
                  });
                }}
              />
            )}

            {activeTab === 'settings' && (
              <SettingsTab onResetToDefaults={handleResetToDefaults} />
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
      </Container>
    </div>
  );
}
