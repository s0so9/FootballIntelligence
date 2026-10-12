import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { DashboardV2 as Dashboard } from './pages/DashboardV2';
import { PopularLeagues } from './pages/PopularLeagues';
import { Upcoming } from './pages/Upcoming';
import { Live } from './pages/Live';
import { Completed } from './pages/Completed';
import { MatchesV2 as Matches } from './pages/MatchesV2';
import { MatchDetailV2 as MatchDetail } from './pages/MatchDetailV2';
import { Predictions } from './pages/Predictions';
import { EasyMatches } from './pages/EasyMatches';
import { Analytics } from './pages/Analytics';
import { Settings } from './pages/Settings';
import { ComponentsTest } from './pages/ComponentsTest';
import { Favorites } from './pages/Favorites';
import { PredictionCacheProvider } from './contexts/PredictionCacheContext';
import { FavoritesProvider } from './contexts/FavoritesContext';
import { AndroidBackHandler } from './native/AndroidBackHandler';
import './pages/pages.css';

function App() {
  return (
    <Router>
      <AndroidBackHandler />
      <FavoritesProvider>
        <PredictionCacheProvider>
          <AppLayout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/popular-leagues" element={<PopularLeagues />} />
              <Route path="/upcoming" element={<Upcoming />} />
              <Route path="/live" element={<Live />} />
              <Route path="/live/:matchId" element={<Live />} />
              <Route path="/completed" element={<Completed />} />
              <Route path="/matches" element={<Matches />} />
              <Route path="/matches/:id" element={<MatchDetail />} />
              <Route path="/predictions" element={<Predictions />} />
              <Route path="/easy-matches" element={<EasyMatches />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/favorites" element={<Favorites />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/components-test" element={<ComponentsTest />} />
            </Routes>
          </AppLayout>
        </PredictionCacheProvider>
      </FavoritesProvider>
    </Router>
  );
}

export default App;
