import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

const Badge = React.forwardRef(({ 
  className, 
  variant = 'default',
  children,
  ...props 
}, ref) => {
  const variants = {
    default: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    success: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-500/30',
    warning: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-500/30',
    danger: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 border border-red-500/30',
    info: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 border border-blue-500/30',
  };

  return (
    <motion.span
      ref={ref}
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </motion.span>
  );
});

Badge.displayName = 'Badge';

export default Badge;