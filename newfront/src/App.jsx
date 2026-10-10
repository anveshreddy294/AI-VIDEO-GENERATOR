import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Public Pages
import LandingPage from './pages/public/LandingPage';
import ProductDemoPage from './pages/public/ProductDemoPage';
import PlatformPage from './pages/public/PlatformPage';
import HowItWorksPage from './pages/public/HowItWorksPage';
import ArchitecturePage from './pages/public/ArchitecturePage';
import AboutPage from './pages/public/AboutPage';
import HelpPage from './pages/public/HelpPage';
import TermsPage from './pages/public/TermsPage';
import PrivacyPage from './pages/public/PrivacyPage';
import SignInPage from './pages/public/SignInPage';

// Authenticated Shell & App Pages
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/app/DashboardPage';
import LibraryPage from './pages/app/LibraryPage';
import TopicExplorerPage from './pages/app/TopicExplorerPage';
import LearningStudioPage from './pages/app/LearningStudioPage';
import AssessmentPage from './pages/app/AssessmentPage';
import ProgressPage from './pages/app/ProgressPage';
import VideoStudioPage from './pages/app/VideoStudioPage';
import ProfilePage from './pages/app/ProfilePage';

// Educator Hub Page
import EducatorHubPage from './pages/educator/EducatorHubPage';

export default function App() {
  return (
    <Routes>
      {/* 1. PUBLIC MARKETING & DEMO ROUTES */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/demo" element={<ProductDemoPage />} />
      <Route path="/platform" element={<PlatformPage />} />
      <Route path="/how-it-works" element={<HowItWorksPage />} />
      <Route path="/architecture" element={<ArchitecturePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/signin" element={<SignInPage />} />

      {/* 2. AUTHENTICATED WORKSPACE SHELL */}
      <Route path="/app" element={<AppLayout />}>
        <Route index element={<Navigate to="/app/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="explore" element={<TopicExplorerPage />} />
        <Route path="studio" element={<LearningStudioPage />} />
        <Route path="assessment" element={<AssessmentPage />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="video" element={<VideoStudioPage />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      {/* 3. INSTRUCTOR / EDUCATOR HUB (WITHIN SHELL) */}
      <Route path="/educator" element={<AppLayout />}>
        <Route index element={<EducatorHubPage />} />
      </Route>

      {/* CATCH-ALL ROUTE */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
