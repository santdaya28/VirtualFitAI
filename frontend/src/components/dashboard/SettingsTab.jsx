import React, { useState } from 'react';
import {
  Database,
  Cpu,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import Button from '../Button';

export default function SettingsTab({
  onResetToDefaults,
}) {
  const [currency] = useState('₹ INR (Indian Rupee)');
  const [tryOnEnabled, setTryOnEnabled] = useState(true);
  const [lowStockThreshold, setLowStockThreshold] = useState(5);
  const [resetSuccess, setResetSuccess] = useState(false);
  const [showConfirmReset, setShowConfirmReset] = useState(false);

  const handleConfirmReset = () => {
    onResetToDefaults();
    setShowConfirmReset(false);
    setResetSuccess(true);
    setTimeout(() => setResetSuccess(false), 4000);
  };

  return (
    <div className="space-y-8 max-w-4xl animate-fadeIn">
      {/* Top Header */}
      <div className="pb-4 border-b border-slate-200">
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
          Shop Settings & Platform Configuration
        </h2>
        <p className="text-xs sm:text-sm text-slate-500">
          Manage currency standards, try-on studio availability, and inventory sync options.
        </p>
      </div>

      {resetSuccess && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2 animate-fadeIn">
          <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>Demo catalogue inventory has been restored to default sample items.</span>
        </div>
      )}

      {/* Settings Grid */}
      <div className="space-y-6">
        {/* Currency & Financial Preferences */}
        <div className="rounded-3xl bg-white border border-slate-200/90 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-2 border-b border-slate-100">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Currency & Regional Standards</h3>
              <p className="text-[11px] text-slate-500">Default currency denomination for your catalogue</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Store Pricing Currency
              </label>
              <input
                type="text"
                disabled
                value={currency}
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-slate-50 text-slate-700 font-semibold cursor-not-allowed"
              />
              <p className="text-[10px] text-slate-400 mt-1">Configured for Indian retail garments (₹)</p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Low Stock Alert Threshold
              </label>
              <input
                type="number"
                min="1"
                max="50"
                value={lowStockThreshold}
                onChange={(e) => setLowStockThreshold(Number(e.target.value))}
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
              <p className="text-[10px] text-slate-400 mt-1">Items below this quantity trigger a warning</p>
            </div>
          </div>
        </div>

        {/* AI Virtual Try-On Studio Integration */}
        <div className="rounded-3xl bg-white border border-slate-200/90 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-2 border-b border-slate-100">
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">Catalogue & AI Try-On Pipeline</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold uppercase tracking-wider">
                  AI Integration Pending
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                Configure garments for store catalogue indexing. Generative AI try-on models will connect in Step 2.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-xs font-bold text-slate-800">
                Enable Customer Virtual Try-On Studio
              </p>
              <p className="text-[11px] text-slate-500 max-w-md">
                Allow customers to select outfits from your catalogue and load them into the interactive fitting studio.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setTryOnEnabled(!tryOnEnabled)}
              className={`w-12 h-6 rounded-full transition-colors relative cursor-pointer ${
                tryOnEnabled ? 'bg-indigo-600' : 'bg-slate-300'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  tryOnEnabled ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Backend & Database Persistence Notice */}
        <div className="rounded-3xl bg-slate-900 text-white p-6 shadow-md border border-slate-800 space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Database Synchronization Status</h3>
              <p className="text-[11px] text-slate-400">PostgreSQL 18 Integration</p>
            </div>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">
            This dashboard operates with interactive local React state for demonstration. When the FastAPI + PostgreSQL backend service is activated, all added, updated, and deleted products synchronize directly with your PostgreSQL database tables.
          </p>

          <div className="flex items-center gap-2 pt-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse" />
            <span className="text-[11px] text-emerald-300 font-semibold font-mono">
              FastAPI Schema & SQLAlchemy Models Ready
            </span>
          </div>
        </div>

        {/* Reset Demo Data */}
        <div className="rounded-3xl bg-rose-50/50 border border-rose-200 p-6 shadow-xs space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-rose-900 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-rose-600" /> Reset Demo Inventory
              </h3>
              <p className="text-xs text-rose-700/80 mt-1 max-w-lg">
                Restore the default 8 sample garments across Formal, Casual, Ethnic, and Outerwear categories.
              </p>
            </div>

            {!showConfirmReset ? (
              <Button
                variant="outline"
                size="sm"
                leftIcon={RotateCcw}
                onClick={() => setShowConfirmReset(true)}
                className="text-rose-700 border-rose-300 hover:bg-rose-100 shrink-0"
              >
                Reset Catalogue
              </Button>
            ) : (
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={handleConfirmReset}
                  className="px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-colors cursor-pointer"
                >
                  Confirm Reset
                </button>
                <button
                  type="button"
                  onClick={() => setShowConfirmReset(false)}
                  className="px-2.5 py-1.5 rounded-xl border border-slate-200 bg-white text-slate-600 text-xs font-medium hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
