import React from 'react';
import { Link } from 'react-router-dom';
import { Shirt, Sparkles, ShieldCheck } from 'lucide-react';
import Container from './Container';
import { FOOTER_LINKS } from '../data/navigation';

const CURRENT_YEAR = 2026;

export default function Footer() {
  const techTags = [
    'React 19',
    'Vite 8',
    'Tailwind CSS v4',
    'FastAPI',
    'PostgreSQL 18',
    'React Native (Expo)',
  ];

  return (
    <footer className="bg-slate-900 text-slate-300 mt-auto border-t border-slate-800">
      <Container className="py-12 lg:py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 lg:gap-12">
          {/* Brand Info */}
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
                <Shirt className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-xl tracking-tight text-white flex items-center gap-1.5">
                VirtualFit <span className="text-xs font-semibold px-1.5 py-0.5 rounded-md bg-indigo-500/30 text-indigo-300 border border-indigo-400/30">AI</span>
              </span>
            </div>
            <p className="text-sm text-slate-400 max-w-sm leading-relaxed">
              VirtualFit AI empowers garment shops, boutiques, and fashion retailers with interactive, AI-driven virtual fitting rooms to boost customer conversions and eliminate fitting room bottlenecks.
            </p>
            <div className="flex items-center gap-4 text-xs text-slate-400 pt-2">
              <span className="inline-flex items-center gap-1.5 text-indigo-400">
                <Sparkles className="w-3.5 h-3.5" />
                AI Try-On Ready
              </span>
              <span className="inline-flex items-center gap-1.5 text-emerald-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                Retail Optimized
              </span>
            </div>
          </div>

          {/* Platform Links */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200 mb-4">
              Platform
            </h4>
            <ul className="space-y-2.5 text-sm">
              {FOOTER_LINKS.platform.map((item) => (
                <li key={item.name}>
                  <Link
                    to={item.path}
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    {item.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Technology Stack Tags */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200 mb-4">
              Technology Stack
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {techTags.map((tag) => (
                <span
                  key={tag}
                  className="px-2.5 py-1 rounded-md bg-slate-800 text-[11px] text-slate-300 border border-slate-700/80 font-mono"
                >
                  {tag}
                </span>
              ))}
            </div>
            <div className="mt-5">
              <Link
                to="/about"
                className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Learn more about our architecture →
              </Link>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 mt-12 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
          <p>© {CURRENT_YEAR} VirtualFit AI. All rights reserved.</p>
          <p className="flex items-center gap-1 text-slate-400">
            Crafted for modern garment boutiques & retailers
          </p>
        </div>
      </Container>
    </footer>
  );
}
