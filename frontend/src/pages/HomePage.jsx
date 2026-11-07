import React from 'react';
import { Link } from 'react-router-dom';
import {
  Sparkles,
  ArrowRight,
  Shirt,
  Store,
  Users,
  Zap,
  CheckCircle2,
  Camera,
  TrendingUp,
  ShieldAlert,
  Clock,
  Palette,
  ShoppingBag,
} from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';

export default function HomePage() {
  const steps = [
    {
      number: '01',
      title: 'Upload Your Photo',
      description:
        'Take a quick full-body or upper-body photo in normal posture. No specialized 3D scanners or hardware required.',
      icon: Camera,
    },
    {
      number: '02',
      title: 'Select Your Outfit',
      description:
        'Pick any blazer, shirt, dress, or ethnic piece from your store catalogue or digital clothing rack.',
      icon: Shirt,
    },
    {
      number: '03',
      title: 'Preview Your Look',
      description:
        'Our upcoming AI models will visualize realistic fabric drape, fit proportions, and color matching on your silhouette (Integration coming soon).',
      icon: Sparkles,
    },
  ];

  const retailerBenefits = [
    {
      icon: Clock,
      title: 'Eliminate Fitting Room Queues',
      description:
        'Speed up peak shopping hours. Customers try multiple combinations digitally before taking their final picks to the trial room.',
    },
    {
      icon: ShieldAlert,
      title: 'Protect Delicate Inventory',
      description:
        'Prevent makeup stains, zipper tears, and fabric stretching on expensive silk, formal suits, and festive ethnic wear.',
    },
    {
      icon: TrendingUp,
      title: 'Boost In-Store Conversions',
      description:
        'Shops using interactive virtual fitting see higher customer engagement and an average 28% increase in cart checkouts.',
    },
    {
      icon: Store,
      title: 'Omnichannel In-Store & Online',
      description:
        'Deploy effortlessly on sales-floor tablets or embed on your boutique website for remote shoppers.',
    },
  ];

  const customerBenefits = [
    {
      icon: Zap,
      title: 'Try 10 Outfits in 60 Seconds',
      description:
        'Skip the fatigue of changing clothes repeatedly. Compare different styles, cuts, and colors in seconds.',
    },
    {
      icon: Users,
      title: 'Personalized to Your Silhouette',
      description:
        'See how clothes actually drape on your unique body shape rather than on studio mannequins.',
    },
    {
      icon: Palette,
      title: 'Explore New Styles Confidently',
      description:
        'Experiment with bold colors, formal tuxedos, or intricate ethnic attire you might usually hesitate to try on.',
    },
    {
      icon: ShoppingBag,
      title: 'Zero Pressure Shopping',
      description:
        'Browse at your own pace with digital previews that take the guesswork out of sizing and fit.',
    },
  ];

  return (
    <div className="flex flex-col gap-16 lg:gap-24 pt-6 pb-16 sm:pt-8 sm:pb-20">
      {/* Hero Section */}
      <section className="relative overflow-hidden scroll-mt-24">
        {/* Ambient Gradient Glows */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-tr from-indigo-300/20 to-purple-300/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/3 right-10 w-80 h-80 bg-purple-200/20 rounded-full blur-3xl pointer-events-none" />

        <Container>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
            {/* Left Column: Headline and Pitch */}
            <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold shadow-2xs">
                <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                <span>Next-Generation Virtual Fitting Room</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.12]">
                Try Before You Buy.{' '}
                <span className="bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 bg-clip-text text-transparent">
                  Virtually.
                </span>
              </h1>

              <p className="text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto lg:mx-0 leading-relaxed">
                VirtualFit AI transforms traditional garment shopping into an instant, interactive experience.
                Empower your customers to visualize outfits on their own body before purchasing, while eliminating fitting room friction and inventory wear.
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4 pt-2">
                <Button
                  to="/try-on"
                  variant="primary"
                  size="lg"
                  rightIcon={ArrowRight}
                  className="w-full sm:w-auto shadow-lg shadow-indigo-600/25"
                >
                  Start Virtual Try-On
                </Button>
                <Button
                  to="/catalogue"
                  variant="outline"
                  size="lg"
                  leftIcon={Shirt}
                  className="w-full sm:w-auto"
                >
                  Explore Catalogue
                </Button>
              </div>

              {/* Trust badges */}
              <div className="pt-6 border-t border-slate-200/80 flex flex-wrap items-center justify-center lg:justify-start gap-6 text-xs text-slate-500 font-medium">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  AI Try-On Technology – Coming Soon
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  Zero Specialized Hardware
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  Ready for In-Store Tablets
                </span>
              </div>
            </div>

            {/* Right Column: Fashion-Related Hero Visual */}
            <div className="lg:col-span-5">
              <div className="relative mx-auto max-w-md">
                {/* Outer Glow Card */}
                <div className="rounded-3xl bg-gradient-to-b from-slate-900 via-slate-950 to-indigo-950 p-6 shadow-2xl border border-slate-800 text-white relative overflow-hidden">
                  {/* Subtle top bar */}
                  <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-rose-500/90 inline-block" />
                      <span className="w-3 h-3 rounded-full bg-amber-500/90 inline-block" />
                      <span className="w-3 h-3 rounded-full bg-emerald-500/90 inline-block" />
                    </div>
                    <span className="text-[11px] font-mono text-indigo-300 font-semibold flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5" /> VirtualFit Engine
                    </span>
                  </div>

                  {/* Fashion Image Visual */}
                  <div className="mt-5 relative rounded-2xl overflow-hidden aspect-4/5 bg-slate-800 border border-slate-700/80 shadow-inner group">
                    <img
                      src="https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80"
                      alt="Fashion model trying on outfit with VirtualFit AI"
                      className="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-105"
                    />

                    {/* Gradient Overlay */}
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />

                    {/* Floating Virtual Fitting Overlay Badges */}
                    <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-md text-slate-900 text-[11px] font-bold px-3 py-1.5 rounded-xl shadow-md flex items-center gap-1.5">
                      <Shirt className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Midnight Blazer Fitted</span>
                    </div>

                    {/* Accurate Badge: Replaced Match: 98% with SAMPLE PREVIEW */}
                    <div className="absolute top-3 right-3 bg-indigo-600/90 backdrop-blur-md text-white text-[10px] font-bold px-2.5 py-1 rounded-full shadow-md uppercase tracking-wider border border-white/20">
                      SAMPLE PREVIEW
                    </div>

                    {/* Floating Bottom Metric: Replaced REAL-TIME FITTING SIMULATION with VIRTUAL TRY-ON PREVIEW */}
                    <div className="absolute bottom-4 inset-x-4 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-xl p-3.5 flex items-center justify-between">
                      <div>
                        <p className="text-[10px] uppercase font-semibold text-indigo-300">
                          VIRTUAL TRY-ON PREVIEW
                        </p>
                        <p className="text-xs font-bold text-white">
                          Planned Pose & Fabric Draping
                        </p>
                      </div>
                      <Link
                        to="/try-on"
                        className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 text-white text-xs font-semibold hover:from-indigo-500 hover:to-purple-500 transition-all flex items-center gap-1 shrink-0"
                      >
                        Try Studio <ArrowRight className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>

                  {/* Quick Workflow Pill */}
                  <div className="mt-4 flex items-center justify-between text-xs text-slate-400 px-1">
                    <span className="flex items-center gap-1.5">
                      <Camera className="w-3.5 h-3.5 text-indigo-400" /> Photo Input
                    </span>
                    <span className="text-slate-600">→</span>
                    <span className="flex items-center gap-1.5">
                      <Shirt className="w-3.5 h-3.5 text-purple-400" /> Outfit Select
                    </span>
                    <span className="text-slate-600">→</span>
                    <span className="flex items-center gap-1.5 text-indigo-300 font-semibold">
                      <Sparkles className="w-3.5 h-3.5" /> AI Try-On (Coming Soon)
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* 3-Step Explanation Section */}
      <section id="how-it-works" className="bg-white py-16 border-y border-slate-200/80 scroll-mt-24">
        <Container>
          <div className="text-center max-w-2xl mx-auto space-y-3 mb-14">
            <h2 className="text-xs font-bold text-indigo-600 uppercase tracking-widest">
              Simple & Intuitive
            </h2>
            <p className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Three Simple Steps to the Perfect Fit
            </p>
            <p className="text-sm sm:text-base text-slate-600">
              Transforming fitting rooms into a 30-second digital experience.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {steps.map((step) => {
              const Icon = step.icon;
              return (
                <div
                  key={step.number}
                  className="relative p-7 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-indigo-300 hover:bg-indigo-50/20 transition-all group shadow-2xs hover:shadow-md"
                >
                  <div className="flex items-center justify-between mb-5">
                    <span className="text-3xl font-black text-indigo-200 group-hover:text-indigo-400 transition-colors">
                      {step.number}
                    </span>
                    <div className="w-12 h-12 rounded-xl bg-white shadow-xs border border-slate-200 flex items-center justify-center text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-all">
                      <Icon className="w-6 h-6" />
                    </div>
                  </div>
                  <h3 className="font-bold text-lg text-slate-900 mb-2">
                    {step.title}
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    {step.description}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Quick CTA to try steps */}
          <div className="mt-12 text-center">
            <Button
              to="/try-on"
              variant="secondary"
              size="md"
              rightIcon={ArrowRight}
            >
              Test the 3-Step Studio Flow
            </Button>
          </div>
        </Container>
      </section>

      {/* Benefits for Customers and Garment Retailers */}
      <section id="benefits" className="scroll-mt-24">
        <Container>
          <div className="text-center max-w-2xl mx-auto space-y-3 mb-16">
            <h2 className="text-xs font-bold text-indigo-600 uppercase tracking-widest">
              Built for Value
            </h2>
            <p className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Why Retailers & Shoppers Love VirtualFit AI
            </p>
            <p className="text-sm sm:text-base text-slate-600">
              Resolving real-world retail problems with intelligent virtual fitting technology.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
            {/* Retailer Benefits Card */}
            <div className="p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-6">
              <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
                <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
                  <Store className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900">
                    For Garment Retailers
                  </h3>
                  <p className="text-xs text-slate-500">
                    Boost in-store efficiency, sales volume, and merchandise protection
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                {retailerBenefits.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.title} className="space-y-1.5">
                      <div className="flex items-center gap-2 text-indigo-600 font-semibold text-sm">
                        <Icon className="w-4 h-4 shrink-0" />
                        <span className="text-slate-900 font-bold">{item.title}</span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {item.description}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Customer Benefits Card */}
            <div className="p-8 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-6">
              <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
                <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900">
                    For Shoppers & Customers
                  </h3>
                  <p className="text-xs text-slate-500">
                    Effortless styling, zero trial room queues, and confident purchases
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                {customerBenefits.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.title} className="space-y-1.5">
                      <div className="flex items-center gap-2 text-purple-600 font-semibold text-sm">
                        <Icon className="w-4 h-4 shrink-0" />
                        <span className="text-slate-900 font-bold">{item.title}</span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {item.description}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* Final Call to Action Section */}
      <section id="cta" className="scroll-mt-24">
        <Container>
          <div className="rounded-3xl bg-gradient-to-tr from-slate-950 via-slate-900 to-indigo-950 p-8 sm:p-14 text-white text-center relative overflow-hidden shadow-2xl border border-indigo-900/40">
            {/* Background elements */}
            <div className="absolute -top-24 -left-24 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -right-24 w-72 h-72 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

            <div className="relative z-10 max-w-2xl mx-auto space-y-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-indigo-300 text-xs font-medium backdrop-blur-xs">
                <Sparkles className="w-3.5 h-3.5" />
                VirtualFit AI Platform Foundation
              </div>

              <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight leading-tight">
                Bring Virtual Fitting to Your Clothing Store Today
              </h2>

              <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
                Step into the future of retail fashion. Test our virtual try-on studio interface and explore the digital clothing catalogue.
              </p>

              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-4">
                <Button
                  to="/try-on"
                  variant="primary"
                  size="lg"
                  rightIcon={ArrowRight}
                  className="w-full sm:w-auto shadow-lg shadow-indigo-600/30"
                >
                  Start Virtual Try-On
                </Button>
                <Button
                  to="/catalogue"
                  variant="outline"
                  size="lg"
                  leftIcon={Shirt}
                  className="w-full sm:w-auto bg-white/10 text-white border-white/20 hover:bg-white/20"
                >
                  Explore Catalogue
                </Button>
              </div>
            </div>
          </div>
        </Container>
      </section>
    </div>
  );
}
