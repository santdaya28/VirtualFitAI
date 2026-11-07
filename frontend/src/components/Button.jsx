import React from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

/**
 * Reusable Button component with multiple variants, sizes, icon slots, and safe disabled router link support
 */
export default function Button({
  children,
  type = 'button',
  variant = 'primary', // 'primary', 'secondary', 'outline', 'ghost', 'white'
  size = 'md', // 'sm', 'md', 'lg'
  isLoading = false,
  disabled = false,
  to,
  href,
  className = '',
  leftIcon: LeftIcon,
  rightIcon: RightIcon,
  icon: Icon,
  iconPosition = 'left',
  ...props
}) {
  // Support both explicit leftIcon/rightIcon and legacy icon + iconPosition
  const ResolvedLeftIcon = LeftIcon || (iconPosition === 'left' ? Icon : null);
  const ResolvedRightIcon = RightIcon || (iconPosition === 'right' ? Icon : null);

  const isActuallyDisabled = disabled || isLoading;

  const baseStyles =
    'inline-flex items-center justify-center font-medium transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed select-none rounded-xl active:scale-[0.98] cursor-pointer';

  const variants = {
    primary:
      'bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 text-white shadow-sm hover:from-indigo-500 hover:to-purple-500 hover:shadow-md hover:shadow-indigo-500/25 focus-visible:ring-indigo-500',
    secondary:
      'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 active:bg-indigo-200/70 focus-visible:ring-indigo-400 border border-indigo-100',
    outline:
      'border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 hover:border-slate-400 focus-visible:ring-slate-400 shadow-xs',
    ghost:
      'text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus-visible:ring-slate-400',
    white:
      'bg-white text-slate-900 hover:bg-slate-100 shadow-md focus-visible:ring-white',
  };

  const sizes = {
    sm: 'text-xs px-3 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2.5 gap-2',
    lg: 'text-base px-6 py-3.5 gap-2.5 font-semibold',
  };

  const combinedClasses = `${baseStyles} ${variants[variant] || variants.primary} ${sizes[size] || sizes.md} ${className} ${
    isActuallyDisabled ? 'cursor-not-allowed pointer-events-none' : ''
  }`;

  const content = (
    <>
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-current shrink-0" />
      ) : ResolvedLeftIcon ? (
        <ResolvedLeftIcon className="w-4 h-4 shrink-0" />
      ) : null}
      {children && <span>{children}</span>}
      {!isLoading && ResolvedRightIcon ? (
        <ResolvedRightIcon className="w-4 h-4 shrink-0" />
      ) : null}
    </>
  );

  // If a router link is disabled or loading, do not render an active anchor tag
  if (to && !isActuallyDisabled) {
    return (
      <Link to={to} className={combinedClasses} {...props}>
        {content}
      </Link>
    );
  }

  if (href && !isActuallyDisabled) {
    return (
      <a href={href} className={combinedClasses} {...props}>
        {content}
      </a>
    );
  }

  return (
    <button
      type={type}
      disabled={isActuallyDisabled}
      className={combinedClasses}
      {...props}
    >
      {content}
    </button>
  );
}
