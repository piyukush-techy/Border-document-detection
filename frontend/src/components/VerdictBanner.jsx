import React from 'react';
import { motion } from 'framer-motion';
import { Shield, AlertTriangle, XCircle, CheckCircle2 } from 'lucide-react';
import { cn } from '../lib/utils';

const VerdictBanner = ({ verdict, score, hardGated, hardGateReason, reasons }) => {
  const verdictConfig = {
    GENUINE: {
      icon: CheckCircle2,
      bgGradient: 'from-emerald-900/50 to-dark-900',
      borderColor: 'border-emerald-500/30',
      glow: 'shadow-emerald-500/20',
      iconBg: 'bg-emerald-500/20',
      iconBorder: 'border-emerald-500/30',
      iconColor: 'text-emerald-400',
      textColor: 'text-emerald-400',
      scoreRing: 'border-emerald-500/30',
      scoreSpinner: 'border-t-emerald-500',
    },
    SUSPICIOUS: {
      icon: AlertTriangle,
      bgGradient: 'from-amber-900/50 to-dark-900',
      borderColor: 'border-amber-500/30',
      glow: 'shadow-amber-500/20',
      iconBg: 'bg-amber-500/20',
      iconBorder: 'border-amber-500/30',
      iconColor: 'text-amber-400',
      textColor: 'text-amber-400',
      scoreRing: 'border-amber-500/30',
      scoreSpinner: 'border-t-amber-500',
    },
    FAKE: {
      icon: XCircle,
      bgGradient: 'from-red-900/50 to-dark-900',
      borderColor: 'border-red-500/30',
      glow: 'shadow-red-500/20',
      iconBg: 'bg-red-500/20',
      iconBorder: 'border-red-500/30',
      iconColor: 'text-red-400',
      textColor: 'text-red-400',
      scoreRing: 'border-red-500/30',
      scoreSpinner: 'border-t-red-500',
    },
  };

  const config = verdictConfig[verdict] || verdictConfig.FAKE;
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        'rounded-2xl p-8 border-2 backdrop-blur-xl',
        `bg-gradient-to-br ${config.bgGradient}`,
        config.borderColor,
        `shadow-2xl ${config.glow}`
      )}
    >
      <div className="flex items-start justify-between gap-8">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-4">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: 'spring' }}
              className={cn(
                'p-3 rounded-xl',
                config.iconBg,
                config.iconBorder
              )}
            >
              <Icon className={cn('w-8 h-8', config.iconColor)} />
            </motion.div>
            <div>
              <h3 className="text-sm font-mono text-gray-400 uppercase tracking-wider">
                Unified Risk Verdict
              </h3>
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className={cn(
                  'text-4xl font-bold mt-1',
                  config.textColor
                )}
              >
                {verdict}
              </motion.p>
            </div>
          </div>

          {hardGated && hardGateReason && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm mb-4"
            >
              <Shield className="w-4 h-4" />
              <span>Hard gate: {hardGateReason}</span>
            </motion.div>
          )}

          {reasons && reasons.length > 0 && (
            <motion.ul
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="space-y-2 mt-4"
            >
              {reasons.map((reason, index) => (
                <motion.li
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 + index * 0.1 }}
                  className="flex items-start gap-2 text-sm text-gray-300"
                >
                  <span className={cn('mt-0.5', config.textColor)}>›</span>
                  <span>{reason}</span>
                </motion.li>
              ))}
            </motion.ul>
          )}
        </div>

        <motion.div
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ delay: 0.4, type: 'spring' }}
          className="relative"
        >
          <div className={cn(
            'w-32 h-32 rounded-full border-4 flex items-center justify-center',
            config.scoreRing,
            'bg-dark-900/50'
          )}>
            <div className="text-center">
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                className={cn('text-4xl font-bold', config.textColor)}
              >
                {score}
              </motion.span>
              <span className="text-xs text-gray-500 block mt-1">/ 100</span>
            </div>
          </div>
          <motion.div
            className={cn(
              'absolute inset-0 rounded-full border-4 border-transparent',
              config.scoreSpinner,
              'animate-spin'
            )}
            style={{ animationDuration: '3s' }}
          />
        </motion.div>
      </div>
    </motion.div>
  );
};

export default VerdictBanner;