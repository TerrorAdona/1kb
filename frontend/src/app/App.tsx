import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../shared/components/AppShell";
import { AuthGate } from "../shared/components/AuthGate";
import { HomePage } from "../features/home/HomePage";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { RecoveryPage } from "../features/auth/RecoveryPage";
import { LobbyPage } from "../features/lobby/LobbyPage";
import { RoomPage } from "../features/lobby/RoomPage";
import { SoloSetupPage } from "../features/solo/SoloSetupPage";
import { GamePage } from "../features/game/GamePage";
import { ResultPage } from "../features/results/ResultPage";
import { LeaderboardPage } from "../features/profile/LeaderboardPage";
import { ProfilePage } from "../features/profile/ProfilePage";
import { useAuthStore } from "../features/auth/authStore";
import { NotFoundPage } from "../shared/components/NotFoundPage";

export function App() {
  const initialize = useAuthStore((state) => state.initialize);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="recover" element={<RecoveryPage />} />
          <Route
            path="lobby"
            element={
              <AuthGate>
                <LobbyPage />
              </AuthGate>
            }
          />
          <Route
            path="lobby/:gameId"
            element={
              <AuthGate>
                <RoomPage />
              </AuthGate>
            }
          />
          <Route
            path="solo"
            element={
              <AuthGate>
                <SoloSetupPage />
              </AuthGate>
            }
          />
          <Route
            path="game/:gameId"
            element={
              <AuthGate>
                <GamePage />
              </AuthGate>
            }
          />
          <Route
            path="result/:gameId"
            element={
              <AuthGate>
                <ResultPage />
              </AuthGate>
            }
          />
          <Route
            path="profile"
            element={
              <AuthGate>
                <ProfilePage />
              </AuthGate>
            }
          />
          <Route
            path="leaderboard"
            element={
              <AuthGate>
                <LeaderboardPage />
              </AuthGate>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
          <Route path="home" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
