import { motion } from 'motion/react';
import { Shield, Lock, User, ArrowRight } from 'lucide-react';
import { useState } from 'react';

export default function Auth({ setView }: { setView: (view: string) => void, key?: string }) {
  const [isLogin, setIsLogin] = useState(true);

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="min-h-screen w-full bg-midnight flex items-center justify-center p-6 relative overflow-hidden text-ghost"
    >
      {/* Background Elements */}
      <div className="absolute inset-0 z-0">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-electric/10 rounded-full blur-[100px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-900/20 rounded-full blur-[100px]" />
      </div>

      <motion.div 
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.8, ease: "easeOut" }}
        className="w-full max-w-md liquid-glass rounded-2xl p-8 z-10 relative"
      >
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-electric/10 flex items-center justify-center border border-electric/30 shadow-[0_0_30px_rgba(56,189,248,0.2)]">
            <Shield className="w-8 h-8 text-electric" />
          </div>
        </div>

        <div className="text-center mb-8">
          <h2 className="font-serif text-3xl mb-2">{isLogin ? 'Secure Access' : 'Initialize Node'}</h2>
          <p className="text-white/50 text-sm">Enter your credentials to access the command center.</p>
        </div>

        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); setView('dashboard'); }}>
          {!isLogin && (
            <div className="space-y-1">
              <label className="text-xs font-mono text-white/50 uppercase tracking-wider">Operator ID</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/30" />
                <input 
                  type="text" 
                  className="w-full bg-black/20 border border-white/10 rounded-lg py-3 pl-10 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 focus:ring-1 focus:ring-electric/50 transition-all"
                  placeholder="OP-7742"
                />
              </div>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs font-mono text-white/50 uppercase tracking-wider">Email Designation</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/30" />
              <input 
                type="email" 
                className="w-full bg-black/20 border border-white/10 rounded-lg py-3 pl-10 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 focus:ring-1 focus:ring-electric/50 transition-all"
                placeholder="operator@velorah.com"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-mono text-white/50 uppercase tracking-wider">Encryption Key</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/30" />
              <input 
                type="password" 
                className="w-full bg-black/20 border border-white/10 rounded-lg py-3 pl-10 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 focus:ring-1 focus:ring-electric/50 transition-all"
                placeholder="••••••••••••"
              />
            </div>
          </div>

          <button 
            type="submit"
            className="w-full py-3 mt-6 bg-electric text-midnight font-medium rounded-lg hover:bg-electric/90 transition-colors flex items-center justify-center gap-2 group"
          >
            {isLogin ? 'Authenticate' : 'Establish Connection'}
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </form>

        <div className="mt-6 text-center">
          <button 
            onClick={() => setIsLogin(!isLogin)}
            className="text-sm text-white/50 hover:text-electric transition-colors"
          >
            {isLogin ? 'Request new access node?' : 'Return to authentication?'}
          </button>
        </div>
      </motion.div>
      
      <button 
        onClick={() => setView('home')}
        className="absolute top-6 left-6 text-white/50 hover:text-white text-sm font-mono transition-colors"
      >
        ← RETURN TO ORIGIN
      </button>
    </motion.div>
  );
}
