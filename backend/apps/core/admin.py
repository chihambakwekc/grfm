from django.contrib import admin

from .models import Alert, AuditLog, CaseAction, CaseEscalation, CaseInvestigation, CaseReferral, CaseResolution, CaseTimeline, CitizenFeedback, CommunityChildcareWorker, Court, District, Intake, MoreInformationRequest, Notification, NotificationRule, Organization, PartnersInDistrict, Province, PublicSubmission, UpdateRequest, UserProfile, Ward


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "organization", "district", "ward", "active")
    list_filter = ("role", "active", "district")
    search_fields = ("user__username", "user__first_name", "user__last_name", "phone")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("reference", "programme", "priority", "child_display_name", "district", "status", "internal_status", "emergency", "created_at")
    list_filter = ("programme", "priority", "status", "internal_status", "emergency", "district")
    search_fields = ("reference", "programme", "priority", "child_first_name", "child_surname", "description")


@admin.register(Intake)
class IntakeAdmin(admin.ModelAdmin):
    list_display = ("temporary_case_reference", "alert", "status", "risk_level", "allocated_officer", "created_at")
    list_filter = ("status", "risk_level", "immediate_action_required")
    search_fields = ("temporary_case_reference", "alert__reference")


@admin.register(PublicSubmission)
class PublicSubmissionAdmin(admin.ModelAdmin):
    list_display = ("reference", "submission_type", "programme", "district", "category", "priority", "status", "satisfaction_score", "created_at")
    list_filter = ("submission_type", "status", "priority", "district")
    search_fields = ("reference", "programme", "category", "description", "transcript")


admin.site.register(Province)
admin.site.register(District)
admin.site.register(Ward)
admin.site.register(CommunityChildcareWorker)
admin.site.register(PartnersInDistrict)
admin.site.register(Court)
admin.site.register(Organization)
admin.site.register(MoreInformationRequest)
admin.site.register(CaseInvestigation)
admin.site.register(CaseAction)
admin.site.register(CaseReferral)
admin.site.register(CaseEscalation)
admin.site.register(CaseResolution)
admin.site.register(CitizenFeedback)
admin.site.register(CaseTimeline)
admin.site.register(Notification)
admin.site.register(NotificationRule)
admin.site.register(AuditLog)
admin.site.register(UpdateRequest)
