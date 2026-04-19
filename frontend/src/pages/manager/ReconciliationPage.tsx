import { PageHeader } from "../../components/ui/PageHeader";
import { ReconciliationWizard } from "../../components/reconciliation/ReconciliationWizard";

export default function ManagerReconciliationPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Reconciliation"
        description="Reconcile completed shifts for your pump."
      />
      <ReconciliationWizard />
    </div>
  );
}
