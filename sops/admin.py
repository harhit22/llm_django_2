from django.contrib import admin

from .models import SopQNA, Sops, City, SopStep


# Register your models here.


class SopsAdmin(admin.ModelAdmin):
    # List display for the admin interface
    list_display = [
        'sop', 'action_owner', 'department', 'topics', 'vertical', 'training_and_task_start', 'sop_percentage',
        'in_working'
    ]

    # List filter to allow filtering based on department, frequency, and in_working status
    list_filter = ['department', 'in_working', 'frequency', 'cities']

    # Search fields for the admin interface
    search_fields = ['sop', 'action_owner', 'topics', 'vertical']

    # Filter for ManyToMany fields in the form view
    filter_horizontal = ['cities']

    # Form layout customization
    fieldsets = (
        (None, {
            'fields': ('sop', 'action_owner', 'department', 'cities')
        }),
        ('Details', {
            'fields': ('topics', 'vertical', 'training_and_task_start', 'action_step'),
        }),
        ('Deadlines and Assessments', {
            'fields': ('Deadline_1', 'assessment_1', 'Deadline_2', 'assessment_2'),
        }),
        ('Team Information', {
            'fields': ('team_assessment', 'no_of_deadline', 'total_sop_step', 'done_sop_step_number', 'sop_percentage'),
        }),
        ('Frequency & Status', {
            'fields': ('frequency', 'in_working'),
        }),
    )


@admin.register(SopStep)
class SopStepAdmin(admin.ModelAdmin):
    list_display = ["id", "step_number", "description", "sop"]


@admin.register(City)
class SopStepAdmin(admin.ModelAdmin):
    list_display = ["id", 'city']


admin.site.register(SopQNA)
admin.site.register(Sops, SopsAdmin)

