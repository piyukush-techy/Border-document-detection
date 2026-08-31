import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

const ProgressBar = ({ 
  value, 
  max = 100, 
  label, 
  showValue = true,
  invert = false,
  className 
}) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  const getColor = () => {
    if (invert) {
      if (percentage < 35) return 'bg-emerald-500';
      if (percentage < 60) return 'bg-amber-500';
      return 'bg-red-500';
    }
    if (percentage > 65) return 'bg-emerald-500';
    if (percentage >= 40) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between text-sm">
        {label && <span className="text-gray-400 font-medium">{label}</span>}
        {showValue && <span className="text-gray-200 font-mono">{Math.round(value)}%</span>}
      </div>
      <div className="h-2 bg-dark-900 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={cn('h-full rounded-full', getColor())}
        />
      </div>
    </div>
  );
};

export default ProgressBar;