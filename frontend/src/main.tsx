import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { AppShell } from "./components/ui/AppShell";
import { BalanceScalePage } from "./pages/BalanceScalePage";
import { CapturesPage } from "./pages/CapturesPage";
import { CastlingRightsPage } from "./pages/CastlingRightsPage";
import { CheckmatePage } from "./pages/CheckmatePage";
import { EqualAttackersDefendersPage } from "./pages/EqualAttackersDefendersPage";
import { ExercisesPage } from "./pages/ExercisesPage";
import { GetOutOfCheckPage } from "./pages/GetOutOfCheckPage";
import { GiveCheckPage } from "./pages/GiveCheckPage";
import { HangingPiecesPage } from "./pages/HangingPiecesPage";
import { LegalDestinationsPage } from "./pages/LegalDestinationsPage";
import { MaterialComparisonPage } from "./pages/MaterialComparisonPage";
import { MemoryBoardPage } from "./pages/MemoryBoardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PathfindingPage } from "./pages/PathfindingPage";
import { PieceRecognitionPage } from "./pages/PieceRecognitionPage";
import { PinPage } from "./pages/PinPage";
import "./index.css";

// Routes only. Keep data fetching inside pages via api client.
// "/" is the main exercise-selection menu; "/exercises" is an alias.
const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <ExercisesPage /> },
      { path: "/exercises", element: <ExercisesPage /> },
      { path: "/exercises/piece-recognition", element: <PieceRecognitionPage /> },
      { path: "/exercises/legal-destinations", element: <LegalDestinationsPage /> },
      { path: "/exercises/captures", element: <CapturesPage /> },
      { path: "/exercises/balance-scale", element: <BalanceScalePage /> },
      { path: "/exercises/hanging-pieces", element: <HangingPiecesPage /> },
      { path: "/exercises/equal-attackers-defenders", element: <EqualAttackersDefendersPage /> },
      { path: "/exercises/castling-rights", element: <CastlingRightsPage /> },
      { path: "/exercises/is-checkmate", element: <CheckmatePage /> },
      { path: "/exercises/give-check", element: <GiveCheckPage /> },
      { path: "/exercises/get-out-of-check", element: <GetOutOfCheckPage /> },
      { path: "/exercises/heavier-side", element: <MaterialComparisonPage /> },
      { path: "/exercises/memory-board", element: <MemoryBoardPage /> },
      { path: "/exercises/pathfinding", element: <PathfindingPage /> },
      { path: "/exercises/pin", element: <PinPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);

// Re-export default for tooling that expects App entry.
export default App;
