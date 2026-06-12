from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlertViewSet,
    AuditLogViewSet,
    CalendarTaskViewSet,
    ChangePasswordView,
    CommunityAccountView,
    CommunityChildcareWorkerViewSet,
    CourtViewSet,
    DistrictViewSet,
    HealthView,
    LoginView,
    MapBoundariesView,
    MapCasesView,
    MeView,
    MoreInformationRequestViewSet,
    NotificationRuleViewSet,
    NotificationViewSet,
    OrganizationViewSet,
    PartnersInDistrictViewSet,
    ProvinceViewSet,
    PublicSubmissionViewSet,
    RelationshipTypeViewSet,
    ReportsAnalyticsView,
    ReportsExcelExportView,
    ReportsGenerateView,
    ReportsPdfExportView,
    ReportsPowerPointExportView,
    UserViewSet,
    WardViewSet,
)

router = DefaultRouter()
router.register("alerts", AlertViewSet, basename="alert")
router.register("information-requests", MoreInformationRequestViewSet, basename="information-request")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("notification-rules", NotificationRuleViewSet, basename="notification-rule")
router.register("users", UserViewSet, basename="user")
router.register("provinces", ProvinceViewSet, basename="province")
router.register("districts", DistrictViewSet, basename="district")
router.register("wards", WardViewSet, basename="ward")
router.register("ccws", CommunityChildcareWorkerViewSet, basename="ccw")
router.register("partners-in-district", PartnersInDistrictViewSet, basename="partners-in-district")
router.register("courts", CourtViewSet, basename="court")
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("relationship-types", RelationshipTypeViewSet, basename="relationship-type")
router.register("public-submissions", PublicSubmissionViewSet, basename="public-submission")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
router.register("calendar-tasks", CalendarTaskViewSet, basename="calendar-task")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/register-community/", CommunityAccountView.as_view(), name="register-community"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("map/boundaries/", MapBoundariesView.as_view(), name="map-boundaries"),
    path("map/cases/", MapCasesView.as_view(), name="map-cases"),
    path("reports/analytics/", ReportsAnalyticsView.as_view(), name="reports-analytics"),
    path("reports/generate/", ReportsGenerateView.as_view(), name="reports-generate"),
    path("reports/export/excel/", ReportsExcelExportView.as_view(), name="reports-export-excel"),
    path("reports/export/pdf/", ReportsPdfExportView.as_view(), name="reports-export-pdf"),
    path("reports/export/powerpoint/", ReportsPowerPointExportView.as_view(), name="reports-export-powerpoint"),
    path("", include(router.urls)),
]
