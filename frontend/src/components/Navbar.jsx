import React, { useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { Sparkles, Menu, X, Shirt, ArrowRight, LogOut, LogIn, Store } from 'lucide-react';
import Container from './Container';
import Button from './Button';
import { NAV_LINKS } from '../data/navigation';
import { useScrollPosition } from '../hooks/useScrollPosition';
import { useAuth } from '../context/AuthContext';
import AuthModal from './AuthModal';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authInitialMode, setAuthInitialMode] = useState('login');
  const [authInitialRole, setAuthInitialRole] = useState('customer');

  const scrollPosition = useScrollPosition();
  const location = useLocation();
  const { user, isAuthenticated, isShopOwner, logout } = useAuth();

  const isScrolled = scrollPosition > 10;
  const isShopDashboard = location.pathname.startsWith('/shop-dashboard');
  const storeMatch = location.pathname.match(/^\/store\/([^/]+)/);
  const urlShopSlug = storeMatch ? decodeURIComponent(storeMatch[1]).toLowerCase() : null;
  const effectiveShopSlug = urlShopSlug || (isShopOwner && user?.shop_slug ? user.shop_slug : null);

  const resolveNavPath = (basePath) => {
    if (!effectiveShopSlug) return basePath;
    if (basePath === '/catalogue') return `/store/${effectiveShopSlug}/catalogue`;
    if (basePath === '/try-on') return `/store/${effectiveShopSlug}/try-on`;
    return basePath;
  };

  const isNavItemActive = (basePath) => {
    if (basePath === '/') return location.pathname === '/';
    if (basePath === '/catalogue') {
      return (
        location.pathname.startsWith('/catalogue') ||
        /^\/store\/[^/]+(\/catalogue)?\/?$/.test(location.pathname)
      );
    }
    if (basePath === '/try-on') {
      return (
        location.pathname.startsWith('/try-on') ||
        /^\/store\/[^/]+\/try-on\/?$/.test(location.pathname)
      );
    }
    return location.pathname.startsWith(basePath);
  };

  const closeMobileMenu = () => setMobileMenuOpen(false);

  const openAuth = (mode = 'login', role = 'customer') => {
    setAuthInitialMode(mode);
    setAuthInitialRole(role);
    setAuthModalOpen(true);
    closeMobileMenu();
  };

  return (
    <>
      <header
        className={`sticky top-0 z-50 transition-all duration-200 ${
          isScrolled
            ? 'bg-white/90 backdrop-blur-md border-b border-slate-200/80 shadow-xs'
            : 'bg-white/70 backdrop-blur-xs border-b border-transparent'
        }`}
      >
        <Container>
          <div className="flex items-center justify-between h-18">
            {/* Brand Logo */}
            <Link
              to="/"
              onClick={closeMobileMenu}
              className="flex items-center gap-2.5 group focus:outline-none"
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
                <Shirt className="w-5 h-5 text-white" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-lg tracking-tight text-slate-900 group-hover:text-indigo-600 transition-colors flex items-center gap-1.5">
                  VirtualFit
                  <span className="text-xs font-semibold px-1.5 py-0.5 rounded-md bg-indigo-100 text-indigo-700 uppercase tracking-wider">
                    AI
                  </span>
                </span>
                <span className="text-[10px] text-slate-500 font-medium tracking-wide -mt-0.5 hidden sm:block">
                  For Garment Retailers
                </span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-0.5 lg:gap-1.5">
              {NAV_LINKS.map((link) => {
                const targetPath = resolveNavPath(link.path);
                const active = isNavItemActive(link.path);
                return (
                  <NavLink
                    key={link.path}
                    to={targetPath}
                    end={link.path === '/'}
                    className={() =>
                      `px-2.5 py-1.5 lg:px-3.5 lg:py-2 text-xs lg:text-sm font-medium rounded-lg transition-colors ${
                        active
                          ? 'text-indigo-600 bg-indigo-50/70 font-semibold'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                      }`
                    }
                  >
                    {link.name}
                  </NavLink>
                );
              })}
            </nav>

            {/* Right Action Desktop */}
            <div className="hidden md:flex items-center gap-3">
              {isAuthenticated ? (
                <div className="flex items-center gap-2.5 bg-slate-100/80 px-3 py-1.5 rounded-xl border border-slate-200">
                  <div className="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-semibold">
                    {user?.full_name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || 'U'}
                  </div>
                  <div className="flex flex-col text-left">
                    <span className="text-xs font-bold text-slate-800 leading-tight">
                      {user?.full_name || user?.email}
                    </span>
                    <span className="text-[10px] text-indigo-600 font-semibold uppercase tracking-wider leading-tight">
                      {isShopOwner ? 'Shop Owner' : 'Shopper'}
                    </span>
                  </div>
                  <button
                    onClick={logout}
                    title="Sign Out"
                    className="ml-1 p-1 text-slate-400 hover:text-red-600 rounded-md hover:bg-slate-200/60 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => openAuth('login', 'customer')}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:text-indigo-600 hover:bg-slate-100/80 rounded-lg transition-colors cursor-pointer"
                  >
                    <LogIn className="w-3.5 h-3.5" />
                    Sign In
                  </button>
                  <button
                    type="button"
                    onClick={() => openAuth('register', 'shop_owner')}
                    data-testid="navbar-shop-signup"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors cursor-pointer"
                  >
                    <Store className="w-3.5 h-3.5" />
                    Shop Sign Up
                  </button>
                </div>
              )}

              {!isShopDashboard && (
                <Button
                  to={resolveNavPath('/try-on')}
                  variant="primary"
                  size="sm"
                  leftIcon={Sparkles}
                >
                  Try Virtual Fitting
                </Button>
              )}
            </div>

            {/* Mobile Menu Button */}
            <div className="flex items-center md:hidden gap-2">
              <button
                type="button"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 cursor-pointer"
                aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
                aria-expanded={mobileMenuOpen}
              >
                {mobileMenuOpen ? (
                  <X className="w-6 h-6" />
                ) : (
                  <Menu className="w-6 h-6" />
                )}
              </button>
            </div>
          </div>

          {/* Mobile Navigation Drawer */}
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-slate-200/80 py-4 bg-white/95 backdrop-blur-md transition-all">
              {/* Mobile User Profile Section */}
              {isAuthenticated ? (
                <div className="px-3 py-2.5 mb-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-semibold">
                      {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-900">{user?.full_name || user?.email}</div>
                      <div className="text-[10px] text-indigo-600 font-semibold uppercase tracking-wider">
                        {isShopOwner ? 'Shop Owner' : 'Shopper'}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      logout();
                      closeMobileMenu();
                    }}
                    className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-100 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="px-3 py-2 mb-3 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => openAuth('login', 'customer')}
                    className="w-full py-2 px-3 text-xs font-semibold text-center rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <LogIn className="w-3.5 h-3.5" />
                    Sign In
                  </button>
                  <button
                    type="button"
                    onClick={() => openAuth('register', 'shop_owner')}
                    data-testid="navbar-mobile-shop-signup"
                    className="w-full py-2 px-3 text-xs font-semibold text-center rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Store className="w-3.5 h-3.5" />
                    Shop Sign Up
                  </button>
                </div>
              )}

              <div className="flex flex-col gap-1.5">
                {NAV_LINKS.map((link) => {
                  const isActive = isNavItemActive(link.path);
                  const targetPath = resolveNavPath(link.path);
                  return (
                    <Link
                      key={link.path}
                      to={targetPath}
                      onClick={closeMobileMenu}
                      className={`px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                        isActive
                          ? 'text-indigo-600 bg-indigo-50 font-semibold'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                      }`}
                    >
                      {link.name}
                    </Link>
                  );
                })}
                {!isShopDashboard && (
                  <div className="pt-3 mt-2 border-t border-slate-100">
                    <Button
                      to={resolveNavPath('/try-on')}
                      onClick={closeMobileMenu}
                      variant="primary"
                      size="md"
                      rightIcon={ArrowRight}
                      className="w-full justify-center"
                    >
                      Start Virtual Try-On
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </Container>
      </header>

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        initialMode={authInitialMode}
        initialRole={authInitialRole}
      />
    </>
  );
}
