import { useState } from "react";
import { AdminConfig } from "../components/AdminConfig";
import { ApplicationStatCards } from "../components/ApplicationStatCards";
import { Diagnostics } from "../components/Diagnostics";
import { EventLogViewer } from "../components/EventLogViewer";
import { LoginForm } from "../components/LoginForm";
import { OnboardingDelta } from "../components/OnboardingDelta";
import { OrganizerActivityChart } from "../components/OrganizerActivityChart";
import { OrganizerProfile } from "../components/OrganizerProfile";
import { RecentlyOnboarded } from "../components/RecentlyOnboarded";
import { ResubmissionLog } from "../components/ResubmissionLog";
import { ResubmitNowButton } from "../components/ResubmitNowButton";
import { ScannerStatusCard } from "../components/ScannerStatusCard";
import { StatusTimeline } from "../components/StatusTimeline";
import { TabNavigation, type Tab } from "../components/TabNavigation";
import { TaskTriggers } from "../components/TaskTriggers";
import { WaitTimeEstimator } from "../components/WaitTimeEstimator";
import { useAuthSession, useLogout } from "../lib/useAuthSession";

const TABS: Tab[] = [
  { id: "application", label: "My Application" },
  { id: "organizers", label: "Organizers" },
  { id: "admin", label: "Admin" },
];

export function Dashboard() {
  const [activeTab, setActiveTab] = useState(TABS[0].id);
  const authQuery = useAuthSession();
  const logout = useLogout();

  // Three-way session-gate state: `isPending` covers the initial round trip (neutral loading
  // UI, no gated content, no login form); `isError` fails closed to the login form rather than
  // inheriting whatever `data` last held, so a broken/erroring session check never leaves gated
  // content exposed indefinitely. Only a resolved, successful check with `authenticated: true`
  // unlocks the real content.
  const sessionGateState: "loading" | "authenticated" | "unauthenticated" = authQuery.isPending
    ? "loading"
    : authQuery.isError || authQuery.data?.authenticated !== true
      ? "unauthenticated"
      : "authenticated";

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <h1 className="text-3xl font-bold text-primary">Limitless Organizer Tracker</h1>
      <div className="flex items-center justify-between">
        <TabNavigation tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
        {sessionGateState === "authenticated" && (
          <button type="button" onClick={() => logout()} className="btn btn-ghost btn-sm">
            Log out
          </button>
        )}
      </div>

      {activeTab === "application" && (
        <div className="space-y-6">
          {sessionGateState === "loading" ? (
            <p className="text-sm text-base-content/60">Checking session…</p>
          ) : sessionGateState === "authenticated" ? (
            <>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">Application Overview</h2>
                <ApplicationStatCards />
              </section>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">Status History</h2>
                <StatusTimeline />
              </section>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">Resubmit Application</h2>
                <ResubmitNowButton />
              </section>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">Resubmission Log</h2>
                <ResubmissionLog />
              </section>
            </>
          ) : (
            <LoginForm onSuccess={() => authQuery.refetch()} />
          )}
        </div>
      )}

      {activeTab === "organizers" && (
        <div className="space-y-6">
          <section className="card bg-base-200 p-4">
            <h2 className="mb-1 text-lg font-semibold">Organizer Activity</h2>
            <p className="mb-3 text-sm text-base-content/60">
              Organizers running their first tournament per week
            </p>
            <OrganizerActivityChart />
          </section>
          <section className="card bg-base-200 p-4">
            <h2 className="mb-3 text-lg font-semibold">Onboarding to First Tournament</h2>
            <OnboardingDelta />
          </section>
          <section className="card bg-base-200 p-4">
            <h2 className="mb-3 text-lg font-semibold">Recently Onboarded</h2>
            <RecentlyOnboarded />
          </section>
          <section className="card bg-base-200 p-4">
            <h2 className="mb-3 text-lg font-semibold">Wait Time Estimator</h2>
            <WaitTimeEstimator />
          </section>
          <section className="card bg-base-200 p-4">
            <h2 className="mb-3 text-lg font-semibold">Scanner Status</h2>
            <ScannerStatusCard />
          </section>
          <section className="card bg-base-200 p-4">
            <h2 className="mb-3 text-lg font-semibold">Organizer Profile</h2>
            <OrganizerProfile />
          </section>
        </div>
      )}

      {activeTab === "admin" && (
        <div className="space-y-6">
          {sessionGateState === "loading" ? (
            <p className="text-sm text-base-content/60">Checking session…</p>
          ) : sessionGateState === "authenticated" ? (
            <>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">System Diagnostics</h2>
                <Diagnostics />
              </section>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">Task Triggers</h2>
                <TaskTriggers />
              </section>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">Configuration</h2>
                <AdminConfig />
              </section>
              <section className="card bg-base-200 p-4">
                <h2 className="mb-3 text-lg font-semibold">Event Log</h2>
                <EventLogViewer />
              </section>
            </>
          ) : (
            <LoginForm onSuccess={() => authQuery.refetch()} />
          )}
        </div>
      )}
    </main>
  );
}
