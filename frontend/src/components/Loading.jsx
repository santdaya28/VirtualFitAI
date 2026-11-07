import React from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Reusable Loading state component
 */
export default function Loading({
  message = 'Loading...',
  size = 'md', // 'sm', 'md', 'lg'
  fullPage = false,
  className = '',
}) {
  const sizeClasses = {
    sm: {
      spinner: 'w-4 h-4',
      text: 'text-xs',
    },
    md: {
      spinner: 'w-7 h-7',
      text: 'text-sm',
    },
    lg: {
      spinner: 'w-10 h-10',
      text: 'text-base',
    },
  };

  const selected = sizeClasses[size] || sizeClasses.md;

  const content = (
    <div className={`flex flex-col items-center justify-center gap-3 p-6 ${className}`}>
      <div className="relative flex items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-indigo-500/10 animate-ping" />
        <Loader2 className={`${selected.spinner} text-indigo-600 animate-spin`} />
      </div>
      {message && (
        <p className={`font-medium text-slate-500 ${selected.text}`}>
          {message}
        </p>
      )}
    </div>
  );

  if (fullPage) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center w-full">
        {content}
      </div>
    );
  }

  return content;
}

