# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
# router.register(r'ministry', MinistryViewSet, basename='ministry'),
router.register(r'users', UserViewSet, basename='user')
router.register(r'hospitals', HospitalViewSet, basename='hospital')
router.register(r'doctors', DoctorViewSet, basename='doctor')
router.register(r'chronic-diseases', ChronicDiseaseViewSet, basename='chronic-disease')
router.register(r'user-chronic-diseases', UserChronicDiseaseViewSet, basename='user-chronic-disease')
router.register(r'patient-profiles', PatientMedicalProfileViewSet, basename='patient-profile')
router.register(r'donor-profiles', DonorMedicalProfileViewSet, basename='donor-profile')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'organ-matching', OrganMatchingViewSet, basename='organ-matching')
router.register(r'surgeries', SurgeryViewSet, basename='surgery')
router.register(r'mri-reports', MRIReportViewSet, basename='mri-report')
router.register(r'UserReport', UserReportViewSet, basename='UserReport')
router.register(r'surgery-reports', SurgeryReportViewSet, basename='surgery-reports')
router.register(r'patient-priority', PatientPriorityViewSet, basename='patient-priority')
router.register(r'donor-health-status', DonorHealthStatusViewSet,basename='donor-health-status')
router.register(r'alerts', AlertViewSet, basename='alert')
router.register(r'hospital-alerts', HospitalAlertViewSet, basename='hospital-alert')
router.register(r'allergies', AllergyViewSet, basename='allergy')
router.register(r'medicines', MedicineViewSet, basename='medicine')
router.register(r'search/patients', PatientSearchViewSet, basename='patient-search')
router.register(r'search/donors', DonorSearchViewSet, basename='donor-search')
router.register(r'ministry/dashboard', MinistryDashboardViewSet, basename='ministry-dashboard')
router.register(r'ministry-alerts', MinistryAlertViewSet, basename='ministry-alerts')
router.register(r'vital-signs', VitalSignsViewSet)
router.register(r'create-patient', PatientCreateViewSet, basename='create-patient')
router.register(r'create-donor', DonorCreateViewSet, basename='create-donor')



urlpatterns = [
    path('', include(router.urls)),

    path('register/', RegisterUserView.as_view(), name='register-user'),
    # path('login/', LoginUserView.as_view(), name='login-user'),
    path('logout/', LogoutUserView.as_view(), name='logout-user'),
    path('hospital/register/', HospitalRegisterView.as_view(), name='hospital-register'),
    # path('hospital/login/', HospitalLoginView.as_view(), name='hospital-login'),
    path('login/', UnifiedLoginView.as_view(), name='unified-login'),
    path('hospital/change-password/', ChangeHospitalPasswordView.as_view(), name='change_password'),
    path('ministry/register/', MinistryRegisterView.as_view()),
     path('send-ministry-alert/', SendMinistryAlertView.as_view()),

    # path('users/search_by_organ/', search_users_by_organ, name='search_by_organ'),
]
