import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { AppShell } from "./components/ui/AppShell";
import { BalanceScalePage } from "./pages/BalanceScalePage";
import { BlindfoldCalculationPage } from "./pages/BlindfoldCalculationPage";
import { BlindfoldSquareVisionPage } from "./pages/BlindfoldSquareVisionPage";
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
import { OpeningMoveReconstructionPage } from "./pages/OpeningMoveReconstructionPage";
import { OpeningTrapsPage } from "./pages/OpeningTrapsPage";
import { RuleOfTheSquarePage } from "./pages/RuleOfTheSquarePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PathfindingPage } from "./pages/PathfindingPage";
import { PieceRecognitionPage } from "./pages/PieceRecognitionPage";
import { PinPage } from "./pages/PinPage";
import { TrappedPiecesPage } from "./pages/TrappedPiecesPage";
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
      { path: "/exercises/opening-traps", element: <OpeningTrapsPage /> },
      { path: "/exercises/opening-move-reconstruction", element: <OpeningMoveReconstructionPage /> },
      { path: "/exercises/rule-of-the-square", element: <RuleOfTheSquarePage /> },
      { path: "/exercises/blindfold-square-vision", element: <BlindfoldSquareVisionPage /> },
      { path: "/exercises/blindfold-calculation", element: <BlindfoldCalculationPage /> },
      { path: "/exercises/pathfinding", element: <PathfindingPage /> },
      { path: "/exercises/pin", element: <PinPage /> },
      { path: "/exercises/trapped-pieces", element: <TrappedPiecesPage /> },
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
