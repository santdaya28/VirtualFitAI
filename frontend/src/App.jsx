import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import RootLayout from './layouts/RootLayout';
import Loading from './components/Loading';

// Route Pages
const HomePage = lazy(() => import('./pages/HomePage'));
const TryOnPage = lazy(() => import('./pages/TryOnPage'));
const CataloguePage = lazy(() => import('./pages/CataloguePage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading fullPage message="Loading VirtualFit AI..." />}>
        <Routes>
          <Route element={<RootLayout />}>
            <Route index element={<HomePage />} />
            <Route path="try-on" element={<TryOnPage />} />
            <Route path="catalogue" element={<CataloguePage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
