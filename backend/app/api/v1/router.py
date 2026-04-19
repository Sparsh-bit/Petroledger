"""PetroLedger — API v1 Router."""

from fastapi import APIRouter

from app.api.v1.health.routes import router as health_router
from app.api.v1.anomaly_flags.routes import router as anomaly_flags_router
from app.api.v1.analytics.routes import router as analytics_router
from app.api.v1.audit_logs.routes import router as audit_logs_router
from app.api.v1.daily_consolidation.routes import router as daily_consolidation_router
from app.api.v1.inventory.routes import router as inventory_router
from app.api.v1.maintenance.routes import router as maintenance_router
from app.api.v1.upi_transactions.routes import router as upi_transactions_router
from app.api.v1.superadmin.routes import router as superadmin_router
from app.api.v1.provider.routes import router as provider_router
from app.api.v1.meter_readings.routes import router as meter_readings_router
from app.api.v1.auth.routes import router as auth_router
from app.api.v1.cash_entries.routes import router as cash_entries_router
from app.api.v1.contact.routes import router as contact_router
from app.api.v1.access_requests.routes import router as access_requests_router
from app.api.v1.provider.access_requests_routes import (
    router as provider_access_requests_router,
)
from app.api.v1.data_ingestion.routes import router as data_ingestion_router
from app.api.v1.fleet_transactions.routes import router as fleet_transactions_router
from app.api.v1.fms_transactions.routes import router as fms_transactions_router
from app.api.v1.nozzle_assignments.routes import router as nozzle_assignments_router
from app.api.v1.organizations.routes import router as organizations_router
from app.api.v1.pos_batch_settlements.routes import (
    router as pos_batch_settlements_router,
)
from app.api.v1.pumps.routes import router as pumps_router
from app.api.v1.reconciliation.routes import router as reconciliation_router
from app.api.v1.reports.routes import router as reports_router
from app.api.v1.shifts.routes import router as shifts_router
from app.api.v1.tenants.routes import router as tenants_router
from app.api.v1.users.routes import router as users_router
from app.api.v1.workers.routes import router as workers_router

api_router = APIRouter()

api_router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"],
)
api_router.include_router(
    tenants_router,
    prefix="/tenants",
    tags=["Tenants"],
)
api_router.include_router(
    organizations_router,
    prefix="/organizations",
    tags=["Organizations"],
)
api_router.include_router(
    pumps_router,
    prefix="/pumps",
    tags=["Pumps"],
)
api_router.include_router(
    workers_router,
    prefix="/workers",
    tags=["Workers"],
)
api_router.include_router(
    users_router,
    prefix="/users",
    tags=["Users"],
)
api_router.include_router(
    shifts_router,
    prefix="/shifts",
    tags=["Shifts"],
)
api_router.include_router(
    data_ingestion_router,
    prefix="/data-ingestion",
    tags=["Data Ingestion"],
)
api_router.include_router(
    reconciliation_router,
    prefix="/reconciliation",
    tags=["Reconciliation"],
)
api_router.include_router(
    fms_transactions_router,
    prefix="/fms-transactions",
    tags=["FMS Transactions"],
)
api_router.include_router(
    pos_batch_settlements_router,
    prefix="/pos-batch-settlements",
    tags=["POS Batch Settlements"],
)
api_router.include_router(
    fleet_transactions_router,
    prefix="/fleet-transactions",
    tags=["Fleet Transactions"],
)
api_router.include_router(
    cash_entries_router,
    prefix="/cash-entries",
    tags=["Cash Entries"],
)
api_router.include_router(
    nozzle_assignments_router,
    prefix="/nozzle-assignments",
    tags=["Nozzle Assignments"],
)
api_router.include_router(
    anomaly_flags_router,
    prefix="/anomaly-flags",
    tags=["Anomaly Flags"],
)
api_router.include_router(
    meter_readings_router,
    prefix="/meter-readings",
    tags=["Meter Readings"],
)
api_router.include_router(
    upi_transactions_router,
    prefix="/upi-transactions",
    tags=["UPI Transactions"],
)
api_router.include_router(
    superadmin_router,
    prefix="/superadmin",
    tags=["Developer Portal (Superadmin)"],
)
api_router.include_router(
    provider_router,
    prefix="/provider",
    tags=["Provider Portal"],
)
api_router.include_router(
    audit_logs_router,
    prefix="/audit-logs",
    tags=["Audit Logs"],
)
api_router.include_router(
    daily_consolidation_router,
    tags=["Daily Consolidation"],
)
api_router.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["Analytics"],
)
api_router.include_router(
    reports_router,
    prefix="/reports",
    tags=["Reports"],
)
api_router.include_router(
    inventory_router,
    prefix="/inventory",
    tags=["Inventory"],
)
api_router.include_router(
    maintenance_router,
    prefix="/maintenance",
    tags=["Maintenance"],
)
api_router.include_router(
    contact_router,
    prefix="/contact",
    tags=["Contact"],
)
api_router.include_router(
    access_requests_router,
    prefix="/access-requests",
    tags=["Access Requests"],
)
api_router.include_router(
    provider_access_requests_router,
    prefix="/provider",
    tags=["Provider Portal"],
)
