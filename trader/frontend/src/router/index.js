import { Routes, Route } from 'react-router-dom';
import { NextActions } from '../views/NextActions';
import { Diversification } from '../views/Diversification';
import { SecurityUniverse } from '../views/SecurityUniverse';
import { RecentTrades } from '../views/RecentTrades';
import { Logs } from '../views/Logs';
import { Layout } from '../components/layout/Layout';

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<NextActions />} />
        <Route path="diversification" element={<Diversification />} />
        <Route path="security-universe" element={<SecurityUniverse />} />
        <Route path="recent-trades" element={<RecentTrades />} />
        <Route path="logs" element={<Logs />} />
      </Route>
    </Routes>
  );
}
