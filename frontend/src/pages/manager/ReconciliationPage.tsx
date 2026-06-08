import { PageHeader } from "../../components/ui/PageHeader";
import { ReconciliationWizard } from "../../components/reconciliation/ReconciliationWizard";
import { useAuth } from "../../store/auth";

export default function ManagerReconciliationPage() {
  const { user } = useAuth();
  return (
    <div className="space-y-6">
      <PageHeader
        title="Reconciliation"
        description="Reconcile completed shifts for your pump."
      />
      <ReconciliationWizard orgId={user?.org_id} />
    </div>
  );
}
