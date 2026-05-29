import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import Layout from "./components/Layout";
import AuthPage from "./pages/AuthPage";
import HomePage from "./pages/HomePage";
import ClansPage from "./pages/ClansPage";
import ClanDetailPage from "./pages/ClanDetailPage";
import MatchesPage from "./pages/MatchesPage";
import MatchDetailPage from "./pages/MatchDetailPage";
import PlayersPage from "./pages/PlayersPage";
import LeaderboardPage from "./pages/LeaderboardPage";
import ProfilePage from "./pages/ProfilePage";
import AdminPage from "./pages/AdminPage";
import RulesPage from "./pages/RulesPage";
import TournamentsPage from "./pages/TournamentsPage";
import TournamentDetailPage from "./pages/TournamentDetailPage";
import BlacklistPage from "./pages/BlacklistPage";
import PersonalPlusPage from "./pages/PersonalPlusPage";
import PlayerProfilePage from "./pages/PlayerProfilePage";
import LeaguesPage from "./pages/LeaguesPage";
import { Toaster } from "sonner";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen grid place-items-center text-white/40">...</div>;
  if (!user) return <Navigate to="/auth" replace />;
  return children;
}

function PublicShell({ children }) {
  const { loading } = useAuth();
  if (loading) return <div className="min-h-screen grid place-items-center text-white/40">...</div>;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/auth" element={<AuthPage />} />

      <Route path="/" element={<PublicShell><HomePage /></PublicShell>} />
      <Route path="/clans" element={<PublicShell><ClansPage /></PublicShell>} />
      <Route path="/clans/:id" element={<PublicShell><ClanDetailPage /></PublicShell>} />
      <Route path="/matches" element={<PublicShell><MatchesPage /></PublicShell>} />
      <Route path="/players" element={<PublicShell><PlayersPage /></PublicShell>} />
      <Route path="/players/:id" element={<PublicShell><PlayerProfilePage /></PublicShell>} />
      <Route path="/leaderboard" element={<PublicShell><LeaderboardPage /></PublicShell>} />
      <Route path="/leagues" element={<PublicShell><LeaguesPage /></PublicShell>} />
      <Route path="/rules" element={<PublicShell><RulesPage /></PublicShell>} />
      <Route path="/tournaments" element={<PublicShell><TournamentsPage /></PublicShell>} />
      <Route path="/tournaments/:id" element={<PublicShell><TournamentDetailPage /></PublicShell>} />
      <Route path="/blacklist" element={<PublicShell><BlacklistPage /></PublicShell>} />
      <Route path="/plus" element={<PublicShell><PersonalPlusPage /></PublicShell>} />

      <Route path="/matches/:id" element={<Protected><Layout><MatchDetailPage /></Layout></Protected>} />
      <Route path="/me" element={<Protected><Layout><ProfilePage /></Layout></Protected>} />
      <Route path="/admin" element={<Protected><Layout><AdminPage /></Layout></Protected>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster position="top-center" theme="dark" richColors />
      </BrowserRouter>
    </AuthProvider>
  );
}
