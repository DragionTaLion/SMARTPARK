/**
 * StatsPanel — Hiển thị metrics thống kê bãi đỗ xe
 * Dữ liệu thật từ /api/stats qua SmartParkContext
 * Animated counters giữ phong cách Velorah
 */

import { motion } from 'motion/react';
import { useSmartPark } from '../context/SmartParkContext';
import { Car, LogIn, LogOut, ShieldAlert, Loader2 } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: number | null;
  icon: React.ReactNode;
  color: string;
  delay?: number;
}

function StatCard({ label, value, icon, color, delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ y: 10, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay, duration: 0.5, ease: 'easeOut' }}
      className="flex-1 min-w-0 p-3 rounded-xl liquid-glass flex items-center gap-3 border border-white/5"
    >
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: `${color}20`, border: `1px solid ${color}40` }}
      >
        <div style={{ color }}>{icon}</div>
      </div>
      <div className="min-w-0">
        <div className="text-white/40 text-[9px] font-mono uppercase tracking-wider truncate">{label}</div>
        <motion.div
          key={value}
          initial={{ scale: 1.2, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="text-white font-bold text-lg leading-none mt-0.5"
          style={{ color: value === null ? undefined : color }}
        >
          {value === null ? (
            <Loader2 className="w-4 h-4 animate-spin text-white/30" />
          ) : value}
        </motion.div>
      </div>
    </motion.div>
  );
}

export default function StatsPanel() {
  const { stats, isLoading } = useSmartPark();

  return (
    <div className="flex gap-2 flex-wrap">
      <StatCard
        label="Xe trong bãi"
        value={isLoading ? null : (stats?.inside ?? 0)}
        icon={<Car className="w-4 h-4" />}
        color="#38BDF8"
        delay={0.1}
      />
      <StatCard
        label="Lượt vào hôm nay"
        value={isLoading ? null : (stats?.entries_today ?? 0)}
        icon={<LogIn className="w-4 h-4" />}
        color="#4ADE80"
        delay={0.2}
      />
      <StatCard
        label="Lượt ra"
        value={isLoading ? null : (stats?.exits_today ?? 0)}
        icon={<LogOut className="w-4 h-4" />}
        color="#94A3B8"
        delay={0.3}
      />
      <StatCard
        label="Xe lạ"
        value={isLoading ? null : (stats?.strangers_today ?? 0)}
        icon={<ShieldAlert className="w-4 h-4" />}
        color="#F87171"
        delay={0.4}
      />
    </div>
  );
}
