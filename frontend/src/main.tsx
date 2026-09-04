import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { AppShell } from "./components/ui/AppShell";
import { ExercisesPage } from "./pages/ExercisesPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PieceRecognitionPage } from "./pages/PieceRecognitionPage";
import "./index.css";

// Routes only. Keep data fetching inside pages via api client.
const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/exercises", element: <ExercisesPage /> },
      { path: "/exercises/piece-recognition", element: <PieceRecognitionPage /> },
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
