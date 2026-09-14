import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { AppShell } from "./components/ui/AppShell";
import { AccountPage } from "./pages/AccountPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AuthProvider } from "./lib/auth-context";
import { RequireAuth } from "./lib/require-auth";
import { RequireRole } from "./lib/require-role";
import { RequireAdmin } from "./lib/require-admin";
import { AdminAnalyticsPage } from "./pages/AdminAnalyticsPage";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { AdminExercisesPage } from "./pages/AdminExercisesPage";
import { AdminGeneratorsPage } from "./pages/AdminGeneratorsPage";
import { AdminPuzzlesPage } from "./pages/AdminPuzzlesPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
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
import { CoachStudentsPage, ParentChildrenPage } from "./pages/MentorStudentsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RelationshipsPage } from "./pages/RelationshipsPage";
import { PathfindingPage } from "./pages/PathfindingPage";
import { PathfindingObstaclesPage } from "./pages/PathfindingObstaclesPage";
import { PieceRecognitionPage } from "./pages/PieceRecognitionPage";
import { PinPage } from "./pages/PinPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ProgressPage } from "./pages/ProgressPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { SupportDetailPage } from "./pages/SupportDetailPage";
import { SupportPage } from "./pages/SupportPage";
import { AdminSupportPage } from "./pages/AdminSupportPage";
import { TrappedPiecesPage } from "./pages/TrappedPiecesPage";
import { UndefendedPiecesPage } from "./pages/UndefendedPiecesPage";
import "./index.css";

// Routes only. Keep data fetching inside pages via api client.
// "/" is the player home (dashboard when logged in, exercise menu when
// anonymous); "/exercises" is the exercise menu alias.
const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <HomePage /> },
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
      {
        path: "/progress",
        element: (
          <RequireRole allowed={["PLAYER", "COACH", "PARENT"]}>
            <ProgressPage />
          </RequireRole>
        ),
      },
      {
        path: "/profile",
        element: (
          <RequireRole allowed={["PLAYER", "COACH", "PARENT"]}>
            <ProfilePage />
          </RequireRole>
        ),
      },
      {
        path: "/relationships",
        element: (
          <RequireRole allowed={["PLAYER", "COACH", "PARENT"]}>
            <RelationshipsPage />
          </RequireRole>
        ),
      },
      {
        path: "/support",
        element: (
          <RequireAuth>
            <SupportPage />
          </RequireAuth>
        ),
      },
      {
        path: "/support/:id",
        element: (
          <RequireAuth>
            <SupportDetailPage />
          </RequireAuth>
        ),
      },
      {
        path: "/notifications",
        element: (
          <RequireAuth>
            <NotificationsPage />
          </RequireAuth>
        ),
      },
      {
        path: "/coach/students",
        element: (
          <RequireRole allowed={["COACH"]}>
            <CoachStudentsPage />
          </RequireRole>
        ),
      },
      {
        path: "/parent/children",
        element: (
          <RequireRole allowed={["PARENT"]}>
            <ParentChildrenPage />
          </RequireRole>
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
      {
        path: "/admin",
        element: (
          <RequireAdmin>
            <AdminDashboardPage />
          </RequireAdmin>
        ),
      },
      {
        path: "/admin/analytics",
        element: (
          <RequireAdmin>
            <AdminAnalyticsPage />
          </RequireAdmin>
        ),
      },
      {
        path: "/admin/users",
        element: (
          <RequireAdmin>
            <AdminUsersPage />
          </RequireAdmin>
        ),
      },
      {
        path: "/admin/exercises",
        element: (
          <RequireAdmin>
            <AdminExercisesPage />
          </RequireAdmin>
        ),
      },
      {
        path: "/admin/puzzles",
        element: (
          <RequireAdmin>
            <AdminPuzzlesPage />
          </RequireAdmin>
        ),
      },
      {
        path: "/admin/generators",
        element: (
          <RequireAdmin>
            <AdminGeneratorsPage />
          </RequireAdmin>
        ),
      },
      {
        path: "/admin/support",
        element: (
          <RequireAdmin>
            <AdminSupportPage />
          </RequireAdmin>
        ),
      },
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
