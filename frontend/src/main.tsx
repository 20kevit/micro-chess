import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { AppShell } from "./components/ui/AppShell";
import { AccountPage } from "./pages/AccountPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AuthProvider } from "./lib/auth-context";
import { RequireAuth } from "./lib/require-auth";
import { BalanceScalePage } from "./pages/BalanceScalePage";
import { BlindfoldCalculationPage } from "./pages/BlindfoldCalculationPage";
import { BlindfoldSquareVisionPage } from "./pages/BlindfoldSquareVisionPage";
import { CapturesPage } from "./pages/CapturesPage";
import { CastlingRightsPage } from "./pages/CastlingRightsPage";
import { CheckmatePage } from "./pages/CheckmatePage";
import { ChineseBoardPage } from "./pages/ChineseBoardPage";
import { ExercisesPage } from "./pages/ExercisesPage";
import { GetOutOfCheckPage } from "./pages/GetOutOfCheckPage";
import { GiveCheckPage } from "./pages/GiveCheckPage";
import { LegalDestinationsPage } from "./pages/LegalDestinationsPage";
import { MaterialComparisonPage } from "./pages/MaterialComparisonPage";
import { OpeningTrapsPage } from "./pages/OpeningTrapsPage";
import { ReverseOpeningPage } from "./pages/ReverseOpeningPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PathfindingPage } from "./pages/PathfindingPage";
import { PathfindingObstaclesPage } from "./pages/PathfindingObstaclesPage";
import { PieceRecognitionPage } from "./pages/PieceRecognitionPage";
import { PinPage } from "./pages/PinPage";
import { TrappedPiecesPage } from "./pages/TrappedPiecesPage";
import { UndefendedPiecesPage } from "./pages/UndefendedPiecesPage";
import "./index.css";

// Routes only. Keep data fetching inside pages via api client.
// "/" is the main exercise-selection menu; "/exercises" is an alias.
const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <ExercisesPage /> },
      { path: "/exercises", element: <ExercisesPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      {
        path: "/account",
        element: (
          <RequireAuth>
            <AccountPage />
          </RequireAuth>
        ),
      },
      { path: "/exercises/piece-recognition", element: <PieceRecognitionPage /> },
      { path: "/exercises/legal-destinations", element: <LegalDestinationsPage /> },
      { path: "/exercises/captures", element: <CapturesPage /> },
      { path: "/exercises/undefended-pieces", element: <UndefendedPiecesPage /> },
      { path: "/exercises/balance-scale", element: <BalanceScalePage /> },
      { path: "/exercises/is-checkmate", element: <CheckmatePage /> },
      { path: "/exercises/give-check", element: <GiveCheckPage /> },
      { path: "/exercises/get-out-of-check", element: <GetOutOfCheckPage /> },
      { path: "/exercises/heavier-side", element: <MaterialComparisonPage /> },
      { path: "/exercises/chinese-board", element: <ChineseBoardPage /> },
      { path: "/exercises/opening-traps", element: <OpeningTrapsPage /> },
      { path: "/exercises/reverse-opening", element: <ReverseOpeningPage /> },
      { path: "/exercises/blindfold-square-vision", element: <BlindfoldSquareVisionPage /> },
      { path: "/exercises/blindfold-calculation", element: <BlindfoldCalculationPage /> },
      { path: "/exercises/pathfinding", element: <PathfindingPage /> },
      { path: "/exercises/pathfinding-obstacles", element: <PathfindingObstaclesPage /> },
      { path: "/exercises/pin", element: <PinPage /> },
      { path: "/exercises/trapped-pieces", element: <TrappedPiecesPage /> },
      { path: "/exercises/castling-rights", element: <CastlingRightsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </StrictMode>,
);

// Re-export default for tooling that expects App entry.
export default App;
