import  uuid
import binascii, os
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from django.utils import timezone
import datetime
from django.urls import reverse
from django.conf import settings


# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, national_id, password=None, **extra_fields):
        if not national_id:
            raise ValueError("National ID is required")
        user = self.model(national_id=national_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, national_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(national_id, password, **extra_fields)


# User
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('patient', 'patient'),
        ('donor', 'donor'),
    )
    STATUS_CHOICES = (
        ('قيد الانتظار', 'قيد الانتظار'),
        ('جاهز', 'جاهز'),
        ('قيد المراجعة', 'قيد المراجعة'),
        ('تحت المطابقه', 'تحت المطابقه'),
        ('تحت العمليه', 'تحت العمليه'),
        ('مرفوض', 'مرفوض'),
    )

    BLOOD_TYPE_CHOICES = (
        ('A', 'A'),
        ('B', 'B'),
        ('O', 'O'),
        ('AB', 'AB'),
    )

    GENDER_CHOICES = (
        ('ذكر', 'ذكر '),
        ("انثي", "انثي"),

    )
    national_id = models.CharField(max_length=14, unique=True, null=False, blank=False)
    first_name = models.CharField(max_length=50, null=False, blank=False)
    last_name = models.CharField(max_length=50, null=False, blank=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=False, blank=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='قيد الانتظار', null=False, blank=False)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    city = models.CharField(max_length=50, default="القاهرة")
    birthdate = models.DateField(null=False, blank=False)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    bmi = models.FloatField(null=True, blank=True)
    blood_type = models.CharField(max_length=5, choices=BLOOD_TYPE_CHOICES, null=False, blank=False)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=False, blank=False)
    medical_record_number = models.CharField(max_length=50, blank=False, null=False)
    HLA_A_1 = models.CharField(max_length=10, blank=True, null=True)
    HLA_A_2 = models.CharField(max_length=10, blank=True, null=True)
    HLA_B_1 = models.CharField(max_length=10, blank=True, null=True)
    HLA_B_2 = models.CharField(max_length=10, blank=True, null=True)
    HLA_DR_1 = models.CharField(max_length=10, blank=True, null=True)
    HLA_DR_2 = models.CharField(max_length=10, blank=True, null=True)

    PRA = models.FloatField(null=True, blank=True)

    CMV_status = models.BooleanField(default=False)
    EBV_status = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)


    supervisor_doctor = models.ForeignKey(
        'Doctor',
        on_delete=models.SET_NULL,  # أو CASCADE حسب منطق المشروع
        related_name="patients",
        null=True,
        blank=False
    )

    hospital = models.ForeignKey(
        'Hospital', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='users'
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'national_id'
    REQUIRED_FIELDS = ['first_name', 'last_name','hospital']

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if self.height_cm and self.weight_kg and self.height_cm > 0:
            height_m = self.height_cm / 100
            self.bmi = round(self.weight_kg / (height_m ** 2), 2)
        else:
            self.bmi = None
        super().save(*args, **kwargs)

    def is_donor_medically_eligible(self):
        if self.role != 'donor' or self.bmi is None:
            return True
        return 18.5 <= self.bmi <= 35

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"


class OrganType(models.TextChoices):
    KIDNEY = 'kidney', 'kidney'
    KIDNEY_RIGHT = 'kidney_right', 'kidney_right'
    KIDNEY_LEFT = 'kidney_left', 'kidney_left'

    LIVER = 'liver', 'liver'
    LIVER_LOBE = 'liver_lobe', 'liver_lobe'

    HEART = 'heart','heart'

    LUNG_RIGHT = 'lung_right', 'lung_right'
    LUNG_LOBE = 'lung_lobe', 'lung_lobe'

    PANCREAS = 'pancreas', 'pancreas'
    LUNG_LEFT = 'lung_left', 'lung_left'
    PANCREAS_SEGMENT = 'pancreas_segment', 'pancreas_segment'


# Hospital & Doctor
class Hospital(models.Model):
    HOSPITAL_TYPE_CHOICES = (
        ('حكومي', 'حكومي'),
        ('خاص', 'خاص'),
    )
    name = models.CharField(max_length=100, null=False, blank=False)
    city = models.CharField(max_length=50, default="القاهره")
    location = models.CharField(max_length=200, null=False, blank=False)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=False, null=False)
    emergency_phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    working_hours = models.CharField(max_length=100, blank=False, null=False)
    hospital_type = models.CharField(max_length=10, choices=HOSPITAL_TYPE_CHOICES, default='حكومي')
    password = models.CharField(max_length=128)
    ministry = models.ForeignKey(
    'Ministry',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="hospitals"
)

    #     ministry = models.ForeignKey(
    #     'Ministry',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="hospitals"
    # )

    status = models.CharField(
            max_length=20,
            choices=[
                ('تحت المراجعه', 'تحت المراجعه'),
                ('نشط', 'نشط'),
                ('مرفوض', 'مرفوض'),
            ],
            default='تحت المراجعه'
    )
    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save(update_fields=['password'])

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.name


class Doctor(models.Model):
    name = models.CharField(max_length=100, null=False)
    specialty = models.CharField(max_length=100, null=False, blank=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='doctors', null=False)
    phone = models.CharField(max_length=20)

    def __str__(self):
        return f"Dr. {self.name}"


# Chronic Diseases
class ChronicDisease(models.Model):
    name = models.CharField(max_length=255, null=False, blank=False, unique=True)

    def __str__(self):
        return self.name


class UserChronicDisease(models.Model):
    SEVERITY_CHOICES = (
        ('منخفض', 'منخفض'),
        ('متوسط', 'متوسط'),
        ('عالي', 'عالي'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chronic_diseases')
    disease = models.ForeignKey(ChronicDisease, on_delete=models.CASCADE)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)

    def __str__(self):
        return f"{self.user} - {self.disease}"


# Patient & Donor Profiles

# class PatientMedicalProfile(models.Model):

#     URGENCY_CHOICES = (
#         ('low', 'Low'),
#         ('medium', 'Medium'),
#         ('high', 'High'),
#         ('critical', 'Critical'),
#     )

#     patient = models.OneToOneField(
#         User,
#         on_delete=models.CASCADE,
#         related_name='patient_profile'
#     )
#     organ_needed = models.CharField(
#         max_length=20,
#         choices=OrganType.choices,
#         default='liver'
#     )

#     # ✅ New fields
#     urgency_level = models.CharField(
#         max_length=20,
#         choices=URGENCY_CHOICES,
#         null=True,
#         blank=True,
#         help_text="Urgency level of the transplant"
#     )
#     waitlist_time_days = models.PositiveIntegerField(
#         null=True,
#         blank=True,
#         help_text="Number of days the patient has been on the waiting list"
#     )
#     dialysis_duration_days = models.PositiveIntegerField(
#         null=True,
#         blank=True,
#         help_text="Duration of dialysis in days (kidney patients only)"
#     )
#     MELD_score = models.FloatField(
#         null=True,
#         blank=True,
#         help_text="Model for End-Stage Liver Disease score (liver patients only)"
#     )
#     lung_severity_score = models.FloatField(
#         null=True,
#         blank=True,
#         help_text="Lung severity score (lung patients only)"
#     )

#     def clean(self):
#         KIDNEY_ORGANS = {'kidney', 'kidney_right', 'kidney_left'}
#         LIVER_ORGANS = {'liver', 'liver_lobe'}
#         LUNG_ORGANS = {'lung_right', 'lung_lobe'}

#         if self.dialysis_duration_days is not None and self.organ_needed not in KIDNEY_ORGANS:
#             raise ValidationError("dialysis_duration_days is only applicable for kidney patients.")

#         if self.MELD_score is not None and self.organ_needed not in LIVER_ORGANS:
#             raise ValidationError("MELD_score is only applicable for liver patients.")

#         if self.lung_severity_score is not None and self.organ_needed not in LUNG_ORGANS:
#             raise ValidationError("lung_severity_score is only applicable for lung patients.")

#     def save(self, *args, **kwargs):
#         self.full_clean()
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"{self.patient} needs {self.organ_needed}"


class PatientMedicalProfile(models.Model):

    URGENCY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )

    patient = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='patient_profile'
    )
    organ_needed = models.CharField(
        max_length=20,
        choices=OrganType.choices,
        default='liver'
    )

    # ✅ Dataset identifier (mirrors donor_code in DonorMedicalProfile)
    recipient_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Recipient ID from dataset e.g. R000861"
    )

    urgency_level = models.CharField(
        max_length=20,
        choices=URGENCY_CHOICES,
        null=True,
        blank=True,
        help_text="Urgency level of the transplant"
    )
    waitlist_time_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of days the patient has been on the waiting list"
    )
    dialysis_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of dialysis in days (kidney patients only)"
    )
    MELD_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Model for End-Stage Liver Disease score (liver patients only)"
    )
    lung_severity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Lung severity score (lung patients only)"
    )

    def clean(self):
        KIDNEY_ORGANS = {'kidney', 'kidney_right', 'kidney_left'}
        LIVER_ORGANS  = {'liver', 'liver_lobe'}
        LUNG_ORGANS   = {'lung_right', 'lung_lobe'}

        if self.dialysis_duration_days is not None and self.organ_needed not in KIDNEY_ORGANS:
            raise ValidationError("dialysis_duration_days is only applicable for kidney patients.")

        if self.MELD_score is not None and self.organ_needed not in LIVER_ORGANS:
            raise ValidationError("MELD_score is only applicable for liver patients.")

        if self.lung_severity_score is not None and self.organ_needed not in LUNG_ORGANS:
            raise ValidationError("lung_severity_score is only applicable for lung patients.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient} needs {self.organ_needed}"

class OrganPortion(models.TextChoices):
    FULL = 'full', 'Full'
    SEGMENT = 'segment', 'Segment'
    LOBE = 'lobe', 'Lobe'
class DonorMedicalProfile(models.Model):


    DONATION_TYPE_CHOICES = (
        ('living', 'Living'),
        ('deceased', 'Deceased'),
    )

    ORGAN_PARTIAL_ALLOWED = {
    'kidney': True,
    'liver': True,
    'heart': False,
    'lung': False,
    'pancreas': False,
    }

    organ_full_or_partial = models.CharField(
        max_length=20,
        choices=OrganPortion,
        default='full'
    )

    donation_type = models.CharField(
        max_length=20,
        choices=DONATION_TYPE_CHOICES,
        default='living'
    )


    donor = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='donor_profile'
    )
    organ_available = models.CharField(
        max_length=20,
        choices=OrganType.choices,
        default='liver'
    )
    kdpi_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Kidney Donor Profile Index (only for kidney donors)"
    )

    donor_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Donor ID from dataset e.g. D00748"
    )
 
    distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance in km between donor and recipient hospital"
    )
 
    cold_ischemia_limit_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum hours the organ can survive outside the body"
    )

    # def clean(self):
    #     if self.organ_available != 'kidney' and self.kdpi_score is not None:
    #         raise ValidationError("KDPI score is only applicable for kidney donors.")

    def clean(self):
        # ✅ KDPI مقبول لكل أنواع الكُلى (kidney, kidney_right, kidney_left)
        KIDNEY_ORGANS = {'kidney', 'kidney_right', 'kidney_left'}
 
        if self.organ_available not in KIDNEY_ORGANS and self.kdpi_score is not None:
            raise ValidationError("KDPI score is only for kidney donors.")
 
        PARTIAL_ALLOWED = {'kidney', 'kidney_right', 'kidney_left', 'liver', 'liver_lobe'}
 
        if self.organ_full_or_partial not in ('full', OrganPortion.FULL) and \
                self.organ_available not in PARTIAL_ALLOWED:
            raise ValidationError(
                f"{self.organ_available} cannot be partial donation."
            )
        



    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.donor} donates {self.organ_available}"
    



# Appointment
class Appointment(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True, blank=True)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    reason = models.TextField(blank=True, null=True)

    STATUS_CHOICES = (
        ('مجدول', 'مجدول'),
        ('مكتمل', 'مكتمل'),
        ('ملغى', 'ملغى'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='مجدول')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        if self.doctor and self.hospital and self.doctor.hospital != self.hospital:
            raise ValidationError("Doctor must belong to selected hospital")

        appointment_datetime = datetime.datetime.combine(
            self.appointment_date,
            self.appointment_time
        )
        if timezone.is_naive(appointment_datetime):
            appointment_datetime = timezone.make_aware(
                appointment_datetime,
                timezone.get_current_timezone()
            )

        if appointment_datetime <= timezone.now():
            raise ValidationError("Appointment must be in the future")

    class Meta:
        ordering = ['-appointment_date']

    def __str__(self):
        return f"{self.patient} - {self.appointment_date}"


# Organ & AI Matching
class OrganMatching(models.Model):
    STATUS_CHOICES = (
        ('قيد التحليل', 'قيد التحليل'),
        ('تحت المراجعه', 'تحت المراجعه'),
        ('تحت المطابقه', 'تحت المطابقه'),
        ('قيد الانتظار', 'قيد الانتظار'),
    )
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_matches')
    request_number = models.CharField(max_length=20, unique=True, blank=True)
    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='donor_matches')
    organ_type = models.CharField(max_length=20, choices=OrganType.choices)
    match_percentage = models.FloatField(null=True, blank=True, default=None)
    ai_result = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='قيد التحليل')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-match_percentage']

    def update_match(self):
        result = self.calculate_match(self.patient, self.donor)
        self.match_percentage = result['match_percentage']
        self.ai_result = result['ai_result']
        self.status = 'تحت المراجعه'
        self.save()

    def save(self, *args, **kwargs):
        if not self.request_number:
            # توليد رقم فريد تلقائي (مثال: OM-XXXX)
            self.request_number = f"OM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        if self.patient.role != "patient":
            raise ValidationError("Selected patient must have role patient")

        if self.donor.role != "donor":
            raise ValidationError("Selected donor must have role donor")

    def __str__(self):
        return f"{self.patient} ↔ {self.donor} ({self.match_percentage}%)"

    # HLA mismatch ديناميكي

    @property
    def hla_mismatch_count(self):
        mismatches = 0
        hla_fields = ['HLA_A_1', 'HLA_A_2', 'HLA_B_1', 'HLA_B_2', 'HLA_DR_1', 'HLA_DR_2']
        for field in hla_fields:
            patient_val = getattr(self.patient, field, None)
            donor_val = getattr(self.donor, field, None)
            if patient_val and donor_val and patient_val != donor_val:
                mismatches += 1
        return mismatches

    @staticmethod
    def calculate_match(patient, donor):
        mismatches = 0
        hla_fields = ['HLA_A_1', 'HLA_A_2', 'HLA_B_1', 'HLA_B_2', 'HLA_DR_1', 'HLA_DR_2']
        for field in hla_fields:
            patient_val = getattr(patient, field, None)
            donor_val = getattr(donor, field, None)
            if patient_val and donor_val and patient_val != donor_val:
                mismatches += 1

        score = max(0, 100 - mismatches * 10)

        if hasattr(donor, 'is_donor_medically_eligible') and not donor.is_donor_medically_eligible():
            score -= 20
            score = max(score, 0)
        return {
            "hla_mismatch_count": mismatches,
            "match_percentage": score,
            "ai_result": {
                "hla_mismatches": mismatches,
                "bmi": getattr(donor, 'bmi', None),
                "eligible": getattr(donor, 'is_donor_medically_eligible', lambda: False)()
            }
        }


# # Surgery
# class Surgery(models.Model):
#     SURGERY_STATUS = [
#         ('مجدولة', 'مجدولة'),
#         ('جاريه', 'جاريه'),
#         ('مكتملة', 'مكتملة'),
#         ('تحت المتابعة', 'تحت المتابعة'),
#     ]
#     DEPARTMENT_CHOICES = [
        
#         ('liver', 'liver'),
#         ('kidney', 'kidney'),
        
    
#     ]

#     surgery_number = models.CharField(max_length=50, unique=True)
#     organ_matching = models.OneToOneField(OrganMatching, on_delete=models.CASCADE)
#     surgery_name = models.CharField(max_length=100)
#     department = models.CharField(
#         max_length=50,
#         choices=DEPARTMENT_CHOICES,
#         default='kidney'
#     )

#     hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, null=False)
#     doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True)

#     scheduled_date = models.DateField()
#     scheduled_time = models.TimeField(null=True, blank=True)

#     status = models.CharField(
#         max_length=20,
#         choices=SURGERY_STATUS,
#         default='مجدولة'
#     )
#     duration = models.PositiveIntegerField(null=True, blank=True)
#     operation_room = models.CharField(max_length=100, null=True, blank=True)

#     created_at = models.DateTimeField(auto_now_add=True)

#     def clean(self):
#         if self.scheduled_time:
#             surgery_datetime = datetime.datetime.combine(
#                 self.scheduled_date,
#                 self.scheduled_time
#             )
#             surgery_datetime = timezone.make_aware(
#                 surgery_datetime,
#                 timezone.get_current_timezone()
#             )
#             if surgery_datetime <= timezone.now():
#                 raise ValidationError("Surgery must be in the future")
#         else:
#             if self.scheduled_date < timezone.now().date():
#                 raise ValidationError("Surgery date must be in the future")

#     def __str__(self):
#         return f"Surgery {self.surgery_number}"

#     def get_admin_url(self):
#         return reverse("admin:core_surgery_change", args=[self.id])
# Surgery
class Surgery(models.Model):
    SURGERY_STATUS = [
        ('مجدولة', 'مجدولة'),
        ('جاريه', 'جاريه'),
        ('تمت بنجاح', 'تمت بنجاح'),
        ('فشلت', 'فشلت'),
        ('تحت المتابعة', 'تحت المتابعة'),
    ]
    DEPARTMENT_CHOICES = [
        
        ('liver', 'liver'),
        ('kidney', 'kidney'),
        
    
    ]

    surgery_number = models.CharField(max_length=50, unique=True)
    organ_matching = models.OneToOneField(OrganMatching, on_delete=models.CASCADE)
    surgery_name = models.CharField(max_length=100)
    department = models.CharField(
        max_length=50,
        choices=DEPARTMENT_CHOICES,
        default='kidney'
    )

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, null=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True)

    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=SURGERY_STATUS,
        default='مجدولة'
    )
    duration = models.PositiveIntegerField(null=True, blank=True)
    operation_room = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.scheduled_time:
            surgery_datetime = datetime.datetime.combine(
                self.scheduled_date,
                self.scheduled_time
            )
            surgery_datetime = timezone.make_aware(
                surgery_datetime,
                timezone.get_current_timezone()
            )
            if surgery_datetime <= timezone.now():
                raise ValidationError("Surgery must be in the future")
        else:
            if self.scheduled_date < timezone.now().date():
                raise ValidationError("Surgery date must be in the future")

    def __str__(self):
        return f"Surgery {self.surgery_number}"

    def get_admin_url(self):
        return reverse("admin:core_surgery_change", args=[self.id])

# MRI Reports
class MRIReport(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mri_reports')
    # organ_type = models.CharField(max_length=50)

    # before_scan = models.ImageField(upload_to='mri/before/', null=True, blank=True)
    # after_scan = models.ImageField(upload_to='mri/after/', null=True, blank=True)
    before_scan = models.FileField(upload_to='mri/before/', null=True, blank=True)  # ✅ مش ImageField
    after_scan = models.FileField(upload_to='mri/after/', null=True, blank=True)
    nlp_report = models.FileField(upload_to='mri/nlp/', null=True, blank=True)  # ✅


    ai_result = models.TextField(null=True, blank=True)
    mismatch_alert = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MRI - {self.patient}"


# Patient Priority
class PatientPriority(models.Model):
    patient = models.OneToOneField(User, on_delete=models.CASCADE, related_name='priority')
    score = models.FloatField(default=0)
    level = models.CharField(
        max_length=20,
        choices=[
            ('اولوليه عاليه', 'اولوليه عاليه'),
            ('اولوليه متوسطة', 'اولوليه متوسطة'),
            ('اولوليه منخفضه', 'اولوليه منخفضه'),
            ('حرجة جداً', 'حرجة جداً'),

        ]
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient} - {self.level}"


# Alerts
class Alert(models.Model):
    ALERT_TYPES = (
        ('معلومة', 'معلومة'),
        ('تحذير', 'تحذير'),
        ('طبي', 'طبي'),
        ('حرج', 'حرج'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    message_title = models.TextField()
    message = models.TextField(default="title")
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.alert_type}"


class AlertHospital(models.Model):
    ALERT_TYPES = (
        ('معلومة', 'معلومة'),
        ('تحذير', 'تحذير'),
        ('حرج', 'حرج'),
    )

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, null=True, blank=True)
    message_title = models.TextField()
    message = models.TextField(default="title")
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.hospital} - {self.alert_type}"





class UserReport(models.Model):
    reportState = (
        ('مكتمل', 'مكتمل'),
        ('تحت الاجراء', 'تحت الاجراء'),
    )
    type = (
        ('اشعه', 'اشعه'),
        ('تحاليل', 'تحاليل'),
        ('تقرير طبي', 'تقرير طبي'),
    )

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_reports')
    report_type = models.CharField(max_length=50, choices=type)
    report_file = models.FileField(upload_to='user_reports/', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    report_title = models.TextField(null=True, blank=True)
    state = models.CharField(max_length=20, choices=reportState, null=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient} - {self.report_type}"


class SurgeryReport(models.Model):
    surgery = models.OneToOneField(Surgery, on_delete=models.CASCADE, related_name='report')

    result_summary = models.TextField()
    complications = models.TextField(null=True, blank=True)
    doctor_notes = models.TextField(null=True, blank=True)

    blood_pressure = models.CharField(max_length=20, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    temperature_c = models.FloatField(null=True, blank=True)
    heart_rate = models.PositiveIntegerField(null=True, blank=True)
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True)
    oxygen_saturation = models.FloatField(null=True, blank=True)

    report_file = models.FileField(upload_to='surgery_reports/files/', null=True, blank=True)
    report_image = models.ImageField(upload_to='surgery_reports/images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report for {self.surgery}"


class Allergy(models.Model):
    SEVERITY_CHOICES = [
        ('منخفض', 'منخفض'),
        ('متوسط', 'متوسط'),
        ('عالي', 'عالي'),
        ('حرج', 'حرج'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='allergies')
    name = models.CharField(max_length=100)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='منخفض')

    def __str__(self):
        return f"{self.name} - {self.user}"


class Medicine(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medicines'
    )
    name = models.CharField(max_length=255)
    frequency_per_day = models.PositiveIntegerField(default=1)  # عدد المرات اليومية
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.user}"


class HospitalToken(models.Model):
    hospital = models.OneToOneField('Hospital', on_delete=models.CASCADE, related_name='token')
    key = models.CharField(max_length=40, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = binascii.hexlify(os.urandom(20)).decode()  # 40 char hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Token for {self.hospital.name}"

# class Ministry(models.Model):
#     name = models.CharField(max_length=200)
#     email = models.EmailField(unique=True)
#     phone = models.CharField(max_length=20)
#     password = models.CharField(max_length=128)

#     created_at = models.DateTimeField(auto_now_add=True)

#     def set_password(self, raw_password):
#         self.password = make_password(raw_password)
#         self.save(update_fields=['password'])

#     def check_password(self, raw_password):
#         return check_password(raw_password, self.password)

#     def __str__(self):
#         return self.name



class Ministry(models.Model):
    national_id = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    password = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 🚫 منع إنشاء أكتر من وزارة
        if not self.pk and Ministry.objects.exists():
            raise ValidationError("يوجد وزارة بالفعل، لا يمكن إنشاء أكثر من واحدة")
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save(update_fields=['password'])

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
    
    def clean(self):
        if not self.national_id.isdigit() or len(self.national_id) != 5:
            raise ValidationError("كود الوزارة لازم يكون 5 أرقام")

    def __str__(self):
        return self.name
    

class MinistryToken(models.Model):
    ministry = models.OneToOneField(Ministry, on_delete=models.CASCADE)
    key = models.CharField(max_length=40, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ministry.name} Token"



class MinistryAlert(models.Model):
    ALERT_TYPES = (
        ('خطر', 'خطر'),
        ('تحذير', 'تحذير'),
        ('تم الحل', 'تم الحل'),
        ('حرج', 'حرج'),
        
    )
    ALERT_Status = (
        ('متابعة التحقيق', 'متابعة التحقيق'),
        ('قيد التحقيق', 'قيد التحقيق'),
        
    )
 
    PRIORITY_CHOICES = (
        ('منخفضة', 'منخفضة'),
        ('متوسطة', 'متوسطة'),
        ('عالية', 'عالية'),
    )

    ministry = models.ForeignKey(
        Ministry,
        on_delete=models.CASCADE,
        related_name='alerts'
    )

    sender_hospital = models.ForeignKey(
        Hospital,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ministry_notifications'
            )

    message_title = models.TextField()
    message = models.TextField()

    alert_type = models.CharField(
        max_length=20,
        choices=ALERT_TYPES
    )
    ALERT_Status= models.CharField(
        max_length=20,
        choices=ALERT_Status
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='متوسطة'
    )
    description = models.TextField(blank=True, null=True)

    read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ministry.name} - {self.alert_type} - {self.priority}"
