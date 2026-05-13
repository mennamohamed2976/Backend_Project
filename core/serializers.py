from rest_framework import serializers
from .models import *
from django.contrib.auth import authenticate
from django.utils import timezone
import datetime
from rest_framework.authtoken.models import Token


# register users
class RegisterSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=[('patient', 'Patient'), ('donor', 'Donor')])
    organ = serializers.ChoiceField(choices=OrganType.choices, write_only=True)
    supervisor_doctor = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(),
        required=False
    )

    class Meta:
        model = User
        fields = [
            'national_id', 'first_name', 'last_name', 'role',
            'birthdate', 'height_cm', 'weight_kg',
            'blood_type', 'gender', 'phone', 'hospital',
            'organ', 'medical_record_number', 'supervisor_doctor', 'email', 'city',
        ]

    def validate_national_id(self, value):
        if len(value) != 14 or not value.isdigit():
            raise serializers.ValidationError("National ID must be 14 digits")
        if User.objects.filter(national_id=value).exists():
            raise serializers.ValidationError("National ID already exists")
        return value

    def validate(self, data):
        role = data.get("role")
        organ = data.get("organ")

        if role == "patient" and not organ:
            raise serializers.ValidationError("Patient must specify organ needed")

        if role == "donor" and not organ:
            raise serializers.ValidationError("Donor must specify organ available")

        return data

    #  إنشاء المستخدم والبروفايل حسب الدور
    def create(self, validated_data):
        organ = validated_data.pop('organ')
        doctor = validated_data.pop('supervisor_doctor', None)
        national_id = validated_data['national_id']
        role = validated_data['role']

        # Password = آخر 4 أرقام من الرقم القومي
        password = national_id[-4:]

        # إنشاء المستخدم مرة واحدة فقط
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()

        if doctor:
            user.supervisor_doctor = doctor
            user.save()

        # إنشاء profile حسب الدور
        if role == 'patient':
            PatientMedicalProfile.objects.create(
                patient=user,
                organ_needed=organ
            )
        elif role == 'donor':
            DonorMedicalProfile.objects.create(
                donor=user,
                organ_available=organ
            )

        # حفظ الباسورد المؤقت للعرض
        user._temp_password = password

        return user


# hospital registration
class HospitalRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Hospital
        fields = ['name', 'location', 'license_number', 'phone', 'emergency_phone', 'email', 'working_hours',
                  'hospital_type', 'password']

    def validate(self, data):
        # doctor = data.get("supervisor_doctor")
        # hospital = data.get("hospital")

        # if doctor and hospital and doctor.hospital != hospital:
        #     raise serializers.ValidationError("Doctor must belong to selected hospital")
        return data


class UnifiedLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        identifier = data.get("identifier")
        password = data.get("password")

        if not identifier or not password:
            raise serializers.ValidationError({
                "message": "الرجاء إدخال identifier و password"
            })

        # 🔴 1. Ministry (5 digits only)
        if identifier.isdigit() and len(identifier) == 5:
            try:
                ministry = Ministry.objects.get(national_id=identifier)
            except Ministry.DoesNotExist:
                raise serializers.ValidationError({
                    "message": "الوزارة غير موجودة"
                })

            if not ministry.check_password(password):
                raise serializers.ValidationError({
                    "message": "كلمة مرور الوزارة غير صحيحة"
                })

            token, _ = MinistryToken.objects.get_or_create(ministry=ministry)

            data["type"] = "ministry"
            data["ministry"] = ministry
            data["token"] = token.key
            return data

        # 🔵 2. Hospital (email)
        if "@" in identifier:
            try:
                hospital = Hospital.objects.get(email=identifier)
            except Hospital.DoesNotExist:
                raise serializers.ValidationError({
                    "message": "المستشفى غير موجودة"
                })

            if not hospital.check_password(password):
                raise serializers.ValidationError({
                    "message": "بيانات المستشفى غير صحيحة"
                })

            token, _ = HospitalToken.objects.get_or_create(hospital=hospital)

            data["type"] = "hospital"
            data["hospital"] = hospital
            data["token"] = token.key
            return data

        # 🟢 3. User (national_id)
        user = authenticate(username=identifier, password=password)

        if not user:
            raise serializers.ValidationError({
                "message": "بيانات المستخدم غير صحيحة"
            })

        token, _ = Token.objects.get_or_create(user=user)

        data["type"] = "user"
        data["user"] = user
        data["token"] = token.key

        return data

# mini serializer for search results
class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    CMV_status = serializers.SerializerMethodField()
    EBV_status = serializers.SerializerMethodField()


    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'role', 'national_id', 'blood_type', 'gender', 
            'medical_record_number', 'status',
            'HLA_A_1', 'HLA_A_2', 'HLA_B_1', 'HLA_B_2', 'HLA_DR_1', 'HLA_DR_2',
            'EBV_status', 'CMV_status', 'PRA',
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_CMV_status(self, obj):
        return "Positive" if obj.CMV_status else "Negative"

    def get_EBV_status(self, obj):
        return "Positive" if obj.EBV_status else "Negative"


# الحساسيه
class AllergySerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    # user_detail = UserMiniSerializer(read_only=True) # يجيب المستخدمين موجودين

    class Meta:
        model = Allergy
        fields = ['id', 'user', 'name', 'severity']


# medicine serializer

class MedicineSerializer(serializers.ModelSerializer):
    # user = UserMiniSerializer(read_only=True)  # يعرض بيانات المستخدم
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user', write_only=True
    )
    user_detail = UserMiniSerializer(source='user', read_only=True)

    # نستخدمه لتحديد المستخدم عند الـ POST

    class Meta:
        model = Medicine
        fields = ['id', 'user_detail', 'user_id', 'name', 'frequency_per_day', 'notes']


class ChronicDiseaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChronicDisease
        fields = '__all__'


class UserChronicDiseaseSerializer(serializers.ModelSerializer):
    disease_detail = ChronicDiseaseSerializer(source='disease', read_only=True)
    user_detail = UserMiniSerializer(source='user', read_only=True)

    class Meta:
        model = UserChronicDisease
        fields = ['id', 'user', 'user_detail', 'disease', 'disease_detail', 'severity']


class OrganMatchingSerializer(serializers.ModelSerializer):
    patient_detail = UserMiniSerializer(source='patient', read_only=True)
    donor_detail = UserMiniSerializer(source='donor', read_only=True)
    # patient_detail = serializers.SerializerMethodField()
    # donor_detail = serializers.SerializerMethodField()
    hla_mismatch_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrganMatching
        fields = [
            'id', 'patient', 'patient_detail', 'donor', 'donor_detail',
            'organ_type', 'match_percentage', 'hla_mismatch_count',
            'ai_result', 'status', 'created_at','request_number'
        ]
        # read_only_fields = ['hla_mismatch_count', 'match_percentage', 'ai_result', 'created_at']

    def get_patient_detail(self, obj):
        return {"id": obj.patient.id, "full_name": f"{obj.patient.first_name} {obj.patient.last_name}"}

    def get_donor_detail(self, obj):
        return {"id": obj.donor.id, "full_name": f"{obj.donor.first_name} {obj.donor.last_name}"}


class HospitalUserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'role',
            'national_id',
            'gender',
            'blood_type',
            'status',
        ]


class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = '__all__'


class AlertSerializer(serializers.ModelSerializer):
    user_detail = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = ['id', 'user', 'user_detail', 'message', 'message_title', 'alert_type', 'read', 'created_at', ]

    def get_user_detail(self, obj):
        return {"id": obj.user.id, "full_name": f"{obj.user.first_name} {obj.user.last_name}"}


class AlertHospitalSerializer(serializers.ModelSerializer):
    hospital_detail = serializers.SerializerMethodField()
    is_urgent = serializers.SerializerMethodField()

    class Meta:
        model = AlertHospital
        fields = ['id', 'hospital', 'hospital_detail', 'message', 'message_title', 'alert_type', 'read','is_urgent', 'created_at', ]

    def get_hospital_detail(self, obj):
        return {"id": obj.hospital.id, "name": obj.hospital.name}

    def get_is_urgent(self, obj):
        return obj.alert_type == "حرج"


class PatientPrioritySerializer(serializers.ModelSerializer):
    patient_detail = serializers.SerializerMethodField()

    class Meta:
        model = PatientPriority
        fields = ['id', 'patient', 'patient_detail', 'score', 'level', 'updated_at']

    def get_patient_detail(self, obj):
        return {"id": obj.patient.id, "full_name": f"{obj.patient.first_name} {obj.patient.last_name}"}


# doctor
class DoctorSerializer(serializers.ModelSerializer):
    hospital_detail = HospitalSerializer(source='hospital', read_only=True)

    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty', 'phone', 'hospital', 'hospital_detail']

    def validate_hospital(self, value):
        if not Hospital.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("المستشفى دي غير موجودة")
        return value


class MRIReportSerializer(serializers.ModelSerializer):
    patient_detail = UserMiniSerializer(source='patient', read_only=True)

    class Meta:
        model = MRIReport
        fields = ['id', 'patient', 'patient_detail', 'before_scan', 'after_scan','nlp_report',
                  'ai_result', 'mismatch_alert', 'created_at']


class SurgeryReportSerializer(serializers.ModelSerializer):
    # عرض أسماء الطرفيات
    patient_name = serializers.CharField(source='surgery.organ_matching.patient.__str__', read_only=True)
    doctor_name = serializers.CharField(source='surgery.doctor.name', read_only=True)
    hospital_name = serializers.CharField(source='surgery.hospital.name', read_only=True)
    surgery_detail = serializers.SerializerMethodField(read_only=True)  # بدل الـ nested كامل

    # اختيار الجراحة عند الإنشاء بالاسم
    surgery_number = serializers.SlugRelatedField(
        queryset=Surgery.objects.all(),
        slug_field='surgery_number',
        source='surgery',  # يرتبط بالـ ForeignKey 'surgery'
        write_only=True
    )

    # اسم العملية للعرض في GET
    surgery_name = serializers.CharField(
        source='surgery.surgery_number',
        read_only=True
    )

    duration = serializers.IntegerField(source='surgery.duration', read_only=True)
    operation_room = serializers.CharField(source='surgery.operation_room', read_only=True)

    class Meta:
        model = SurgeryReport
        fields = [
            'id',
            'surgery_number',  # للـ POST
            'surgery_name',  # للـ GET
            'surgery_detail',
            'patient_name',
            'doctor_name',
            'hospital_name',
            'duration',
            'operation_room',
            'result_summary',
            'complications',
            'doctor_notes',
            'report_file',
            'report_image',
            'created_at',
            'blood_pressure',
            'temperature_c',
            'heart_rate',
            'respiratory_rate',
            'oxygen_saturation',
            'recorded_at',

        ]

    def get_surgery_detail(self, obj):
        # ممكن تعرض معلومات مختصرة عن الجراحة بدل الـ nested serializer الكامل
        return {
            "surgery_number": obj.surgery.surgery_number,
            "status": obj.surgery.status,
            "scheduled_date": obj.surgery.scheduled_date,
        }


class AppointmentSerializer(serializers.ModelSerializer):
    patient_detail = UserMiniSerializer(source='patient', read_only=True)
    doctor_detail = DoctorSerializer(source='doctor', read_only=True)
    hospital_detail = HospitalSerializer(source='hospital', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_detail', 'doctor', 'doctor_detail',
            'hospital', 'hospital_detail', 'appointment_date', 'reason', 'status', 'created_at', 'appointment_time'

        ]

    def get_patient_detail(self, obj):
        return {"id": obj.patient.id, "full_name": f"{obj.patient.first_name} {obj.patient.last_name}"}

    def get_doctor_detail(self, obj):
        if obj.doctor:
            return {"id": obj.doctor.id, "name": obj.doctor.name, "specialty": obj.doctor.specialty}
        return None

    def get_hospital_detail(self, obj):
        if obj.hospital:
            return {"id": obj.hospital.id, "name": obj.hospital.name}
        return None

    def validate(self, data):

        doctor = data.get('doctor')
        hospital = data.get('hospital')
        appointment_date = data.get('appointment_date')
        appointment_time = data.get('appointment_time')

        # Doctor-Hospital validation
        if doctor and hospital and doctor.hospital != hospital:
            raise serializers.ValidationError(
                "Doctor must belong to selected hospital"
            )

        # Future validation (date + time)
        if appointment_date and appointment_time:
            appointment_datetime = datetime.datetime.combine(
                appointment_date,
                appointment_time
            )

        if timezone.is_naive(appointment_datetime):
            appointment_datetime = timezone.make_aware(
                appointment_datetime,
                timezone.get_current_timezone()
            )

        if appointment_datetime <= timezone.now():
            raise serializers.ValidationError(
                "Appointment must be in the future"
            )

        return data


class UserReportSerializer(serializers.ModelSerializer):
    patient_detail = serializers.SerializerMethodField()

    class Meta:
        model = UserReport
        fields = [
            'id', 'patient', 'patient_detail', 'report_type','report_title',
            'report_file', 'description', 'created_at', 'state','hospital'
        ]

    def get_patient_detail(self, obj):
        if obj.patient:
            return {
                "id": obj.patient.id,
                "full_name": f"{obj.patient.first_name} {obj.patient.last_name}",
                "national_id": getattr(obj.patient, 'national_id', None),
                "role": getattr(obj.patient, 'role', None)
            }
        return None



class SurgerySerializer(serializers.ModelSerializer):
    organ_matching_detail = OrganMatchingSerializer(source='organ_matching', read_only=True)
    doctor_detail = DoctorSerializer(source='doctor', read_only=True)
    hospital_detail = HospitalSerializer(source='hospital', read_only=True)

    class Meta:
        model = Surgery
        fields = [
            'id', 'surgery_number', 'organ_matching', 'organ_matching_detail',
            'hospital', 'hospital_detail', 'doctor', 'doctor_detail',
            'scheduled_date', 'scheduled_time', 'status', 'created_at', 'duration',
            'operation_room', 'surgery_name', 'department',

        ]


# user
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)
    surgeries = serializers.SerializerMethodField()
    organ_needed = serializers.SerializerMethodField()
    organ_available = serializers.SerializerMethodField()
    chronic_diseases = serializers.SerializerMethodField()
    hospital_detail = serializers.SerializerMethodField()
    supervisor_doctors_detail = serializers.SerializerMethodField()
    appointments = serializers.SerializerMethodField()
    mri_reports = serializers.SerializerMethodField()
    surgery_reports = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    allergies = serializers.SerializerMethodField()
    user_medicines = serializers.SerializerMethodField()
    alerts = serializers.SerializerMethodField()
    user_reports = serializers.SerializerMethodField()
    CMV_status = serializers.SerializerMethodField()
    EBV_status = serializers.SerializerMethodField()

    supervisor_doctor = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(),
        required=False
    )

    class Meta:
        model = User
        fields = [
            'id', 'national_id', 'first_name', 'last_name', 'full_name', 'role', 'status',
            'birthdate', 'height_cm', 'weight_kg', 'bmi', 'blood_type', 'gender',
            'HLA_A_1', 'HLA_A_2', 'HLA_B_1', 'HLA_B_2', 'HLA_DR_1', 'HLA_DR_2',
            'PRA', 'CMV_status', 'EBV_status', 'supervisor_doctor', 'updated_at',
            'hospital', 'allergies', 'phone', 'city', 'email', 'user_medicines',
            'is_active', 'is_staff', 'created_at', 'medical_record_number', 'surgeries',
            # بيانات profile
            'organ_needed', 'organ_available', 'chronic_diseases', 'hospital_detail', 'supervisor_doctors_detail',
            "appointments", "mri_reports", "surgery_reports", "priority", "alerts", 'user_reports'
        ]
        read_only_fields = ['bmi', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    # =========================
    # Patient fields
    # =========================
    # def get_organ_needed(self, obj):
    #     if obj.role == 'patient' and hasattr(obj, 'patient_profile'):
    #         return obj.patient_profile.organ_needed
    #     return None

    def get_organ_needed(self, obj):
        if obj.role == 'patient' and hasattr(obj, 'patient_profile'):
            profile = obj.patient_profile
            return {
                "organ_needed": profile.organ_needed,
                "recipient_id": profile.recipient_id,
                "urgency_level": profile.urgency_level,
                "waitlist_time_days": profile.waitlist_time_days,
                "dialysis_duration_days": profile.dialysis_duration_days,
                "MELD_score": profile.MELD_score,
                "lung_severity_score": profile.lung_severity_score,
            }
        return None

    def get_chronic_diseases(self, obj):
        if obj.role == 'patient' and hasattr(obj, 'patient_profile'):
            return [
                {"name": uc.disease.name, "severity": uc.severity}
                for uc in obj.chronic_diseases.all()
            ]
        elif obj.role == 'donor' and hasattr(obj, 'donor_profile'):
            return [
                {"name": uc.disease.name, "severity": uc.severity}
                for uc in obj.chronic_diseases.all()
            ]
        return []

    def get_hospital_detail(self, obj):
        if hasattr(obj, 'patient_profile') and obj.role == 'patient' and obj.hospital:

            return HospitalSerializer(obj.hospital).data
        elif hasattr(obj, 'donor_profile') and obj.role == 'donor' and obj.hospital:

            return HospitalSerializer(obj.hospital).data
        return None

    def get_supervisor_doctors_detail(self, obj):
        # access from User مباشرة
        if obj.role == 'patient':
            if obj.supervisor_doctor:
                from .serializers import DoctorSerializer
                return DoctorSerializer(obj.supervisor_doctor).data

            return None

        return []

    def get_organ_available(self, obj):
        if obj.role == 'donor' and hasattr(obj, 'donor_profile'):
            return obj.donor_profile.organ_available
        return None

    def get_user_reports(self, obj):
        from .serializers import UserReportSerializer
        qs = UserReport.objects.filter(patient=obj)
        return UserReportSerializer(qs, many=True).data

    def get_appointments(self, obj):
        from .serializers import AppointmentSerializer
        qs = Appointment.objects.filter(patient=obj).select_related('doctor', 'hospital')
        return AppointmentSerializer(qs, many=True).data

    def get_mri_reports(self, obj):
        from .serializers import MRIReportSerializer
        qs = MRIReport.objects.filter(patient=obj)
        return MRIReportSerializer(qs, many=True).data

    def get_surgery_reports(self, obj):
        from .serializers import SurgeryReportSerializer
        qs = SurgeryReport.objects.filter(surgery__organ_matching__patient=obj) \
            .select_related('surgery', 'surgery__doctor', 'surgery__hospital')
        return SurgeryReportSerializer(qs, many=True).data

    def get_priority(self, obj):
        from .serializers import PatientPrioritySerializer
        try:
            priority = PatientPriority.objects.select_related('patient').get(patient=obj)
            return PatientPrioritySerializer(priority).data
        except PatientPriority.DoesNotExist:
            return None

    def get_alerts(self, obj):
        from .serializers import AlertSerializer
        qs = Alert.objects.filter(user=obj)
        return AlertSerializer(qs, many=True).data

    def get_surgeries(self, obj):
        from .serializers import SurgerySerializer

        if obj.role == 'patient':
            qs = Surgery.objects.filter(
                organ_matching__patient=obj
            ).select_related(
                'doctor', 'hospital', 'organ_matching'
            ).order_by('-scheduled_date')  # آخر عملية

        elif obj.role == 'donor':
            qs = Surgery.objects.filter(
                organ_matching__donor=obj
            ).select_related(
                'doctor', 'hospital', 'organ_matching'
            ).order_by('-scheduled_date')  # آخر عملية

        else:
            return None

        # ترجع العملية الأولى فقط بدل كل العمليات
        latest_surgery = qs.first()
        if latest_surgery:
            return SurgerySerializer(latest_surgery).data
        return None

    def get_allergies(self, obj):
        from .serializers import AllergySerializer
        qs = Allergy.objects.filter(user=obj)
        return AllergySerializer(qs, many=True).data

    def get_user_medicines(self, obj):
        from .serializers import MedicineSerializer
        qs = Medicine.objects.filter(user=obj)
        return MedicineSerializer(qs, many=True).data
    
    def get_CMV_status(self, obj):
        return "Positive" if obj.CMV_status else "Negative"

    def get_EBV_status(self, obj):
        return "Positive" if obj.EBV_status else "Negative"
    


# class PatientMedicalProfileSerializer(serializers.ModelSerializer):
#     patient_detail = UserMiniSerializer(source='patient', read_only=True)
#     chronic_diseases = serializers.SerializerMethodField()
#     hospital_detail = serializers.SerializerMethodField()
#     supervisor_doctor_detail = serializers.SerializerMethodField()  # ✅ صح

#     class Meta:
#         model = PatientMedicalProfile
#         fields = [
#             'patient_detail',
#             'organ_needed',
#             'chronic_diseases',
#             'hospital_detail',
#             'supervisor_doctor_detail'
#         ]

#     def get_chronic_diseases(self, obj):
#         return [
#             {"name": uc.disease.name, "severity": uc.severity}
#             for uc in obj.patient.chronic_diseases.all()
#         ]

#     def get_hospital_detail(self, obj):
#         if obj.patient.hospital:
#             return HospitalSerializer(obj.patient.hospital).data
#         return None

#     def get_supervisor_doctor_detail(self, obj):
#         if obj.patient.supervisor_doctor:
#             return DoctorSerializer(obj.patient.supervisor_doctor).data
#         return None





class PatientMedicalProfileSerializer(serializers.ModelSerializer):
    patient_detail = UserMiniSerializer(source='patient', read_only=True)
    chronic_diseases = serializers.SerializerMethodField()
    hospital_detail = serializers.SerializerMethodField()
    supervisor_doctor_detail = serializers.SerializerMethodField()

    class Meta:
        model = PatientMedicalProfile
        fields = [
            'patient_detail',
            'organ_needed',
            'recipient_id',          
            'urgency_level',         
            'waitlist_time_days',    
            'dialysis_duration_days',
            'MELD_score',            
            'lung_severity_score',   
            'chronic_diseases',
            'hospital_detail',
            'supervisor_doctor_detail',
        ]

    def get_chronic_diseases(self, obj):
        return [
            {"name": uc.disease.name, "severity": uc.severity}
            for uc in obj.patient.chronic_diseases.all()
        ]

    def get_hospital_detail(self, obj):
        if obj.patient.hospital:
            return HospitalSerializer(obj.patient.hospital).data
        return None

    def get_supervisor_doctor_detail(self, obj):
        if obj.patient.supervisor_doctor:
            return DoctorSerializer(obj.patient.supervisor_doctor).data
        return None












class DonorMedicalProfileSerializer(serializers.ModelSerializer):
    donor_detail = UserMiniSerializer(source='donor', read_only=True)
    chronic_diseases = serializers.SerializerMethodField()
    hospital_detail = serializers.SerializerMethodField()
    supervisor_doctor_detail = serializers.SerializerMethodField()  # ✅

    class Meta:
        model = DonorMedicalProfile
        fields = [
            'id',
            'donor',
            'donor_detail',
            'organ_available',
            'chronic_diseases',
            'hospital_detail',
            'supervisor_doctor_detail',
            'donation_type',
            'kdpi_score',
            'organ_full_or_partial',
            'donor_code',
            'distance_km',
            'cold_ischemia_limit_hours'
        ]

    def get_chronic_diseases(self, obj):
        return [
            {"name": uc.disease.name, "severity": uc.severity}
            for uc in obj.donor.chronic_diseases.all()
        ]

    def get_hospital_detail(self, obj):
        if obj.donor.hospital:
            return HospitalSerializer(obj.donor.hospital).data
        return None

    def get_supervisor_doctor_detail(self, obj):
        if obj.donor.supervisor_doctor:
            return DoctorSerializer(obj.donor.supervisor_doctor).data
        return None
    


# hospital
class HospitalFullSerializer(serializers.ModelSerializer):
    patients = serializers.SerializerMethodField()
    donors = serializers.SerializerMethodField()
    patients_count = serializers.SerializerMethodField()
    donors_count = serializers.SerializerMethodField()
    total_matches = serializers.SerializerMethodField()
    waiting_transplant_count = serializers.SerializerMethodField()
    total_surgeries = serializers.SerializerMethodField()
    scheduled_surgeries_count = serializers.SerializerMethodField()
    ongoing_surgeries_count = serializers.SerializerMethodField()
    completed_surgeries_count = serializers.SerializerMethodField()
    under_review_surgeries_count = serializers.SerializerMethodField()
    alerts_hospitals = serializers.SerializerMethodField()
    matches = serializers.SerializerMethodField()
    surgeries = serializers.SerializerMethodField()
    analysis_matches_count = serializers.SerializerMethodField()
    review_matches_count = serializers.SerializerMethodField()
    matching_matches_count = serializers.SerializerMethodField()
    total_alerts = serializers.SerializerMethodField()
    unread_alerts = serializers.SerializerMethodField()
    critical_alerts = serializers.SerializerMethodField()

    class Meta:
        model = Hospital
        fields = [
            'id', 'name', 'hospital_type', 'location', 'license_number',
            'phone', 'emergency_phone', 'email', 'working_hours',
            'patients_count', 'donors_count', 'patients', 'donors',
            'total_matches', 'total_surgeries', 'scheduled_surgeries_count',
            'ongoing_surgeries_count', 'completed_surgeries_count', 'under_review_surgeries_count', 'alerts_hospitals',
            'matches', 'surgeries', 'waiting_transplant_count', 'analysis_matches_count', 'review_matches_count',
            'matching_matches_count',
            'total_alerts', 'unread_alerts', 'critical_alerts'
        ]

    # get كل الـ matches لكل المرضى والمانحين في المستشفى

    def get_matches(self, obj):
        matches = OrganMatching.objects.filter(
            patient__hospital=obj
        )
        return OrganMatchingSerializer(matches, many=True).data

    # get كل الـ surgeries لكل المرضى والمانحين في المستشفى
    def get_surgeries(self, obj):
        surgeries = Surgery.objects.filter(
            hospital=obj
        )
        return SurgerySerializer(surgeries, many=True).data

    # all surgeries for all patients and donors in the hospital
    def get_total_surgeries(self, obj):
        return Surgery.objects.filter(
            hospital=obj
        ).count()

    def get_waiting_transplant_count(self, obj):
        return OrganMatching.objects.filter(
            patient__hospital=obj,
            status='قيد الانتظار'
        ).count()

    def get_alerts_hospitals(self, obj):
        alerts = AlertHospital.objects.filter(hospital=obj)
        return AlertHospitalSerializer(alerts, many=True).data

    # def get_patients(self, obj):
    #     qs = obj.users.filter(role='patient')
    #     data = []
    #     for patient in qs:
    #         patient_data = UserSerializer(patient).data
    #         surgeries = Surgery.objects.filter(organ_matching__patient=patient)
    #         patient_data['surgeries'] = SurgerySerializer(surgeries, many=True).data
    #         matches = OrganMatching.objects.filter(patient=patient)
    #         patient_data['matches'] = OrganMatchingSerializer(matches, many=True).data
    #         try:
    #             priority = PatientPriority.objects.get(patient=patient)
    #             patient_data['priority'] = PatientPrioritySerializer(priority).data
    #         except PatientPriority.DoesNotExist:
    #             patient_data['priority'] = None
    #         alerts = Alert.objects.filter(user=patient)
    #         patient_data['alerts'] = AlertSerializer(alerts, many=True).data
    #         data.append(patient_data)
    #     return data

    def get_patients(self, obj):
        # 1️⃣ جلب كل المرضى مع الـ profile
        patients_qs = obj.users.filter(role='patient').select_related('patient_profile', 'supervisor_doctor',
                                                                      'hospital')

        # 2️⃣ جلب كل العمليات مرة واحدة لكل المرضى
        surgeries_qs = Surgery.objects.filter(
            organ_matching__patient__in=patients_qs
        ).select_related('doctor', 'hospital', 'organ_matching')

        # 3️⃣ جلب كل الـ matches مرة واحدة
        matches_qs = OrganMatching.objects.filter(patient__in=patients_qs)

        # 4️⃣ جلب كل أولويات المرضى مرة واحدة
        priorities_qs = PatientPriority.objects.filter(patient__in=patients_qs)
        priorities_map = {p.patient_id: p for p in priorities_qs}

        # 5️⃣ جلب كل التنبيهات مرة واحدة
        alerts_qs = Alert.objects.filter(user__in=patients_qs)
        alerts_map = {}
        for alert in alerts_qs:
            alerts_map.setdefault(alert.user_id, []).append(alert)

        data = []

        for patient in patients_qs:
            patient_data = UserSerializer(patient).data

            # العمليات
            patient_surgeries = [s for s in surgeries_qs if s.organ_matching.patient_id == patient.id]
            patient_data['surgeries'] = SurgerySerializer(patient_surgeries, many=True).data

            # المطابقات
            patient_matches = [m for m in matches_qs if m.patient_id == patient.id]
            patient_data['matches'] = OrganMatchingSerializer(patient_matches, many=True).data

            # الأولوية
            priority = priorities_map.get(patient.id)
            patient_data['priority'] = PatientPrioritySerializer(priority).data if priority else None

            # التنبيهات
            patient_alerts = alerts_map.get(patient.id, [])
            patient_data['alerts'] = AlertSerializer(patient_alerts, many=True).data

            data.append(patient_data)

        return data
        # def get_donors(self, obj):

    #     qs = obj.users.filter(role='donor')
    #     data = []
    #     for donor in qs:
    #         donor_data = UserSerializer(donor).data  # كل بيانات المتبرع
    #         # كل المطابقات (match)
    #         matches = OrganMatching.objects.filter(donor=donor)
    #         donor_data['matches'] = OrganMatchingSerializer(matches, many=True).data
    #         # التنبيهات
    #         alerts = Alert.objects.filter(user=donor)
    #         donor_data['alerts'] = AlertSerializer(alerts, many=True).data
    #         data.append(donor_data)
    #     return data

    def get_donors(self, obj):
        # 1️⃣ جلب كل المتبرعين مع الـ profile
        donors_qs = obj.users.filter(role='donor').select_related('donor_profile', 'supervisor_doctor', 'hospital')

        # 2️⃣ جلب كل الـ matches مرة واحدة لكل المتبرعين
        matches_qs = OrganMatching.objects.filter(donor__in=donors_qs)

        # 3️⃣ جلب كل التنبيهات مرة واحدة
        alerts_qs = Alert.objects.filter(user__in=donors_qs)
        alerts_map = {}
        for alert in alerts_qs:
            alerts_map.setdefault(alert.user_id, []).append(alert)

        data = []

        for donor in donors_qs:
            donor_data = UserSerializer(donor).data

            # المطابقات
            donor_matches = [m for m in matches_qs if m.donor_id == donor.id]
            donor_data['matches'] = OrganMatchingSerializer(donor_matches, many=True).data

            # التنبيهات
            donor_alerts = alerts_map.get(donor.id, [])
            donor_data['alerts'] = AlertSerializer(donor_alerts, many=True).data

            data.append(donor_data)

        return data

    def get_patients_count(self, obj):
        return obj.users.filter(role='patient').count()

    def get_donors_count(self, obj):
        return obj.users.filter(role='donor').count()

    def get_total_matches(self, obj):
        # عدد كل الـ matches لجميع المرضى والمانحين في المستشفى
        return OrganMatching.objects.filter(
            patient__hospital=obj
        ).count()

    def get_scheduled_surgeries_count(self, obj):
        return Surgery.objects.filter(hospital=obj, status='مجدولة').count()

    def get_ongoing_surgeries_count(self, obj):
        return Surgery.objects.filter(hospital=obj, status='جاريه').count()

    def get_completed_surgeries_count(self, obj):
        return Surgery.objects.filter(hospital=obj, status='مكتملة').count()

    def get_under_review_surgeries_count(self, obj):
        return Surgery.objects.filter(hospital=obj, status='تحت المتابعة').count()

    def get_analysis_matches_count(self, obj):
        return OrganMatching.objects.filter(
            patient__hospital=obj,
            status='قيد التحليل'
        ).count()

    def get_review_matches_count(self, obj):
        return OrganMatching.objects.filter(
            patient__hospital=obj,
            status='تحت المراجعه'
        ).count()

    def get_matching_matches_count(self, obj):
        return OrganMatching.objects.filter(
            patient__hospital=obj,
            status='تحت المطابقه'
        ).count()

    def get_total_alerts(self, obj):
        return AlertHospital.objects.filter(hospital=obj).count()

    def get_unread_alerts(self, obj):
        return AlertHospital.objects.filter(
            hospital=obj,
            read=False
        ).count()

    def get_critical_alerts(self, obj):
        return AlertHospital.objects.filter(
            hospital=obj,
            alert_type='حرج'
        ).count()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):

        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("كلمتا المرور غير متطابقتين")

        if data["old_password"] == data["new_password"]:
            raise serializers.ValidationError("لا يمكن استخدام نفس كلمة المرور القديمة")

        return data




class MinistryRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Ministry
        fields = ['national_id', 'name', 'email', 'phone', 'password']

    def validate_national_id(self, value):
        if not value.isdigit() or len(value) != 5:
            raise serializers.ValidationError("كود الوزارة لازم يكون 5 أرقام")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")

        ministry = Ministry.objects.create(**validated_data)
        ministry.set_password(password)

        return ministry
    

class MinistryAlertSerializer(serializers.ModelSerializer):
    hospital_details = HospitalSerializer(source='sender_hospital', read_only=True)

    class Meta:
        model = MinistryAlert
        fields = [
            'id',
            'hospital_details',
            'description',
            'message',
            'message_title',
            'alert_type',
            'created_at',
            'priority',
            'read',
            'ALERT_Status',
            'sender_hospital'
        ]
