import React, { useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { Sparkles, Menu, X, Shirt, ArrowRight } from 'lucide-react';
import Container from './Container';
import Button from './Button';
import { NAV_LINKS } from '../data/navigation';
import { useScrollPosition } from '../hooks/useScrollPosition';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const scrollPosition = useScrollPosition();
  const location = useLocation();

  const isScrolled = scrollPosition > 10;

  const closeMobileMenu = () => setMobileMenuOpen(false);

  return (
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

          {/* Desktop Navigation with 'end' attribute for exact root matching */}
          <nav className="hidden md:flex items-center gap-1 lg:gap-2">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.path}
                to={link.path}
                end={link.path === '/'}
                className={({ isActive }) =>
                  `px-3.5 py-2 text-sm font-medium rounded-lg transition-colors ${
                    isActive
                      ? 'text-indigo-600 bg-indigo-50/70 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                  }`
                }
              >
                {link.name}
              </NavLink>
            ))}
          </nav>

          {/* Right Action Desktop */}
          <div className="hidden md:flex items-center gap-3">
            <Button
              to="/try-on"
              variant="primary"
              size="sm"
              leftIcon={Sparkles}
            >
              Try Virtual Fitting
            </Button>
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
            <div className="flex flex-col gap-1.5">
              {NAV_LINKS.map((link) => {
                const isActive =
                  link.path === '/'
                    ? location.pathname === '/'
                    : location.pathname.startsWith(link.path);
                return (
                  <Link
                    key={link.path}
                    to={link.path}
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
              <div className="pt-3 mt-2 border-t border-slate-100">
                <Button
                  to="/try-on"
                  onClick={closeMobileMenu}
                  variant="primary"
                  size="md"
                  rightIcon={ArrowRight}
                  className="w-full justify-center"
                >
                  Start Virtual Try-On
                </Button>
              </div>
            </div>
          </div>
        )}
      </Container>
    </header>
  );
}
