import React, { useState } from 'react';
import {
  Shirt,
  Sparkles,
  Filter,
  Database,
} from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';
import { SAMPLE_CLOTHES } from '../data/sampleClothes';

export default function CataloguePage() {
  const [activeCategory, setActiveCategory] = useState('All');

  const categories = [
    'All',
    'Formal',
    'Casual',
    'Ethnic',
    'Outerwear',
  ];

  const filteredClothes =
    activeCategory === 'All'
      ? SAMPLE_CLOTHES
      : SAMPLE_CLOTHES.filter((item) => item.category === activeCategory);

  return (
    <div className="py-8 sm:py-14">
      <Container>
        {/* Header Section */}
        <div className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-3 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
              <Shirt className="w-3.5 h-3.5" />
              <span>Garment Shop Catalogue</span>
            </div>
            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
              Curated Clothing Catalogue
            </h1>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
              Explore sample garments across Formal, Casual, Ethnic, and Outerwear categories.
              Click <strong>"Try On This Item"</strong> on any piece to test it directly inside the Virtual Try-On studio.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Button
              to="/try-on"
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
                Inventory Architecture Ready
              </p>
              <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                Currently displaying verified sample collections from <code className="text-slate-200">src/data/sampleClothes.js</code>. This view will dynamically synchronize with your PostgreSQL database in Step 2.
              </p>
            </div>
          </div>
          <span className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 font-mono border border-slate-700 shrink-0">
            {filteredClothes.length} garments displayed
          </span>
        </div>

        {/* Category Filters Bar */}
        <div className="mb-8 flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
          <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5 mr-2 shrink-0">
            <Filter className="w-3.5 h-3.5" /> Category:
          </span>
          {categories.map((category) => {
            const isActive = activeCategory === category;
            return (
              <button
                key={category}
                type="button"
                onClick={() => setActiveCategory(category)}
                className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all shrink-0 cursor-pointer ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm'
                    : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                {category}
              </button>
            );
          })}
        </div>

        {/* Garments Product Card Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {filteredClothes.map((garment) => (
            <div
              key={garment.id}
              className="group rounded-3xl bg-white border border-slate-200/90 shadow-xs hover:shadow-xl hover:border-indigo-300 transition-all flex flex-col justify-between overflow-hidden"
            >
              <div>
                {/* Product Image with Fallback and Badges */}
                <div className="relative aspect-3/4 overflow-hidden bg-slate-100">
                  <img
                    src={garment.image}
                    alt={garment.name}
                    className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-500"
                    loading="lazy"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                      e.currentTarget.nextElementSibling?.classList.remove('hidden');
                    }}
                  />

                  {/* Fallback Container if Image Fails */}
                  <div
                    className={`hidden w-full h-full bg-gradient-to-tr ${garment.fallbackBg} flex flex-col items-center justify-center text-white/80 p-4`}
                  >
                    <Shirt className="w-16 h-16 mb-2" />
                    <span className="text-xs font-semibold text-white/90">{garment.name}</span>
                  </div>

                  {/* Category Pill */}
                  <span className="absolute top-3 left-3 text-[10px] uppercase font-bold tracking-wider px-2.5 py-1 rounded-full bg-slate-900/80 backdrop-blur-md text-white">
                    {garment.category}
                  </span>

                  {/* Badge */}
                  <span className="absolute top-3 right-3 text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-600 text-white shadow-xs">
                    {garment.badge}
                  </span>

                  {/* Bottom Image Tint */}
                  <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-slate-950/60 to-transparent flex items-end p-3">
                    <span className="text-xs text-white/95 font-medium">
                      {garment.fit} • {garment.color}
                    </span>
                  </div>
                </div>

                {/* Card Details */}
                <div className="p-5 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-base text-slate-900 group-hover:text-indigo-600 transition-colors leading-snug">
                      {garment.name}
                    </h3>
                    <span className="font-black text-indigo-600 text-lg shrink-0">
                      {garment.price}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                    {garment.description}
                  </p>
                </div>
              </div>

              {/* Action Button linking to /try-on with garment parameter */}
              <div className="p-5 pt-0">
                <Button
                  to={`/try-on?garment=${garment.id}`}
                  variant="secondary"
                  size="sm"
                  leftIcon={Sparkles}
                  className="w-full justify-center group-hover:bg-indigo-600 group-hover:text-white transition-colors"
                >
                  Try On This Item
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Container>
    </div>
  );
}
