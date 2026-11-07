import React from 'react';

/**
 * Reusable Container component to constrain maximum width and provide consistent padding
 */
export default function Container({
  children,
  className = '',
  size = 'default', // 'narrow', 'default', 'wide', 'full'
  as: Component = 'div',
  ...props
}) {
  const sizeClasses = {
    narrow: 'max-w-4xl',
    default: 'max-w-7xl',
    wide: 'max-w-screen-2xl',
    full: 'max-w-full',
  };

  return (
    <Component
      className={`mx-auto w-full px-4 sm:px-6 lg:px-8 ${sizeClasses[size] || sizeClasses.default} ${className}`}
      {...props}
    >
      {children}
    </Component>
  );
}

