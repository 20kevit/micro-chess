import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { AppShell } from "./components/ui/AppShell";
import { CapturesPage } from "./pages/CapturesPage";
import { ExercisesPage } from "./pages/ExercisesPage";
import { HangingPiecesPage } from "./pages/HangingPiecesPage";
import { LegalDestinationsPage } from "./pages/LegalDestinationsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PieceRecognitionPage } from "./pages/PieceRecognitionPage";
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
      { path: "/exercises/hanging-pieces", element: <HangingPiecesPage /> },
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
