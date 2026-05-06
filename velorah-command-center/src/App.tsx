import { useState } from 'react';
import { AnimatePresence } from 'motion/react';
import Home from './components/Home';
import Auth from './components/Auth';
import Dashboard from './components/Dashboard';
import AboutContact from './components/AboutContact';

export default function App() {
  const [view, setView] = useState('home');

  return (
    <div className="bg-midnight min-h-screen text-ghost font-sans">
      <AnimatePresence mode="wait">
        {view === 'home' && <Home key="home" setView={setView} />}
        {view === 'auth' && <Auth key="auth" setView={setView} />}
        {view === 'dashboard' && <Dashboard key="dashboard" setView={setView} />}
        {view === 'about' && <AboutContact key="about" setView={setView} />}
      </AnimatePresence>
    </div>
  );
}
