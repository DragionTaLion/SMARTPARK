import { motion } from 'motion/react';
import Navbar from './Navbar';
import { ArrowRight } from 'lucide-react';

export default function Home({ setView }: { setView: (view: string) => void, key?: string }) {
  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="min-h-screen w-full bg-midnight relative overflow-hidden text-ghost"
    >
      <Navbar setView={setView} currentView="home" />

      {/* Hero Video Background */}
      <div className="absolute inset-0 z-0">
        <video 
          src="https://assets.mixkit.co/videos/preview/mixkit-city-traffic-on-a-highway-at-night-34530-large.mp4" 
          autoPlay 
          loop 
          muted 
          className="w-full h-full object-cover opacity-40"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-midnight/80 via-midnight/40 to-midnight/90" />
      </div>

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-6 text-center">
        <motion.div
          initial={{ y: 50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 1, ease: "easeOut" }}
          className="max-w-4xl"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full liquid-glass text-sm font-mono text-electric mb-8">
            <div className="w-2 h-2 rounded-full bg-electric animate-pulse" />
            VELORAH OS V4.2 ONLINE
          </div>
          
          <h1 className="font-serif text-6xl md:text-8xl leading-tight mb-6 text-white drop-shadow-2xl">
            Precision in Motion.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-electric to-blue-600">Performance in Every Frame.</span>
          </h1>
          
          <p className="text-xl text-white/70 mb-12 max-w-2xl mx-auto font-light">
            The ultimate high-performance command center for global node monitoring, live data analytics, and intelligent traffic routing.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
            <button 
              onClick={() => setView('dashboard')}
              className="px-8 py-4 bg-electric text-midnight font-medium rounded-lg hover:bg-electric/90 transition-all flex items-center gap-2 group text-lg"
            >
              Initialize Dashboard
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <button 
              onClick={() => setView('about')}
              className="px-8 py-4 liquid-glass text-white font-medium rounded-lg hover:bg-white/10 transition-all text-lg"
            >
              System Specifications
            </button>
          </div>
        </motion.div>
      </div>

      {/* Bottom Data Ticker */}
      <div className="absolute bottom-0 left-0 right-0 h-12 border-t border-white/10 liquid-glass flex items-center overflow-hidden z-20">
        <motion.div 
          animate={{ x: ["0%", "-50%"] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="flex whitespace-nowrap gap-12 px-6 font-mono text-xs text-electric/70"
        >
          {[...Array(10)].map((_, i) => (
            <span key={i}>NODE_{Math.floor(Math.random() * 999)}: OPTIMAL // LATENCY: {Math.floor(Math.random() * 20) + 5}MS // THROUGHPUT: {Math.floor(Math.random() * 90) + 10}TB/S</span>
          ))}
        </motion.div>
      </div>
    </motion.div>
  );
}
