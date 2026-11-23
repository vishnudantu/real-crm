import { lazy, Suspense, useEffect, useRef } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TenantProvider, useTenant } from "./tenant/TenantProvider";
import { FeaturesProvider } from "./features/FeaturesProvider";
import { Benefits } from "./components/Benefits";
import { PublicLanding } from "./components/PublicLanding";
import { Challenges } from "./components/Challenges";
import { DemoCTA } from "./components/DemoCTA";
import { Footer } from "./components/Footer";
import { Hero } from "./components/Hero";
import { Navigation } from "./components/Navigation";
import { ProductShowcase } from "./components/ProductShowcase";
import { Workflow } from "./components/Workflow";
import { DpdPPage } from "./pages/DpdPPage";
import { LoginPage } from "./pages/LoginPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AdminAuthGuard } from "./admin/AdminAuthGuard";
import { AdminLayout } from "./admin/AdminLayout";
import { AdminOverviewPage } from "./admin/AdminOverviewPage";
import { UserManagementPage } from "./admin/UserManagementPage";
import { ProjectManagementPage } from "./admin/ProjectManagementPage";
import { VisitManagementPage } from "./admin/VisitManagementPage";
import { AnalyticsDashboardPage } from "./admin/AnalyticsDashboardPage";
import { SystemSettingsPage } from "./admin/SystemSettingsPage";
import { MyAccountPage } from "./admin/MyAccountPage";
import { CustomerDirectoryPage } from "./customers/CustomerDirectoryPage";
import { Customer360Page } from "./customers/Customer360Page";
import { CustomerDuplicatesPage } from "./customers/CustomerDuplicatesPage";
import { OpportunityPipelinePage } from "./customers/OpportunityPipelinePage";
import { InventoryMapPage } from "./inventory/InventoryMapPage";
import { SunFacingPage } from "./solar/SunFacingPage";
import { InventoryUnitsPage } from "./inventory/InventoryUnitsPage";
import { DocumentsPage } from "./documents/DocumentsPage";
import { TeamChatPage } from "./teamchat/TeamChatPage";

const SaleBookingsPage = lazy(() =>
  import("./admin/sales/SaleBookingsPage").then((module) => ({
    default: module.SaleBookingsPage,
  })),
);
const OmnichannelInboxPage = lazy(() =>
  import("./omnichannel/OmnichannelInboxPage").then((module) => ({
    default: module.OmnichannelInboxPage,
  })),
);
const ChannelsSettingsPage = lazy(() =>
  import("./omnichannel/ChannelsSettingsPage").then((module) => ({
    default: module.ChannelsSettingsPage,
  })),
);
const AdConnectionsPage = lazy(() =>
  import("./integrations/AdConnectionsPage").then((module) => ({
    default: module.AdConnectionsPage,
  })),
);
const MetaPageSelectStep = lazy(() =>
  import("./integrations/MetaPageSelectStep").then((module) => ({
    default: module.MetaPageSelectStep,
  })),
);
const GoogleAdsSelectStep = lazy(() =>
  import("./integrations/GoogleAdsSelectStep").then((module) => ({
    default: module.GoogleAdsSelectStep,
  })),
);
const FeatureNotEnabledPage = lazy(() =>
  import("./omnichannel/FeatureNotEnabledPage").then((module) => ({
    default: module.FeatureNotEnabledPage,
  })),
);
const ApprovalsPage = lazy(() =>
  import("./approvals/ApprovalsPage").then((module) => ({
    default: module.ApprovalsPage,
  })),
);
const ServiceDeskPage = lazy(() =>
  import("./servicedesk/ServiceDeskPage").then((module) => ({
    default: module.ServiceDeskPage,
  })),
);
const KnowledgeBasePage = lazy(() =>
  import("./servicedesk/KnowledgeBasePage").then((module) => ({
    default: module.KnowledgeBasePage,
  })),
);
const HelpCenterPage = lazy(() =>
  import("./buyer/help/HelpCenterPage").then((module) => ({
    default: module.HelpCenterPage,
  })),
);
const ReconciliationPage = lazy(() =>
  import("./reconciliation/ReconciliationPage").then((module) => ({
    default: module.ReconciliationPage,
  })),
);
const ConstructionPage = lazy(() =>
  import("./construction/ConstructionPage").then((module) => ({
    default: module.ConstructionPage,
  })),
);
const BrokersPage = lazy(() =>
  import("./brokers/BrokersPage").then((module) => ({
    default: module.BrokersPage,
  })),
);
const VoiceIntelPage = lazy(() =>
  import("./voiceintel/VoiceIntelPage").then((module) => ({
    default: module.VoiceIntelPage,
  })),
);
const TenantAIPage = lazy(() =>
  import("./tenantai/TenantAIPage").then((module) => ({
    default: module.TenantAIPage,
  })),
);
import { BuyerAuthGuard } from "./buyer/BuyerAuthGuard";
import { BuyerLayout } from "./buyer/BuyerLayout";
import { BuyerDashboardPage } from "./buyer/BuyerDashboardPage";
import { ConversationsPage } from "./buyer/ConversationsPage";
import { SiteVisitsPage } from "./buyer/SiteVisitsPage";
import { ProjectInfoPage } from "./buyer/ProjectInfoPage";
import { ProfilePage } from "./buyer/ProfilePage";
import { BuyerDocumentsPage } from "./buyer/documents/BuyerDocumentsPage";
import { SalesAuthGuard } from "./sales/SalesAuthGuard";
import { SalesLayout } from "./sales/SalesLayout";
import { SalesDashboardPage } from "./sales/SalesDashboardPage";
import { SalesLeadsPage } from "./sales/SalesLeadsPage";
import { SalesNotificationsPage } from "./sales/SalesNotificationsPage";
import { SalesProfilePage } from "./sales/SalesProfilePage";
import { SalesConversationsPage } from "./sales/SalesConversationsPage";
import { SalesVisitsPage } from "./sales/SalesVisitsPage";
import { SalesFollowUpsPage } from "./sales/SalesFollowUpsPage";
import { LoaderCircle } from "lucide-react";

const OperatorLoginPage = lazy(() =>
  import("./operator/OperatorLoginPage").then((module) => ({
    default: module.OperatorLoginPage,
  })),
);
const OperatorAuthGuard = lazy(() =>
  import("./operator/OperatorAuthGuard").then((module) => ({
    default: module.OperatorAuthGuard,
  })),
);
const OperatorLayout = lazy(() =>
  import("./operator/OperatorLayout").then((module) => ({
    default: module.OperatorLayout,
  })),
);
const OperatorTenantsPage = lazy(() =>
  import("./operator/OperatorTenantsPage").then((module) => ({
    default: module.OperatorTenantsPage,
  })),
);
const OperatorMissionControlPage = lazy(() =>
  import("./operator/OperatorMissionControlPage").then((module) => ({
    default: module.OperatorMissionControlPage,
  })),
);
const OperatorIncidentsPage = lazy(() =>
  import("./operator/OperatorIncidentsPage").then((module) => ({
    default: module.OperatorIncidentsPage,
  })),
);
const OperatorProvisionPage = lazy(() =>
  import("./operator/OperatorProvisionPage").then((module) => ({
    default: module.OperatorProvisionPage,
  })),
);
const OperatorTenantDetailPage = lazy(() =>
  import("./operator/OperatorTenantDetailPage").then((module) => ({
    default: module.OperatorTenantDetailPage,
  })),
);
const OperatorPlansPage = lazy(() =>
  import("./operator/OperatorPlansPage").then((module) => ({
    default: module.OperatorPlansPage,
  })),
);
const OperatorUsersPage = lazy(() =>
  import("./operator/OperatorUsersPage").then((module) => ({
    default: module.OperatorUsersPage,
  })),
);
const OperatorAuditLogsPage = lazy(() =>
  import("./operator/OperatorAuditLogsPage").then((module) => ({
    default: module.OperatorAuditLogsPage,
  })),
);
const OperatorRouteGuard = lazy(() =>
  import("./operator/OperatorRouteGuard").then((module) => ({
    default: module.OperatorRouteGuard,
  })),
);
const OperatorNoAccessPage = lazy(() =>
  import("./operator/OperatorRouteGuard").then((module) => ({
    default: module.OperatorNoAccessPage,
  })),
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30,
      retry: 1,
    },
  },
});

function ScrollToTopOnRouteChange() {
  const { pathname } = useLocation();
  const previousPathname = useRef(pathname);

  useEffect(() => {
    if (previousPathname.current === pathname) return;

    window.scrollTo(0, 0);
    previousPathname.current = pathname;
  }, [pathname]);

  return null;
}

function RouteLoadingFallback() {
  return (
    <div
      role="status"
      className="flex min-h-svh items-center justify-center gap-2 bg-ivory text-sm text-charcoal/65"
    >
      <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
      Loading operator console…
    </div>
  );
}

function HomePage() {
  const { isUsingDefaults } = useTenant();
  if (!isUsingDefaults) return <PublicLanding />;

  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-charcoal focus:px-5 focus:py-3 focus:text-sm focus:font-semibold focus:text-ivory"
      >
        Skip to content
      </a>
      <Navigation />
      <main id="main">
        <Hero />
        <Challenges />
        <ProductShowcase />
        <Workflow />
        <Benefits />
        <DemoCTA />
      </main>
      <Footer />
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TenantProvider>
        <FeaturesProvider>
        <ScrollToTopOnRouteChange />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/privacy" element={<DpdPPage />} />
          <Route
            path="/operator/login"
            element={
              <Suspense fallback={<RouteLoadingFallback />}>
                <OperatorLoginPage />
              </Suspense>
            }
          />
          <Route
            path="/operator"
            element={
              <Suspense fallback={<RouteLoadingFallback />}>
                <OperatorAuthGuard />
              </Suspense>
            }
          >
            <Route
              element={
                <Suspense fallback={<RouteLoadingFallback />}>
                  <OperatorLayout />
                </Suspense>
              }
            >
              <Route
                index
                element={
                  <OperatorRouteGuard>
                    <OperatorMissionControlPage />
                  </OperatorRouteGuard>
                }
              />
              <Route
                path="tenants"
                element={
                  <OperatorRouteGuard permission="tenants.read">
                    <OperatorTenantsPage />
                  </OperatorRouteGuard>
                }
              />
              <Route
                path="incidents"
                element={
                  <OperatorRouteGuard permission="tenants.read">
                    <OperatorIncidentsPage />
                  </OperatorRouteGuard>
                }
              />
              <Route
                path="tenants/new"
                element={
                  <OperatorRouteGuard permission="tenants.write">
                    <OperatorProvisionPage />
                  </OperatorRouteGuard>
                }
              />
              <Route
                path="tenants/:tenantId"
                element={
                  <OperatorRouteGuard permission="tenants.read">
                    <OperatorTenantDetailPage />
                  </OperatorRouteGuard>
                }
              />
              <Route
                path="plans"
                element={
                  <OperatorRouteGuard permission="tenants.read">
                    <OperatorPlansPage />
                  </OperatorRouteGuard>
                }
              />
              <Route
                path="operators"
                element={
                  <OperatorRouteGuard permission="operators.manage">
                    <OperatorUsersPage />
                  </OperatorRouteGuard>
                }
              />
              <Route
                path="audit-logs"
                element={
                  <OperatorRouteGuard permission="audit.read">
                    <OperatorAuditLogsPage />
                  </OperatorRouteGuard>
                }
              />
              <Route path="access" element={<OperatorNoAccessPage />} />
              <Route path="*" element={<Navigate to="/operator" replace />} />
            </Route>
          </Route>
          <Route path="/admin" element={<AdminAuthGuard />}>
            <Route element={<AdminLayout />}>
              <Route index element={<AdminOverviewPage />} />
              <Route path="overview" element={<AdminOverviewPage />} />
              <Route path="users" element={<UserManagementPage />} />
              <Route path="teamchat" element={<TeamChatPage />} />
              <Route path="projects" element={<ProjectManagementPage />} />
              <Route path="customers" element={<CustomerDirectoryPage />} />
              <Route path="customers/:id" element={<Customer360Page />} />
              <Route path="customers/:id/duplicates" element={<CustomerDuplicatesPage />} />
              <Route path="opportunities" element={<OpportunityPipelinePage />} />
              <Route path="inventory" element={<InventoryMapPage />} />
              <Route path="inventory/units" element={<InventoryUnitsPage />} />
              <Route path="inventory/sun-facing" element={<SunFacingPage />} />
              <Route path="visits" element={<VisitManagementPage />} />
              <Route path="analytics" element={<AnalyticsDashboardPage />} />
              <Route
                path="inbox"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <OmnichannelInboxPage />
                  </Suspense>
                }
              />
              <Route
                path="channels"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <ChannelsSettingsPage />
                  </Suspense>
                }
              />
              <Route
                path="integrations"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <AdConnectionsPage />
                  </Suspense>
                }
              />
              <Route
                path="integrations/meta/select"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <MetaPageSelectStep />
                  </Suspense>
                }
              />
              <Route
                path="integrations/google/select"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <GoogleAdsSelectStep />
                  </Suspense>
                }
              />
              <Route
                path="feature-disabled"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <FeatureNotEnabledPage />
                  </Suspense>
                }
              />
              <Route
                path="sales-bookings"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <SaleBookingsPage />
                  </Suspense>
                }
              />
              <Route path="documents" element={<DocumentsPage />} />
              <Route
                path="approvals"
                element={<Suspense fallback={<RouteLoadingFallback />}><ApprovalsPage /></Suspense>}
              />
              <Route
                path="service-desk"
                element={<Suspense fallback={<RouteLoadingFallback />}><ServiceDeskPage /></Suspense>}
              />
              <Route
                path="service-desk/knowledge"
                element={<Suspense fallback={<RouteLoadingFallback />}><KnowledgeBasePage /></Suspense>}
              />
              <Route
                path="reconciliation"
                element={<Suspense fallback={<RouteLoadingFallback />}><ReconciliationPage /></Suspense>}
              />
              <Route
                path="construction"
                element={<Suspense fallback={<RouteLoadingFallback />}><ConstructionPage /></Suspense>}
              />
              <Route
                path="brokers"
                element={<Suspense fallback={<RouteLoadingFallback />}><BrokersPage /></Suspense>}
              />
              <Route
                path="call-intelligence"
                element={<Suspense fallback={<RouteLoadingFallback />}><VoiceIntelPage /></Suspense>}
              />
              <Route
                path="settings/ai-providers"
                element={<Suspense fallback={<RouteLoadingFallback />}><TenantAIPage /></Suspense>}
              />
              <Route path="settings" element={<SystemSettingsPage />} />
              <Route path="settings/:section" element={<SystemSettingsPage />} />
              <Route path="notifications" element={<SystemSettingsPage initialTab="notifications" />} />
              <Route path="account" element={<MyAccountPage />} />
              <Route
                path="audit-logs"
                element={<SystemSettingsPage initialTab="audit_logs" />}
              />
              <Route path="*" element={<Navigate to="/admin" replace />} />
            </Route>
          </Route>
          <Route path="/sales" element={<SalesAuthGuard />}>
            <Route element={<SalesLayout />}>
              <Route index element={<SalesDashboardPage />} />
              <Route path="overview" element={<SalesDashboardPage />} />
              <Route path="leads" element={<SalesLeadsPage />} />
              <Route
                path="conversations"
                element={<SalesConversationsPage />}
              />
              <Route path="teamchat" element={<TeamChatPage />} />
              <Route path="visits" element={<SalesVisitsPage />} />
              <Route path="follow-ups" element={<SalesFollowUpsPage />} />
              <Route
                path="notifications"
                element={<SalesNotificationsPage />}
              />
              <Route path="profile" element={<SalesProfilePage />} />
              <Route path="*" element={<Navigate to="/sales" replace />} />
            </Route>
          </Route>
          <Route path="/buyer" element={<BuyerAuthGuard />}>
            <Route element={<BuyerLayout />}>
              <Route index element={<BuyerDashboardPage />} />
              <Route path="overview" element={<BuyerDashboardPage />} />
              <Route path="conversations" element={<ConversationsPage />} />
              <Route path="visits" element={<SiteVisitsPage />} />
              <Route path="project" element={<ProjectInfoPage />} />
              <Route path="documents" element={<BuyerDocumentsPage />} />
              <Route path="help" element={<Suspense fallback={<RouteLoadingFallback />}><HelpCenterPage /></Suspense>} />
              <Route path="profile" element={<ProfilePage />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        </FeaturesProvider>
        </TenantProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
