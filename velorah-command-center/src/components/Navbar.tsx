import { motion } from 'motion/react';
import { ShieldAlert } from 'lucide-react';

export default function Navbar({ setView, currentView }: { setView: (view: string) => void, currentView: string }) {
  return (
    <motion.nav 
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: "easeOut" }}
      className="fixed top-0 left-0 right-0 z-50 px-6 py-4 flex items-center justify-between liquid-glass border-b border-white/10"
    >
      <div 
        className="flex items-center gap-3 cursor-pointer group"
        onClick={() => setView('home')}
      >
        <div className="w-10 h-10 rounded-xl bg-electric/10 flex items-center justify-center border border-electric/30 group-hover:bg-electric/20 transition-colors">
          <ShieldAlert className="w-5 h-5 text-electric" />
        </div>
        <span className="font-serif text-2xl tracking-wide text-white">Velorah</span>
      </div>

      <div className="hidden md:flex items-center gap-8 font-mono text-xs tracking-widest text-white/50">
        <button 
          onClick={() => setView('home')}
          className={`hover:text-electric transition-colors ${currentView === 'home' ? 'text-electric' : ''}`}
        >
          TECHNOLOGY
        </button>
        <button 
          onClick={() => setView('about')}
          className={`hover:text-electric transition-colors ${currentView === 'about' ? 'text-electric' : ''}`}
        >
          ABOUT
        </button>
        <button 
          onClick={() => setView('about')}
          className="hover:text-electric transition-colors"
        >
          CONTACT
        </button>
      </div>

      <div className="flex items-center gap-4">
        <button 
          onClick={() => setView('auth')}
          className="px-5 py-2 rounded-lg text-sm font-medium text-white/70 hover:text-white hover:bg-white/5 transition-colors"
        >
          Login
        </button>
        <button 
          onClick={() => setView('auth')}
          className="px-5 py-2 rounded-lg text-sm font-medium bg-electric/10 text-electric border border-electric/30 hover:bg-electric/20 transition-colors shadow-[0_0_15px_rgba(56,189,248,0.2)]"
        >
          Join Now
        </button>
      </div>
    </motion.nav>
  );
}
