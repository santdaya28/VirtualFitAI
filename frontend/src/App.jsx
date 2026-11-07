import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import RootLayout from './layouts/RootLayout';
import ErrorBoundary from './components/ErrorBoundary';

// Route Pages - Directly imported for instant, resilient navigation
import HomePage from './pages/HomePage';
import TryOnPage from './pages/TryOnPage';
import CataloguePage from './pages/CataloguePage';
import ShopDashboardPage from './pages/ShopDashboardPage';
import AboutPage from './pages/AboutPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route element={<RootLayout />}>
            <Route index element={<HomePage />} />
            <Route path="try-on" element={<TryOnPage />} />
            <Route path="catalogue" element={<CataloguePage />} />
            <Route path="shop-dashboard" element={<ShopDashboardPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
