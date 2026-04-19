import { PageHeader } from "../../components/ui/PageHeader";
import { ReconciliationWizard } from "../../components/reconciliation/ReconciliationWizard";
import { useOrgStore } from "../../store/org";

export default function ReconciliationPage() {
  const { selectedOrgId } = useOrgStore();
  return (
    <div className="space-y-6">
      <PageHeader
        title="Reconciliation"
        description="Close the books on completed shifts: compare POS + UPI + cash against meter totals."
      />
      <ReconciliationWizard orgId={selectedOrgId} />
    </div>
  );
}
