from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(Hospital)
admin.site.register(Doctor)
admin.site.register(ChronicDisease)
admin.site.register(UserChronicDisease)
admin.site.register(PatientMedicalProfile)
admin.site.register(DonorMedicalProfile)
admin.site.register(Appointment)
admin.site.register(OrganMatching)
admin.site.register(Surgery)
admin.site.register(MRIReport)
admin.site.register(PatientPriority)
admin.site.register(Alert)
admin.site.register(UserReport)
admin.site.register(SurgeryReport)
# admin.site.register(VitalSign)



