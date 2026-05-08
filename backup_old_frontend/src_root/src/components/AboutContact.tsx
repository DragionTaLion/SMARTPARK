import { motion } from 'motion/react';
import Navbar from './Navbar';
import { Server, Cpu, Network, Send } from 'lucide-react';

export default function AboutContact({ setView }: { setView: (view: string) => void, key?: string }) {
  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="min-h-screen w-full bg-midnight relative overflow-hidden text-ghost"
    >
      <Navbar setView={setView} currentView="about" />

      {/* Background Elements */}
      <div className="absolute inset-0 z-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-electric/5 rounded-full blur-[120px]" />
      </div>

      <div className="relative z-10 container mx-auto px-6 pt-32 pb-20">
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.8, ease: "easeOut" }}
          className="text-center mb-20"
        >
          <h1 className="font-serif text-5xl md:text-7xl mb-6">System Architecture</h1>
          <p className="text-white/60 max-w-2xl mx-auto text-lg">
            Velorah provides unprecedented visibility into global infrastructure through advanced neural processing and real-time data synthesis.
          </p>
        </motion.div>

        {/* About Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-32">
          {[
            { icon: Server, title: "Distributed Nodes", desc: "Global edge network ensuring sub-10ms latency for all video feeds." },
            { icon: Cpu, title: "Neural Processing", desc: "Real-time object detection and tracking powered by custom silicon." },
            { icon: Network, title: "Data Synthesis", desc: "Aggregating petabytes of telemetry into actionable intelligence." }
          ].map((item, i) => (
            <motion.div
              key={i}
              initial={{ y: 30, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.4 + (i * 0.1), duration: 0.8, ease: "easeOut" }}
              className="liquid-glass p-8 rounded-2xl border border-white/10 hover:border-electric/30 transition-colors group"
            >
              <div className="w-12 h-12 rounded-xl bg-electric/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <item.icon className="w-6 h-6 text-electric" />
              </div>
              <h3 className="text-xl font-medium mb-3">{item.title}</h3>
              <p className="text-white/50 leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>

        {/* Contact Form */}
        <motion.div
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.8, ease: "easeOut" }}
          className="max-w-3xl mx-auto liquid-glass rounded-3xl p-10 border border-white/10 relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 w-64 h-64 bg-electric/10 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/2" />
          
          <div className="relative z-10">
            <h2 className="font-serif text-4xl mb-2">Establish Contact</h2>
            <p className="text-white/50 mb-8">Request enterprise access or technical support.</p>

            <form className="space-y-6" onSubmit={(e) => e.preventDefault()}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-xs font-mono text-white/50 uppercase tracking-wider">Designation</label>
                  <input type="text" className="w-full bg-black/20 border border-white/10 rounded-lg py-3 px-4 text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 transition-colors" placeholder="John Doe" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-mono text-white/50 uppercase tracking-wider">Comms Link</label>
                  <input type="email" className="w-full bg-black/20 border border-white/10 rounded-lg py-3 px-4 text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 transition-colors" placeholder="john@company.com" />
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="text-xs font-mono text-white/50 uppercase tracking-wider">Transmission</label>
                <textarea rows={4} className="w-full bg-black/20 border border-white/10 rounded-lg py-3 px-4 text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 transition-colors resize-none" placeholder="Enter your message sequence..." />
              </div>

              <button className="px-8 py-4 bg-white text-midnight font-medium rounded-lg hover:bg-white/90 transition-colors flex items-center gap-2 group w-full justify-center">
                Transmit Data
                <Send className="w-4 h-4 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
              </button>
            </form>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
