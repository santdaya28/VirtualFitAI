import React, { useState, useRef } from 'react';
import {
  Store,
  Mail,
  Phone,
  MapPin,
  Upload,
  X,
  Save,
  CheckCircle,
} from 'lucide-react';
import Button from '../Button';

export default function ShopProfileTab({
  shopProfile,
  onSaveProfile,
}) {
  const fileInputRef = useRef(null);

  // Derive and track prop changes without setState in useEffect
  const [prevProfile, setPrevProfile] = useState(shopProfile);
  const [name, setName] = useState(shopProfile.name || '');
  const [description, setDescription] = useState(shopProfile.description || '');
  const [email, setEmail] = useState(shopProfile.email || '');
  const [phone, setPhone] = useState(shopProfile.phone || '');
  const [address, setAddress] = useState(shopProfile.address || '');
  const [logoPreview, setLogoPreview] = useState(shopProfile.logo || null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  if (shopProfile !== prevProfile) {
    setPrevProfile(shopProfile);
    setName(shopProfile.name || '');
    setDescription(shopProfile.description || '');
    setEmail(shopProfile.email || '');
    setPhone(shopProfile.phone || '');
    setAddress(shopProfile.address || '');
    setLogoPreview(shopProfile.logo || null);
  }

  const handleLogoUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('Please select an image file (JPG, PNG, or WebP).');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert('Logo file size cannot exceed 5 MB.');
      return;
    }

    const preview = URL.createObjectURL(file);
    setLogoPreview(preview);
    e.target.value = '';
  };

  const handleRemoveLogo = () => {
    if (logoPreview && logoPreview.startsWith('blob:')) {
      URL.revokeObjectURL(logoPreview);
    }
    setLogoPreview(null);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSaveProfile({
      name: name.trim(),
      description: description.trim(),
      email: email.trim(),
      phone: phone.trim(),
      address: address.trim(),
      logo: logoPreview,
    });
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 4000);
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Header */}
      <div className="pb-4 border-b border-slate-200">
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
          Shop Profile & Retailer Identity
        </h2>
        <p className="text-xs sm:text-sm text-slate-500">
          Configure your store branding, contact information, and physical address shown to shoppers.
        </p>
      </div>

      {/* Success Alert */}
      {saveSuccess && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between gap-3 animate-fadeIn">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>
              <strong>Shop profile updated!</strong> Changes have been applied to your store identity.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setSaveSuccess(false)}
            className="p-1 hover:bg-emerald-100 rounded text-emerald-700 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Form Column */}
        <div className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-8 shadow-xs">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Logo Upload Section */}
            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-700">Store Logo</label>
              <div className="flex items-center gap-4">
                <div className="w-20 h-20 rounded-2xl border-2 border-slate-200 bg-slate-50 flex items-center justify-center overflow-hidden shrink-0 shadow-2xs">
                  {logoPreview ? (
                    <img
                      src={logoPreview}
                      alt="Store Logo"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <Store className="w-8 h-8 text-indigo-400" />
                  )}
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      leftIcon={Upload}
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      {logoPreview ? 'Change Logo' : 'Upload Logo'}
                    </Button>
                    {logoPreview && (
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={X}
                        type="button"
                        onClick={handleRemoveLogo}
                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400">
                    PNG, JPG, or WebP square emblem (Recommended 512x512).
                  </p>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleLogoUpload}
                  className="hidden"
                />
              </div>
            </div>

            {/* Shop Name */}
            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-700">
                Garment Shop Name <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <Store className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Royal Heritage Garments & Boutiques"
                  className="w-full pl-9 pr-3 py-2.5 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Description */}
            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-700">
                Shop Bio & Tagline
              </label>
              <textarea
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Briefly describe your fashion collection, heritage, tailoring specialty, and shopping experience."
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>

            {/* Contact Email & Phone */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block text-xs font-bold text-slate-700">Contact Email</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="contact@royalheritage.in"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-slate-700">Phone Number</label>
                <div className="relative">
                  <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 98765 43210"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              </div>
            </div>

            {/* Physical Address */}
            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-700">
                Store Location / Physical Address
              </label>
              <div className="relative">
                <MapPin className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <textarea
                  rows={2}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="Street, Landmark, City, State, PIN Code"
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Save Button */}
            <div className="pt-3">
              <Button variant="primary" size="md" leftIcon={Save} type="submit">
                Save Profile Changes
              </Button>
            </div>
          </form>
        </div>

        {/* Right Column: Live Retailer Preview Card */}
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-3xl bg-gradient-to-b from-indigo-900 to-slate-900 text-white p-6 shadow-md border border-indigo-800/50">
            <div className="flex items-center gap-2 text-indigo-300 text-xs font-semibold mb-4">
              <Store className="w-4 h-4 text-indigo-400" />
              <span>Public Storefront Preview</span>
            </div>

            <div className="flex items-center gap-3.5 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-white/10 border border-white/20 flex items-center justify-center overflow-hidden shrink-0 shadow-inner">
                {logoPreview ? (
                  <img src={logoPreview} alt="Logo" className="w-full h-full object-cover" />
                ) : (
                  <Store className="w-7 h-7 text-white" />
                )}
              </div>
              <div className="min-w-0">
                <h4 className="font-bold text-lg text-white leading-tight truncate">
                  {name || 'Your Garment Shop'}
                </h4>
                <p className="text-xs text-indigo-200 flex items-center gap-1 mt-0.5">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> VirtualFit AI Partner Boutique
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed mb-4">
              {description ||
                'Premier boutique tailored for high-accuracy virtual clothing fitting and instant retail preview.'}
            </p>

            <div className="border-t border-white/10 pt-4 space-y-2 text-xs text-slate-300">
              <div className="flex items-center gap-2">
                <Mail className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span className="truncate">{email || 'Not specified'}</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span>{phone || 'Not specified'}</span>
              </div>
              <div className="flex items-start gap-2">
                <MapPin className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                <span className="line-clamp-2">{address || 'Not specified'}</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4 text-xs text-slate-600 space-y-1.5">
            <p className="font-bold text-slate-900">Retailer Profile Notice</p>
            <p className="text-[11px] leading-relaxed text-slate-500">
              This information is configured for your store's in-store tablet kiosk and web showcase. In Step 2, shop profiles synchronize directly with PostgreSQL.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
