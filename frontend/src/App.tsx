import { useState } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';

import { AdminPanel } from './components/AdminPanel';
import { AuthModal } from './components/AuthModal';
import { NavBar } from './components/NavBar';
import { FavoritesPage } from './pages/FavoritesPage';
import { HomePage } from './pages/HomePage';

export default function App() {
  const [showAuth, setShowAuth] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);

  return (
    <BrowserRouter>
      <div className="page-shell">
        <div className="aurora aurora-left" />
        <div className="aurora aurora-right" />

        <Toaster position="bottom-right" richColors closeButton />

        <NavBar onShowAuth={() => setShowAuth(true)} onShowAdmin={() => setShowAdmin(true)} />

        <main className="content">
          <Routes>
            <Route path="/" element={<HomePage onShowAuth={() => setShowAuth(true)} />} />
            <Route path="/favorites" element={<FavoritesPage onShowAuth={() => setShowAuth(true)} />} />
          </Routes>
        </main>

        {showAuth ? <AuthModal onClose={() => setShowAuth(false)} /> : null}
        {showAdmin ? <AdminPanel onClose={() => setShowAdmin(false)} /> : null}
      </div>
    </BrowserRouter>
  );
}
