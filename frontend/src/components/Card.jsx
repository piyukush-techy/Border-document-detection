import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

const Card = React.forwardRef(({ 
  className, 
  children, 
  hover = true,
  delay = 0,
  ...props 
}, ref) => {
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
      className={cn(
        'rounded-xl bg-dark-800/50 backdrop-blur-xl border border-gray-800',
        'shadow-xl overflow-hidden',
        hover && 'hover:border-primary-500/30 hover:shadow-2xl hover:shadow-primary-500/10',
        'transition-all duration-300',
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
});

Card.displayName = 'Card';

const CardHeader = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('p-6 border-b border-gray-800', className)}
    {...props}
  >
    {children}
  </div>
));

CardHeader.displayName = 'CardHeader';

const CardContent = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('p-6', className)}
    {...props}
  >
    {children}
  </div>
));

CardContent.displayName = 'CardContent';

const CardFooter = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('p-6 border-t border-gray-800', className)}
    {...props}
  >
    {children}
  </div>
));

CardFooter.displayName = 'CardFooter';

export { Card, CardHeader, CardContent, CardFooter };