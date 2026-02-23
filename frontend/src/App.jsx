import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import AppShell from './components/layout/AppShell';
import LandingPage from './pages/LandingPage';
import ChatPage from './pages/ChatPage';
import DocumentsPage from './pages/DocumentsPage';

import './styles/variables.css';
import './styles/reset.css';
import './styles/animations.css';
import './styles/layout.css';

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.4, 0, 0.2, 1] } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

function AnimatedPage({ children }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
    >
      {children}
    </motion.div>
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route element={<AppShell />}>
          <Route path="/" element={<AnimatedPage><LandingPage /></AnimatedPage>} />
          <Route path="/chat" element={<AnimatedPage><ChatPage /></AnimatedPage>} />
          <Route path="/documents" element={<AnimatedPage><DocumentsPage /></AnimatedPage>} />
        </Route>
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AnimatedRoutes />
    </BrowserRouter>
  );
}
