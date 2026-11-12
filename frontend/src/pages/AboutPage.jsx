import React from 'react';
import {
  Layers,
  Server,
  Database,
  Smartphone,
  Cpu,
  Store,
  ShieldCheck,
  Clock,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';

export default function AboutPage() {
  const problemsSolved = [
    {
      title: 'Long Trial Room Waiting Queues',
      description:
        'During peak retail hours and weekends, fitting rooms become the #1 conversion bottleneck. VirtualFit AI allows shoppers to test 5-10 garments digitally before stepping into a trial room.',
      icon: Clock,
    },
    {
      title: 'Costly Merchandise Damage & Wear',
      description:
        'Repeated physical trials often result in makeup stains, pulled threads, broken zippers, and fabric stretching—especially on delicate silks, bridal wear, and tailored suits.',
      icon: ShieldCheck,
    },
    {
      title: 'High Sizing Returns & Hesitation',
      description:
        'Customers frequently abandon purchases due to sizing doubts or purchase multiple sizes only to return them. Visualizing the silhouette fit upfront gives buyers immediate confidence.',
      icon: TrendingUp,
    },
    {
      title: 'Retail Floor Space Limitations',
      description:
        'Instead of dedicating massive square footage to extensive trial stalls, boutiques can deploy slim digital tablet kiosks where customers virtually try on extended warehouse inventory.',
      icon: Store,
    },
  ];

  const workflowSteps = [
    {
      step: 'Step 1',
      title: 'Customer Capture',
      desc: 'Customer takes or uploads a photo at the boutique tablet or from their own mobile browser.',
    },
    {
      step: 'Step 2',
      title: 'Catalogue Selection',
      desc: 'Browses digital racks categorized by Formal, Casual, Ethnic, and Outerwear.',
    },
    {
      step: 'Step 3',
      title: 'AI Synthesis (FASHN VTON v1.5)',
      desc: 'FastAPI backend orchestrates FASHN VTON diffusion pipeline to synthesize garments onto customer silhouettes with accurate drape.',
    },
    {
      step: 'Step 4',
      title: 'Virtual Fit Review',
      desc: 'Shopper reviews their previewed look, compares sizing options, and completes the purchase with confidence.',
    },
  ];

  const techStack = [
    {
      layer: 'Web Frontend',
      name: 'React 19 + Vite 8 + Tailwind CSS v4',
      description:
        'Ultra-fast client interface with responsive SaaS design system, Lucide icons, and React Router navigation.',
      icon: Layers,
      badge: 'Active & Compiled',
      badgeColor: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    },
    {
      layer: 'Backend API',
      name: 'Python 3.12 + FastAPI + Uvicorn',
      description:
        'High-performance asynchronous REST API handling catalogue management, image pre-processing, and AI orchestration.',
      icon: Server,
      badge: 'Environment Ready',
      badgeColor: 'text-indigo-700 bg-indigo-50 border-indigo-200',
    },
    {
      layer: 'Relational Database',
      name: 'PostgreSQL 18 + SQLAlchemy ORM',
      description:
        'Enterprise relational schema storing garment inventory metadata, boutique settings, and virtual try-on session logs.',
      icon: Database,
      badge: 'Local Server Installed',
      badgeColor: 'text-indigo-700 bg-indigo-50 border-indigo-200',
    },
    {
      layer: 'Mobile Application',
      name: 'React Native + Expo (Android)',
      description:
        'Cross-platform mobile application designed for in-store boutique tablet kiosks and direct customer smartphone try-ons.',
      icon: Smartphone,
      badge: 'Planned Mobile App',
      badgeColor: 'text-slate-700 bg-slate-100 border-slate-200',
    },
    {
      layer: 'AI Try-On Engine',
      name: 'Virtual Try-On Pipeline / Model Adapter',
      description:
        'Generative computer vision architecture planned for pose estimation, clothing segmentation, and fabric draping.',
      icon: Cpu,
      badge: 'Service Adapter Ready',
      badgeColor: 'text-purple-700 bg-purple-50 border-purple-200',
    },
  ];

  return (
    <div className="pt-6 pb-16 sm:pt-10 sm:pb-20">
      <Container>
        {/* Mission Section */}
        <div className="max-w-3xl mx-auto text-center space-y-4 mb-16 scroll-mt-28">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
            <Store className="w-3.5 h-3.5" />
            <span>VirtualFit AI Mission</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
            Empowering Garment Retailers with{' '}
            <span className="bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 bg-clip-text text-transparent">
              Intelligent Virtual Fitting
            </span>
          </h1>

          <p className="text-slate-600 text-base sm:text-lg leading-relaxed">
            Our mission is to eliminate fitting room friction, protect retail clothing inventory, and give garment shoppers the confidence to purchase outfits they love in seconds.
          </p>
        </div>

        {/* Problems We Are Solving Section */}
        <section className="mb-20 scroll-mt-28" id="retail">
          <div className="text-center max-w-xl mx-auto space-y-2 mb-10">
            <h2 className="text-xs font-bold text-indigo-600 uppercase tracking-widest">
              The Retail Challenge
            </h2>
            <p className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Problems We Are Solving for Garment Retailers
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {problemsSolved.map((prob) => {
              const Icon = prob.icon;
              return (
                <div
                  key={prob.title}
                  className="p-7 rounded-3xl bg-white border border-slate-200 shadow-xs flex items-start gap-4 hover:border-indigo-200 hover:shadow-md transition-all"
                >
                  <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                    <Icon className="w-6 h-6" />
                  </div>
                  <div className="space-y-1.5">
                    <h3 className="font-bold text-base text-slate-900">
                      {prob.title}
                    </h3>
                    <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                      {prob.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* How the Platform Works */}
        <section className="mb-20 rounded-3xl bg-white border border-slate-200 p-8 sm:p-12 shadow-xs scroll-mt-28">
          <div className="text-center max-w-xl mx-auto space-y-2 mb-10">
            <h2 className="text-xs font-bold text-indigo-600 uppercase tracking-widest">
              Architecture & Flow
            </h2>
            <p className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              How the VirtualFit AI Platform Works
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {workflowSteps.map((w) => (
              <div
                key={w.step}
                className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2"
              >
                <span className="text-xs font-bold text-indigo-600 tracking-wider uppercase">
                  {w.step}
                </span>
                <h4 className="font-bold text-sm text-slate-900">
                  {w.title}
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {w.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Technology Stack Section */}
        <section className="space-y-8 scroll-mt-28" id="technology">
          <div className="text-center max-w-xl mx-auto space-y-2">
            <h2 className="text-xs font-bold text-indigo-600 uppercase tracking-widest">
              Engineered for Scale
            </h2>
            <p className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Planned Technology Stack
            </p>
            <p className="text-sm text-slate-600">
              A modern, decoupling architecture separating high-speed frontend interfaces from high-concurrency AI workers.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
            {techStack.map((tech) => {
              const Icon = tech.icon;
              return (
                <div
                  key={tech.layer}
                  className="p-6 rounded-3xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center">
                          <Icon className="w-5 h-5" />
                        </div>
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                            {tech.layer}
                          </span>
                          <h3 className="text-sm font-bold text-slate-900">
                            {tech.name}
                          </h3>
                        </div>
                      </div>
                      <span
                        className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${tech.badgeColor}`}
                      >
                        {tech.badge}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      {tech.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Final CTA */}
        <div className="mt-16 text-center">
          <Button
            to="/try-on"
            variant="primary"
            size="lg"
            rightIcon={ArrowRight}
          >
            Launch Virtual Fitting Studio
          </Button>
        </div>
      </Container>
    </div>
  );
}
