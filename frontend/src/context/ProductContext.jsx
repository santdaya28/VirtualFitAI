import React, { createContext, useContext, useState, useEffect } from 'react';
import { SAMPLE_CLOTHES } from '../data/sampleClothes';

const STORAGE_KEY_PRODUCTS = 'virtualfit_demo_products_v1';
const STORAGE_KEY_PROFILE = 'virtualfit_demo_profile_v1';

export const INITIAL_PRODUCTS = SAMPLE_CLOTHES.map((item, idx) => ({
  id: item.id,
  name: item.name,
  category: item.category,
  price: parseInt(String(item.price).replace(/[^\d]/g, ''), 10) || 2999,
  description: item.description,
  sizes: ['S', 'M', 'L', 'XL'],
  colors: [item.color || 'Navy Blue'],
  image: item.image,
  status: idx % 3 === 0 ? 'In Stock' : idx % 3 === 1 ? 'Low Stock' : 'In Stock',
  fit: item.fit || 'Regular Fit',
  badge: item.badge,
  fallbackBg: item.fallbackBg,
  createdAt: new Date(Date.now() - idx * 86400000 * 2).toISOString().split('T')[0],
}));

export const INITIAL_SHOP_PROFILE = {
  name: 'Royal Heritage Garments & Boutiques',
  description:
    'Premier boutique specializing in bespoke formal blazers, handcrafted royal silk ethnic wear, and luxury contemporary attire.',
  email: 'contact@royalheritage.in',
  phone: '+91 98765 43210',
  address: '42 Commercial Street, Fashion District, Bengaluru, Karnataka 560001',
  logo: null,
};

const ProductContext = createContext({
  products: INITIAL_PRODUCTS,
  shopProfile: INITIAL_SHOP_PROFILE,
  addProduct: () => {},
  updateProduct: () => {},
  deleteProduct: () => {},
  resetToDefaults: () => {},
  updateShopProfile: () => {},
});

export function ProductProvider({ children }) {
  // Load products from localStorage with fallback to INITIAL_PRODUCTS
  const [products, setProducts] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_PRODUCTS);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch {
      // Local storage unavailable or failed parse
    }
    return INITIAL_PRODUCTS;
  });

  // Load shop profile from localStorage
  const [shopProfile, setShopProfile] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_PROFILE);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {
      // Local storage unavailable or failed parse
    }
    return INITIAL_SHOP_PROFILE;
  });

  // Sync products to localStorage on update
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_PRODUCTS, JSON.stringify(products));
    } catch {
      // Ignore quota/access errors
    }
  }, [products]);

  // Sync shopProfile to localStorage on update
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_PROFILE, JSON.stringify(shopProfile));
    } catch {
      // Ignore quota/access errors
    }
  }, [shopProfile]);

  const addProduct = (garmentData) => {
    setProducts((prev) => [garmentData, ...prev]);
  };

  const updateProduct = (garmentData) => {
    setProducts((prev) =>
      prev.map((item) => (item.id === garmentData.id ? garmentData : item))
    );
  };

  const deleteProduct = (productId) => {
    setProducts((prev) => prev.filter((item) => item.id !== productId));
  };

  const resetToDefaults = () => {
    setProducts(INITIAL_PRODUCTS);
    setShopProfile(INITIAL_SHOP_PROFILE);
    try {
      localStorage.removeItem(STORAGE_KEY_PRODUCTS);
      localStorage.removeItem(STORAGE_KEY_PROFILE);
    } catch {
      // Ignore storage errors
    }
  };

  const updateShopProfile = (updatedProfile) => {
    setShopProfile(updatedProfile);
  };

  return (
    <ProductContext.Provider
      value={{
        products,
        shopProfile,
        addProduct,
        updateProduct,
        deleteProduct,
        resetToDefaults,
        updateShopProfile,
      }}
    >
      {children}
    </ProductContext.Provider>
  );
}

export function useProducts() {
  return useContext(ProductContext);
}

