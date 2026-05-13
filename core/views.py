from rest_framework import viewsets, status, generics ,permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from .models import *
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db.models import Count, Q
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from .models import *
from babel.dates import format_date
from calendar import monthrange
from datetime import datetime
from dateutil.relativedelta import relativedelta

# User Registration View
class RegisterUserView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "id": user.id,
            # "national_id": user.national_id,
            # "first_name": user.first_name,
            # "last_name": user.last_name,
            "role": user.role,
            # "password": user._temp_password,
            "token": token.key,
            "message": "User registered successfully"
        }, status=status.HTTP_201_CREATED)


# register hospital
class HospitalRegisterView(generics.GenericAPIView):
    serializer_class = HospitalRegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        hospital = serializer.save()
        hospital.set_password(request.data['password'])
        hospital.save()  # مهم نحفظ الباسورد بعد التغيير

        hospital_data = {
            "id": hospital.id,
            "name": hospital.name,
            "hospital_type": hospital.hospital_type,
            "location": hospital.location,
            "license_number": hospital.license_number,
            "phone": hospital.phone,
            "emergency_phone": hospital.emergency_phone,
            "email": hospital.email,
            "working_hours": hospital.working_hours,
        }

        return Response({
            "message": "Hospital registered successfully",
            "hospital": hospital_data
        }, status=status.HTTP_201_CREATED)


# # login users and hospitals
# class UnifiedLoginView(APIView):
#     def post(self, request):
#         serializer = UnifiedLoginSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         if serializer.validated_data["type"] == "hospital":
#             hospital = serializer.validated_data["hospital"]
#             token = serializer.validated_data["token"]

#             return Response({
#                 "type": "hospital",
#                 "id": hospital.id,
#                 "name": hospital.name,
#                 "hospital_type": hospital.hospital_type,
#                 "token": token,
#                 "message": "تم تسجيل الدخول كمستشفى بنجاح"
#             })

#         else:
#             user = serializer.validated_data["user"]
#             token = serializer.validated_data["token"]

#             return Response({
#                 "type": "user",
#                 "id": user.id,
#                 "role": user.role,
#                 "token": token,
#                 "message": "تم تسجيل الدخول كمستخدم بنجاح"
#             })
class UnifiedLoginView(APIView):
    def post(self, request):
        serializer = UnifiedLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # 🔴 Ministry
        if data["type"] == "ministry":
            ministry = data["ministry"]

            return Response({
                "type": "ministry",
                "id": ministry.id,
                "name": ministry.name,
                "token": data["token"],
                "message": "تم تسجيل الدخول كوزارة بنجاح"
            })

        # 🔵 Hospital
        elif data["type"] == "hospital":
            hospital = data["hospital"]

            return Response({
                "type": "hospital",
                "id": hospital.id,
                "name": hospital.name,
                "hospital_type": hospital.hospital_type,
                "token": data["token"],
                "message": "تم تسجيل الدخول كمستشفى بنجاح"
            })

        # 🟢 User
        elif data["type"] == "user":
            user = data["user"]

            return Response({
                "type": "user",
                "id": user.id,
                "role": user.role,
                "token": data["token"],
                "message": "تم تسجيل الدخول كمستخدم بنجاح"
            })



# logout view
class LogoutUserView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, "auth_token"):
            request.user.auth_token.delete()

        return Response({"message": "Logged out successfully"})


# user viewset
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    # 🔹 إحصائيات عامة لكل users
    @action(detail=False, methods=['get'])
    def stats(self, request):
        stats = User.objects.aggregate(
            total_users=Count('id'),
            patients_count=Count('id', filter=Q(role='patient')),
            donors_count=Count('id', filter=Q(role='donor')),
        )
        return Response(stats)

    # 🔹 إحصائيات حسب مستشفى
    @action(detail=False, methods=['get'])
    def stats_by_hospital(self, request):
        hospital_id = request.query_params.get('hospital')
        qs = User.objects.all()
        if hospital_id:
            qs = qs.filter(hospital_id=hospital_id)

        return Response({
            "total_users": qs.count(),
            "patients": qs.filter(role='patient').count(),
            "donors": qs.filter(role='donor').count(),
        })

    # 🔹 كل المستخدمين مع التفاصيل الكاملة (patients + donors)
    @action(detail=False, methods=['get'])
    def stats_all(self, request):
        patients_qs = User.objects.filter(role='patient')
        donors_qs = User.objects.filter(role='donor')

        # استخدام UserSerializer اللي فيه كل بيانات profile
        patients_data = UserSerializer(patients_qs, many=True).data
        donors_data = UserSerializer(donors_qs, many=True).data

        return Response({
            "total_patients": patients_qs.count(),
            "total_donors": donors_qs.count(),
            "patients": patients_data,
            "donors": donors_data
        })


class PatientMedicalProfileListView(generics.ListAPIView):
    queryset = PatientMedicalProfile.objects.all()
    serializer_class = PatientMedicalProfileSerializer


class DonorMedicalProfileListView(generics.ListAPIView):
    queryset = DonorMedicalProfile.objects.all()
    serializer_class = DonorMedicalProfileSerializer


class PatientMedicalProfileViewSet(viewsets.ModelViewSet):
    queryset = PatientMedicalProfile.objects.all()
    serializer_class = PatientMedicalProfileSerializer


class DonorMedicalProfileViewSet(viewsets.ModelViewSet):
    queryset = DonorMedicalProfile.objects.all()
    serializer_class = DonorMedicalProfileSerializer


class HospitalViewSet(viewsets.ModelViewSet):
    queryset = Hospital.objects.all()
    serializer_class = HospitalFullSerializer


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        hospital_id = self.request.query_params.get("hospital")
        if hospital_id:
            queryset = queryset.filter(hospital_id=hospital_id)
        return queryset


class ChronicDiseaseViewSet(viewsets.ModelViewSet):
    queryset = ChronicDisease.objects.all()
    serializer_class = ChronicDiseaseSerializer


class UserChronicDiseaseViewSet(viewsets.ModelViewSet):
    queryset = UserChronicDisease.objects.all()
    serializer_class = UserChronicDiseaseSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer

    def perform_create(self, serializer):
        doctor = serializer.validated_data.get('doctor')
        hospital = serializer.validated_data.get('hospital')
        if doctor and hospital and doctor.hospital != hospital:
            raise ValidationError("Doctor must belong to selected hospital")
        serializer.save()


class OrganMatchingViewSet(viewsets.ModelViewSet):
    queryset = OrganMatching.objects.all()
    serializer_class = OrganMatchingSerializer

    @action(detail=False, methods=['post'])
    def auto_match(self, request):
        patients = User.objects.filter(role='patient', status='جاهز')
        all_matches = []
        for patient in patients:
            donors = User.objects.filter(role='donor', status='جاهز')

        for patient in patients:
            for donor in donors:
                result = OrganMatching.calculate_match(patient, donor)

                match, created = OrganMatching.objects.update_or_create(
                    patient=patient,
                    donor=donor,
                    defaults={
                        "organ_type": getattr(patient.patient_profile, 'organ_needed', 'N/A'),
                        "match_percentage": result['match_percentage'],
                        "ai_result": result['ai_result'],
                        "status": " قيد التحليل "
                    }
                )
                all_matches.append({
                    "patient": str(patient),
                    "donor": str(donor),
                    "organ_type": getattr(patient.patient_profile, 'organ_needed', 'N/A'),
                    "match_percentage": result['match_percentage']
                })
        return Response(all_matches)


class SurgeryViewSet(viewsets.ModelViewSet):
    queryset = Surgery.objects.all()
    serializer_class = SurgerySerializer


class MRIReportViewSet(viewsets.ModelViewSet):
    queryset = MRIReport.objects.all()
    serializer_class = MRIReportSerializer


# class UserReportViewSet(viewsets.ModelViewSet):
#     queryset = UserReport.objects.all()
#     serializer_class = UserReportSerializer
#
#     def get_queryset(self):
#         user = getattr(self.request, 'user', None)
#         if user and not user.is_anonymous:
#             return UserReport.objects.filter(patient=user).order_by('-created_at')
#
#         return UserReport.objects.none()
#
#     def perform_create(self, serializer):
#         user = self.request.user
#
#         if user.is_anonymous:
#             raise ValidationError("Authentication required")
#
#         serializer.save(patient=user)
#


class SurgeryReportViewSet(viewsets.ModelViewSet):
    queryset = SurgeryReport.objects.select_related(
        'surgery__organ_matching__patient',
        'surgery__doctor',
        'surgery__hospital'
    )
    serializer_class = SurgeryReportSerializer

    def perform_create(self, serializer):
        report = serializer.save()

        # 🔔 Alert للمريض
        patient = report.surgery.organ_matching.patient
        Alert.objects.create(
            user=patient,
            message=f"تم إضافة تقرير العملية الجراحية الخاصة بك: {report.surgery.surgery_number}",
            alert_type='طبي'
        )

        # 🔔 Alert للمستشفى
        hospital = getattr(report.surgery, "hospital", None)
        if hospital:
            AlertHospital.objects.create(
                hospital=hospital,
                message=f"تم إضافة تقرير عملية {report.surgery.surgery_number}.",
                alert_type='معلومة'
            )

        # 📊 تحديث أولوية المريض
        priority, created = PatientPriority.objects.get_or_create(patient=patient)
        priority.score += 10
        if priority.score >= 80:
            priority.level = 'حرجة جداً'
        elif priority.score >= 50:
            priority.level = 'اولوليه عاليه'
        elif priority.score >= 20:
            priority.level = 'اولوليه متوسطة'
        else:
            priority.level = 'اولوليه منخفضه'
        priority.save()


class PatientPriorityViewSet(viewsets.ModelViewSet):
    queryset = PatientPriority.objects.all()
    serializer_class = PatientPrioritySerializer

    @action(detail=False, methods=['post'])
    def calculate_priority(self, request):
        patients = User.objects.filter(role='patient')
        results = []
        for patient in patients:
            score = 0
            if patient.chronic_diseases.exists():
                score += patient.chronic_diseases.count() * 10
            if hasattr(patient, 'patient_profile') and patient.patient_profile.organ_needed:
                score += 20

            # تحديد المستوى
            level = 'low'
            if score >= 50:
                level = 'critical'
            elif score >= 30:
                level = 'high'
            elif score >= 10:
                level = 'medium'

            # حفظ أو تحديث
            priority, _ = PatientPriority.objects.update_or_create(
                patient=patient,
                defaults={'score': score, 'level': level}
            )

            results.append({
                "patient": str(patient),
                "score": score,
                "level": level
            })

        return Response(results)


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).order_by('-created_at')  # مؤقتًا بدون auth

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        alert = self.get_object()
        alert.read = True
        alert.save()
        return Response({"detail": "Alert marked as read"})


class HospitalAlertViewSet(viewsets.ModelViewSet):
    queryset = AlertHospital.objects.all()
    serializer_class = AlertHospitalSerializer

    def get_queryset(self):
        return AlertHospital.objects.all().order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        alert = self.get_object()
        alert.read = True
        alert.save()
        return Response({"detail": "Alert marked as read"})


class AllergyViewSet(viewsets.ModelViewSet):
    queryset = Allergy.objects.all()
    serializer_class = AllergySerializer


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get('user')
        qs = super().get_queryset()
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


class HospitalTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token_key = auth_header.split(" ")[1]

        try:
            token = HospitalToken.objects.get(key=token_key)
        except HospitalToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("توكن المستشفى غير صالح")

        return (token.hospital, token)



class ChangeHospitalPasswordView(APIView):
    authentication_classes = [HospitalTokenAuthentication]

    def post(self, request):

        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            hospital = request.user
            old_pass = serializer.validated_data["old_password"]
            new_pass = serializer.validated_data["new_password"]

            if not hospital.check_password(old_pass):
                return Response(
                    {"error": "كلمة السر القديمة غير صحيحة"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            hospital.set_password(new_pass)
            hospital.save()
            return Response({"message": "تم تغيير كلمة السر بنجاح"})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UserReportViewSet(viewsets.ModelViewSet):
    queryset = UserReport.objects.all()
    serializer_class = UserReportSerializer
    authentication_classes = [HospitalTokenAuthentication]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            hospital = request.user
            patient = serializer.validated_data.get("patient")

            # التأكد أن المستخدم تابع لنفس المستشفى
            if patient.hospital != hospital:
                return Response(
                    {"message": "هذا المستخدم لا يتبع هذه المستشفى"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer.save(hospital=hospital)

            return Response(
                {
                    "message": "تم إنشاء التقرير بنجاح",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            {
                "message": "فشل إنشاء التقرير",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )






class PatientSearchViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        return User.objects.filter(role='patient')

    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(medical_record_number__icontains=search)
            )

        organ = request.query_params.get('organ')
        if organ and organ.lower() != 'all':
            queryset = queryset.filter(patient_profile__organ_needed__icontains=organ)

        status = request.query_params.get('status')
        if status and status.lower() != 'all':
            queryset = queryset.filter(status=status)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class DonorSearchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role='donor')
    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # فلترة بالبحث (input)
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(medical_record_number__icontains=search)
            )

        organ = request.query_params.get('organ')
        if organ and organ.lower() != 'all':
            queryset = queryset.filter(donor_profile__organ_available__icontains=organ)

        status = request.query_params.get('status')
        if status and status.lower() != 'all':
            queryset = queryset.filter(status=status)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class HospitalSearchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Hospital.objects.all()
    serializer_class = HospitalFullSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # البحث بالكلمة المفتاحية
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(hospital_type__icontains=search) |
                Q(location__icontains=search)
            )

        # ممكن تضيفي فلترة إضافية لو حابة (مثلاً حسب الحالة)
        status = request.query_params.get('status')
        if status and status.lower() != 'all':
            queryset = queryset.filter(status=status)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MinistryRegisterView(generics.CreateAPIView):
    serializer_class = MinistryRegisterSerializer

    def create(self, request, *args, **kwargs):
        if Ministry.objects.exists():
            return Response(
                {"message": "يوجد وزارة بالفعل"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ministry = serializer.save()

        return Response({
            "id": ministry.id,
            "name": ministry.name,
            "message": "تم تسجيل الوزارة بنجاح"
        }, status=status.HTTP_201_CREATED)
    



# class MinistryDashboardViewSet(viewsets.ViewSet):

#     def list(self, request):
#         total_hospitals = Hospital.objects.count()
#         total_patients = User.objects.filter(role='patient').count()
#         total_donors = User.objects.filter(role='donor').count()
#         total_surgeries = Surgery.objects.count()
#         successful_surgeries = Surgery.objects.filter(status='مكتملة').count()

#         return Response({
#             "total_hospitals": total_hospitals,
#             "total_patients": total_patients,
#             "total_donors": total_donors,
#             "total_surgeries": total_surgeries,
#             "successful_surgeries": successful_surgeries
#         })
    
#     @action(detail=False, methods=['get'])
#     def surgery_organ_stats(self, request):

#         total_operations = Surgery.objects.count()
#         total_successful = Surgery.objects.filter(status='مكتملة').count()

#         # عدد العمليات لكل عضو
#         organ_operations = Surgery.objects.values('organ_matching__organ_type') \
#             .annotate(count=Count('id'))

#         organ_data = []
#         for item in organ_operations:
#             organ_name = item['organ_matching__organ_type']
#             percentage = (item['count'] / total_operations) * 100 if total_operations > 0 else 0
#             successful_count = Surgery.objects.filter(
#                 organ_matching__organ_type=organ_name, status='مكتملة'
#             ).count()
#             success_percentage = (successful_count / item['count']) * 100 if item['count'] > 0 else 0

#             organ_data.append({
#                 "organ": organ_name,
#                 "count": item['count'],
#                 "percentage": round(percentage, 2),
#                 "successful_count": successful_count,
#                 "success_percentage": round(success_percentage, 2)
#             })

#         return Response({
#             "total_operations": total_operations,
#             "total_successful": total_successful,
#             "organs": organ_data
#         })
    


# from rest_framework import viewsets
# from rest_framework.response import Response
# from django.db.models import Count, Q


from django.db.models.functions import TruncMonth

# class MinistryDashboardViewSet(viewsets.ViewSet):

#     def list(self, request):
#         total_hospitals = Hospital.objects.count()
#         total_patients = User.objects.filter(role='patient').count()
#         total_donors = User.objects.filter(role='donor').count()
#         total_surgeries = Surgery.objects.count()
#         successful_surgeries = Surgery.objects.filter(status='مكتملة').count()

#         # بيانات كل مستشفى
#         hospitals = Hospital.objects.all()
#         alerts_qs = MinistryAlert.objects.all().order_by('-created_at')

#         ministry_alerts_data = [
#             {
#                 "id": a.id,
#                 "message_title": a.message_title,
#                 "message": a.message,
#                 "alert_type": a.alert_type,
#                 "priority": a.priority,
#                 "read": a.read,
#                 "status": a.ALERT_Status,
#                 "created_at": a.created_at.strftime('%Y-%m-%d'),
#                 "hospital": a.sender_hospital.name if a.sender_hospital else None
#             }
#             for a in alerts_qs
#         ]

        
#         alerts_stats = {
#             "total_alerts": alerts_qs.count(),
#             "unread_alerts": alerts_qs.filter(read=False).count(),
#             "under_investigation": alerts_qs.filter(ALERT_Status="قيد التحقيق").count(),
#             "resolved_alerts": alerts_qs.filter(alert_type='تم الحل').count(),
#         }




# # بيانات كل مستشفى
#         hospitals_data = []
#         for h in hospitals:
#             # 🔔 إشعارات الوزارة
#             # التنبيهات الخاصة بالمستشفى
#             alerts_qs = AlertHospital.objects.filter(hospital=h).order_by('-created_at')
#             alerts_data = [
#                 {
#                     "id": a.id,
#                     "message": a.message,
#                     "message_title": a.message_title,
#                     "alert_type": a.alert_type,
#                     "read": a.read,
#                     "created_at": a.created_at.strftime('%Y-%m-%d %H:%M:%S')
#                 }
#                 for a in alerts_qs
#             ]
           
#             surgeries_qs = Surgery.objects.filter(hospital=h)
#             surgeries_list = [
#                 {
#                     "id": s.id,
#                     "surgery_number": s.surgery_number,
#                     "surgery_name": s.surgery_name,
#                     "organ_type": s.organ_matching.organ_type if s.organ_matching else None,
#                     "status": s.status,
#                     "scheduled_date": s.scheduled_date,
#                     "scheduled_time": s.scheduled_time,
#                     "created_at": s.created_at.strftime('%Y-%m-%d'),
#                     "patient_name": str(s.organ_matching.patient) if s.organ_matching else None,
#                     "birthdate": s.organ_matching.patient.birthdate.strftime('%Y-%m-%d') if s.organ_matching and s.organ_matching.patient.birthdate else None
#                 }
#                 for s in surgeries_qs
#             ]
            

#             patients_count = User.objects.filter(role='patient', hospital=h).count()
#             donors_count = User.objects.filter(role='donor', hospital=h).count()

#             # العمليات في المستشفى
#             surgeries_count = Surgery.objects.filter(hospital=h).count()
#             successful_surgeries_count = Surgery.objects.filter(hospital=h, status='مكتملة').count()

#             # عدد الأعضاء المطلوبة لكل مستشفى مع اسم العضو وعدده
#             organs_needed = Surgery.objects.filter(
#                 hospital=h,
#                 organ_matching__isnull=False
#             ).values('organ_matching__organ_type') \
#             .annotate(count=Count('organ_matching__organ_type')) \
#             .order_by('-count')

#             organs_needed_list = [
#                 {"organ": o['organ_matching__organ_type'], "count": o['count']}
#                 for o in organs_needed
#             ]

#             hospitals_data.append({
#                 "id": h.id,
#                 "name": h.name,
#                 "location": h.location,
#                 "hospital_type": h.hospital_type,
#                 "status": h.status,
#                 "phone": h.phone,
#                 "email": h.email,
#                 "patients_count": patients_count,
#                 "donors_count": donors_count,
#                 "total_surgeries": surgeries_count,
#                 "successful_surgeries": successful_surgeries_count,
#                 "success_percentage": round((successful_surgeries_count / surgeries_count) * 100, 2) if surgeries_count > 0 else 0,
#                 "organs_needed": organs_needed_list,
#                 "hospital_alerts": alerts_data,
#                 "surgeries": surgeries_list,
#             })
#             hospitals_data.sort(key=lambda x: x['patients_count'], reverse=True)

#             # إضافة حقل الترتيب لكل مستشفى
#             for index, h_data in enumerate(hospitals_data, start=1):
#                 h_data['rank'] = index


#         # # البيانات السابقة (عمليات، نسب نجاح، ... )
#         organ_operations = Surgery.objects.values('organ_matching__organ_type') \
#             .annotate(count=Count('id'))

#         organ_data = []
#         for item in organ_operations:
#             organ_name = item['organ_matching__organ_type']
#             percentage = (item['count'] / total_surgeries) * 100 if total_surgeries > 0 else 0
#             successful_count = Surgery.objects.filter(
#                 organ_matching__organ_type=organ_name, status='مكتملة'
#             ).count()
#             success_percentage = (successful_count / item['count']) * 100 if item['count'] > 0 else 0
#             organ_data.append({
#                 "organ": organ_name,
#                 "count": item['count'],
#                 "percentage": round(percentage, 2),
#                 "successful_count": successful_count,
#                 "success_percentage": round(success_percentage, 2)
#             })

#         # إحصائيات شهرية
#         monthly_stats = Surgery.objects.annotate(month=TruncMonth('created_at')) \
#             .values('month') \
#             .annotate(
#                 total=Count('id'),
#                 successful=Count('id', filter=Q(status='مكتملة'))
#             ).order_by('month')

#         monthly_data = []
#         for stat in monthly_stats:
#             total = stat['total']
#             successful = stat['successful']
#             monthly_data.append({
#                 "month": format_date(stat['month'], format='MMMM', locale='ar'),
#                 "total_surgeries": total,
#                 "successful_surgeries": successful,
#                 "success_percentage": round((successful / total) * 100, 2) if total > 0 else 0
#             })

#         return Response({
#             "total_hospitals": total_hospitals,
#             "total_patients": total_patients,
#             "total_donors": total_donors,
#             "total_surgeries": total_surgeries,
#             "successful_surgeries": successful_surgeries,
#             "hospitals": hospitals_data,
#             "organs_stats": organ_data,
#             "monthly_surgery_stats": monthly_data,
#             "ministry_alerts": ministry_alerts_data,
#             "alerts_statistics": alerts_stats,
#         })


# from django.shortcuts import get_object_or_404
# class MinistryDashboardViewSet(viewsets.ViewSet):

#     def list(self, request):
#         alert_id = request.query_params.get('alert')
    
#     # 🔴 حالة Alert واحد
#         if alert_id:
#             a = get_object_or_404(AlertHospital, id=alert_id)

#             return Response({
#             "id": a.id,
#             "message": a.message,
#             "message_title": a.message_title,
#             "alert_type": a.alert_type,
#             "read": a.read,
#             "created_at": a.created_at.strftime('%Y-%m-%d %H:%M:%S'),
#             "hospital": {
#                 "id": a.hospital.id if a.hospital else None,
#                 "name": a.hospital.name if a.hospital else None
#             }
#         })
#         hospital_id = request.query_params.get('hospital')

#         # 🟦 HOSPITAL DETAILS
#         if hospital_id:
#             h = get_object_or_404(Hospital, id=hospital_id)

#             # 🔔 Alerts
#             alerts_qs = AlertHospital.objects.filter(hospital=h).order_by('-created_at')

#             # 🏥 Surgeries
#             surgeries_qs = Surgery.objects.filter(hospital=h)

#             # 👥 counts
#             patients_count = User.objects.filter(role='patient', hospital=h).count()
#             donors_count = User.objects.filter(role='donor', hospital=h).count()

#             total_surgeries = surgeries_qs.count()
#             successful_surgeries = surgeries_qs.filter(status='مكتملة').count()

#             success_percentage = (
#                 round((successful_surgeries / total_surgeries) * 100, 2)
#                 if total_surgeries > 0 else 0
#             )

#             # 🧠 ORGANS NEEDED
#             all_organs = [choice[0] for choice in OrganType.choices]

#             organs_stats = Surgery.objects.filter(
#                 hospital=h,
#                 organ_matching__isnull=False
#             ).values('organ_matching__organ_type') \
#              .annotate(count=Count('id'))

#             organs_dict = {
#                 o['organ_matching__organ_type']: o['count']
#                 for o in organs_stats
#             }

#             organs_needed = [
#                 {
#                     "organ": organ,
#                     "count": organs_dict.get(organ, 0)
#                 }
#                 for organ in all_organs
#             ]

#             # 📦 RESPONSE
#             return Response({
#                 "id": h.id,
#                 "name": h.name,
#                 "location": h.location,
#                 "hospital_type": h.hospital_type,
#                 "status": h.status,
#                 "phone": h.phone,
#                 "email": h.email,

#                 "patients_count": patients_count,
#                 "donors_count": donors_count,

#                 "total_surgeries": total_surgeries,
#                 "successful_surgeries": successful_surgeries,
#                 "success_percentage": success_percentage,

#                 # 🔔 alerts
#                 "alerts": [
#                     {
#                         "id": a.id,
#                         "message": a.message,
#                         "message_title": a.message_title,
#                         "alert_type": a.alert_type,
#                         "read": a.read,
#                         "created_at": a.created_at.strftime('%Y-%m-%d %H:%M:%S')
#                     }
#                     for a in alerts_qs
#                 ],

#                 # 🏥 surgeries
#                 "surgeries": [
#                     {
#                         "id": s.id,
#                         "surgery_number": s.surgery_number,
#                         "surgery_name": s.surgery_name,
#                         "status": s.status,
#                         "organ_type": s.organ_matching.organ_type if s.organ_matching else None,
#                         "scheduled_date": s.scheduled_date,
#                         "scheduled_time": s.scheduled_time,
#                         "created_at": s.created_at.strftime('%Y-%m-%d'),
#                         "patient_name": str(s.organ_matching.patient) if s.organ_matching else None,
#                         "birthdate": s.organ_matching.patient.birthdate.strftime('%Y-%m-%d') if s.organ_matching and s.organ_matching.patient.birthdate else None
#                     }
#                     for s in surgeries_qs
#                 ],

#                 # 🧠 organs needed
#                 "organs_needed": organs_needed,
#             })


#         total_hospitals = Hospital.objects.count()
#         total_patients = User.objects.filter(role='patient').count()
#         total_donors = User.objects.filter(role='donor').count()
#         total_surgeries = Surgery.objects.count()
#         successful_surgeries = Surgery.objects.filter(status='مكتملة').count()

#         # بيانات كل مستشفى
#         hospitals = Hospital.objects.all()
#         alerts_qs = MinistryAlert.objects.all().order_by('-created_at')

#         ministry_alerts_data = [
#             {
#                 "id": a.id,
#                 "message_title": a.message_title,
#                 "message": a.message,
#                 "alert_type": a.alert_type,
#                 "priority": a.priority,
#                 "read": a.read,
#                 "status": a.ALERT_Status,
#                 "created_at": a.created_at.strftime('%Y-%m-%d'),
#                 "hospital": a.sender_hospital.name if a.sender_hospital else None
#             }
#             for a in alerts_qs
#         ]

        
#         alerts_stats = {
#             "total_alerts": alerts_qs.count(),
#             "unread_alerts": alerts_qs.filter(read=False).count(),
#             "under_investigation": alerts_qs.filter(ALERT_Status="قيد التحقيق").count(),
#             "resolved_alerts": alerts_qs.filter(alert_type='تم الحل').count(),
#         }




# # بيانات كل مستشفى
#         hospitals_data = []
#         for h in hospitals:
#             # 🔔 إشعارات الوزارة
#             # التنبيهات الخاصة بالمستشفى
#             alerts_qs = AlertHospital.objects.filter(hospital=h).order_by('-created_at')
#             alerts_data = [
#                 {
#                     "id": a.id,
#                     "message": a.message,
#                     "message_title": a.message_title,
#                     "alert_type": a.alert_type,
#                     "read": a.read,
#                     "created_at": a.created_at.strftime('%Y-%m-%d %H:%M:%S')
#                 }
#                 for a in alerts_qs
#             ]
           
#             surgeries_qs = Surgery.objects.filter(hospital=h)
#             surgeries_list = [
#                 {
#                     "id": s.id,
#                     "surgery_number": s.surgery_number,
#                     "surgery_name": s.surgery_name,
#                     "organ_type": s.organ_matching.organ_type if s.organ_matching else None,
#                     "status": s.status,
#                     "scheduled_date": s.scheduled_date,
#                     "scheduled_time": s.scheduled_time,
#                     "created_at": s.created_at.strftime('%Y-%m-%d'),
#                     "patient_name": str(s.organ_matching.patient) if s.organ_matching else None,
#                     "birthdate": s.organ_matching.patient.birthdate.strftime('%Y-%m-%d') if s.organ_matching and s.organ_matching.patient.birthdate else None
#                 }
#                 for s in surgeries_qs
#             ]
            

#             patients_count = User.objects.filter(role='patient', hospital=h).count()
#             donors_count = User.objects.filter(role='donor', hospital=h).count()

#             # العمليات في المستشفى
#             surgeries_count = Surgery.objects.filter(hospital=h).count()
#             successful_surgeries_count = Surgery.objects.filter(hospital=h, status='مكتملة').count()

#             # كل أنواع الأعضاء من الـ choices
#             all_organs = [choice[0] for choice in OrganType.choices]

#             # بيانات من الداتابيز
#             organs_needed = Surgery.objects.filter(
#                 hospital=h,
#                 organ_matching__isnull=False
#             ).values('organ_matching__organ_type') \
#             .annotate(count=Count('organ_matching__organ_type'))

#             # نحولها dict
#             organs_dict = {
#                 o['organ_matching__organ_type']: o['count']
#                 for o in organs_needed
#             }

#             # نضمن إن كل الأعضاء موجودة
#             organs_needed_list = [
#                 {
#                     "organ": organ,
#                     "count": organs_dict.get(organ, 0)  # 👈 لو مش موجود = 0
#                 }
#                 for organ in all_organs
#             ]

#             hospitals_data.append({
#                 "id": h.id,
#                 "name": h.name,
#                 "location": h.location,
#                 "hospital_type": h.hospital_type,
#                 "status": h.status,
#                 "phone": h.phone,
#                 "email": h.email,
#                 "patients_count": patients_count,
#                 "donors_count": donors_count,
#                 "total_surgeries": surgeries_count,
#                 "successful_surgeries": successful_surgeries_count,
#                 "success_percentage": round((successful_surgeries_count / surgeries_count) * 100, 2) if surgeries_count > 0 else 0,
#                 "organs_needed": organs_needed_list,
#                 "hospital_alerts": alerts_data,
#                 "surgeries": surgeries_list,
#             })
#             hospitals_data.sort(key=lambda x: x['patients_count'], reverse=True)

#             # إضافة حقل الترتيب لكل مستشفى
#             for index, h_data in enumerate(hospitals_data, start=1):
#                 h_data['rank'] = index


#         all_organs = [choice[0] for choice in OrganType.choices]

#         organ_data = []

#         for organ in all_organs:
#             count = Surgery.objects.filter(
#                 organ_matching__organ_type=organ
#             ).count()

#             successful_count = Surgery.objects.filter(
#                 organ_matching__organ_type=organ,
#                 status='مكتملة'
#             ).count()

#             percentage = (
#                 (count / total_surgeries) * 100
#                 if total_surgeries > 0 else 0
#             )

#             success_percentage = (
#                 (successful_count / count) * 100
#                 if count > 0 else 0
#             )

#             organ_data.append({
#                 "organ": organ,
#                 "count": count,
#                 "percentage": round(percentage, 2),
#                 "successful_count": successful_count,
#                 "success_percentage": round(success_percentage, 2)
#             })

#         now = datetime.now()

#         # 🟢 بداية آخر 6 شهور
#         start_date = (now - relativedelta(months=5)).replace(day=1)

#         # 📊 بيانات من الداتابيز
#         monthly_stats = Surgery.objects.filter(created_at__gte=start_date) \
#             .annotate(month=TruncMonth('created_at')) \
#             .values('month') \
#             .annotate(
#                 total=Count('id'),
#                 successful=Count('id', filter=Q(status='مكتملة'))
#             )

#         # نحولها dict (year, month)
#         stats_dict = {
#             (stat['month'].year, stat['month'].month): stat
#             for stat in monthly_stats
#         }

#         # 📅 نلف على آخر 6 شهور
#         monthly_data = []

#         for i in range(6):
#             current = start_date + relativedelta(months=i)
#             key = (current.year, current.month)

#             stat = stats_dict.get(key)

#             if stat:
#                 total = stat['total']
#                 successful = stat['successful']
#             else:
#                 total = 0
#                 successful = 0

#             monthly_data.append({
#                 "month": format_date(current, format='MMMM', locale='ar'),
#                 "year": current.year,
#                 "month_number": current.month,
#                 "total_surgeries": total,
#                 "successful_surgeries": successful,
#                 "success_percentage": round((successful / total) * 100, 2) if total > 0 else 0
#             })


#         return Response({
#             "total_hospitals": total_hospitals,
#             "total_patients": total_patients,
#             "total_donors": total_donors,
#             "total_surgeries": total_surgeries,
#             "successful_surgeries": successful_surgeries,
#             "hospitals": hospitals_data,
#             "organs_stats": organ_data,
#             "monthly_surgery_stats": monthly_data,
#             "ministry_alerts": ministry_alerts_data,
#             "alerts_statistics": alerts_stats,
#         })
from django.shortcuts import get_object_or_404
class MinistryDashboardViewSet(viewsets.ViewSet):

    def list(self, request):
        alert_id = request.query_params.get('alert')
    
    # 🔴 حالة Alert واحد
        if alert_id:
            a = get_object_or_404(MinistryAlert, id=alert_id)

            return Response({
            "id": a.id,
            "message": a.message,
            "message_title": a.message_title,
            "alert_type": a.alert_type,
            "ALERT_Status": a.ALERT_Status,
            "priority": a.priority,
            "read": a.read,
            "description": a.description,
            "created_at": a.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "sender_hospital": {
                "id": a.sender_hospital.id if a.sender_hospital else None,
                "name": a.sender_hospital.name if a.sender_hospital else None
            }
        })
        hospital_id = request.query_params.get('hospital')

        # 🟦 HOSPITAL DETAILS
        if hospital_id:
            h = get_object_or_404(Hospital, id=hospital_id)

            # 🔔 Alerts
            alerts_qs = AlertHospital.objects.filter(hospital=h).order_by('-created_at')
            

            # 🏥 Surgeries
            surgeries_qs = Surgery.objects.filter(hospital=h)

            # 👥 counts
            patients_count = User.objects.filter(role='patient', hospital=h).count()
            donors_count = User.objects.filter(role='donor', hospital=h).count()

            total_surgeries = surgeries_qs.count()
            successful_surgeries = surgeries_qs.filter(status='مكتملة').count()

            success_percentage = (
                round((successful_surgeries / total_surgeries) * 100, 2)
                if total_surgeries > 0 else 0
            )
            # ✅ آخر 3 عمليات ناجحة لكل مستشفى
            latest_successful_qs = Surgery.objects.filter(
                hospital=h,
                 status__in=['تمت بنجاح', 'فشلت']
            ).order_by('-created_at')[:3]

            if not latest_successful_qs.exists():
                latest_successful = "مفيش عمليات ناجحة"
            else:
                latest_successful = [
                    {
                        "id": s.id,
                        "surgery_number": s.surgery_number,
                        "surgery_name": s.surgery_name,
                        "doctor": str(s.doctor) if s.doctor else None,
                        "organ_type": s.organ_matching.organ_type if s.organ_matching else None,
                        "scheduled_date": s.scheduled_date,
                        "status": s.status,
                        "patient_name": (
                            f"{s.organ_matching.patient.first_name} {s.organ_matching.patient.last_name}"
                            if s.organ_matching and s.organ_matching.patient else None
                        ),
                        "birthdate": s.organ_matching.patient.birthdate.strftime('%Y-%m-%d') 
                            if s.organ_matching and s.organ_matching.patient.birthdate else None,
                        "created_at": s.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    }
                    for s in latest_successful_qs
                ]
            

            # 🧠 ORGANS NEEDED
            all_organs = [choice[0] for choice in OrganType.choices]

            organs_stats = Surgery.objects.filter(
                hospital=h,
                organ_matching__isnull=False
            ).values('organ_matching__organ_type') \
             .annotate(count=Count('id'))

            organs_dict = {
                o['organ_matching__organ_type']: o['count']
                for o in organs_stats
            }

            organs_needed = [
                {
                    "organ": organ,
                    "count": organs_dict.get(organ, 0)
                }
                for organ in all_organs
            ]

            # 📦 RESPONSE
            return Response({
                "id": h.id,
                "name": h.name,
                "location": h.location,
                "hospital_type": h.hospital_type,
                "status": h.status,
                "phone": h.phone,
                "email": h.email,
                "patients_count": patients_count,
                "donors_count": donors_count,
                "total_surgeries": total_surgeries,
                "successful_surgeries": successful_surgeries,
                "success_percentage": success_percentage,
                "latest_successful_surgeries": latest_successful,

                # 🔔 alerts
                "alerts": [
                    {
                        "id": a.id,
                        "message": a.message,
                        "message_title": a.message_title,
                        "alert_type": a.alert_type,
                        "read": a.read,
                        "created_at": a.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    for a in alerts_qs
                ],

                # 🏥 surgeries
                "surgeries": [
                    {
                        "id": s.id,
                        "surgery_number": s.surgery_number,
                        "surgery_name": s.surgery_name,
                        "status": s.status,
                        "organ_type": s.organ_matching.organ_type if s.organ_matching else None,
                        "scheduled_date": s.scheduled_date,
                        "scheduled_time": s.scheduled_time,
                        "created_at": s.created_at.strftime('%Y-%m-%d'),
                        "patient_name": (
                            f"{s.organ_matching.patient.first_name} {s.organ_matching.patient.last_name}"
                            if s.organ_matching and s.organ_matching.patient else None
                        ),
                        "birthdate": s.organ_matching.patient.birthdate.strftime('%Y-%m-%d') if s.organ_matching and s.organ_matching.patient.birthdate else None
                    }
                    for s in surgeries_qs
                ],

                # 🧠 organs needed
                "organs_needed": organs_needed,
            })


        total_hospitals = Hospital.objects.count()
        total_patients = User.objects.filter(role='patient').count()
        total_donors = User.objects.filter(role='donor').count()
        total_surgeries = Surgery.objects.count()
        successful_surgeries = Surgery.objects.filter(status='مكتملة').count()

        # بيانات كل مستشفى
        hospitals = Hospital.objects.all()
        alerts_qs = MinistryAlert.objects.all().order_by('-created_at')

        ministry_alerts_data = [
            {
                "id": a.id,
                "message_title": a.message_title,
                "message": a.message,
                "alert_type": a.alert_type,
                "priority": a.priority,
                "read": a.read,
                "status": a.ALERT_Status,
                "created_at": a.created_at.strftime('%Y-%m-%d'),
                "hospital": a.sender_hospital.name if a.sender_hospital else None
            }
            for a in alerts_qs
        ]

        
        alerts_stats = {
            "total_alerts": alerts_qs.count(),
            "unread_alerts": alerts_qs.filter(read=False).count(),
            "under_investigation": alerts_qs.filter(ALERT_Status="قيد التحقيق").count(),
            "resolved_alerts": alerts_qs.filter(alert_type='تم الحل').count(),
        }



        hospitals_data = []
        for h in hospitals:
            # 🔔 إشعارات الوزارة
            # التنبيهات الخاصة بالمستشفى
            alerts_qs = AlertHospital.objects.filter(hospital=h).order_by('-created_at')
            alerts_data = [
                {
                    "id": a.id,
                    "message": a.message,
                    "message_title": a.message_title,
                    "alert_type": a.alert_type,
                    "read": a.read,
                    "created_at": a.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for a in alerts_qs
            ]
           
            surgeries_qs = Surgery.objects.filter(hospital=h)
            surgeries_list = [
                {
                    "id": s.id,
                    "surgery_number": s.surgery_number,
                    "surgery_name": s.surgery_name,
                    "organ_type": s.organ_matching.organ_type if s.organ_matching else None,
                    "status": s.status,
                    "scheduled_date": s.scheduled_date,
                    "scheduled_time": s.scheduled_time,
                    "created_at": s.created_at.strftime('%Y-%m-%d'),
                    "patient_name": str(s.organ_matching.patient) if s.organ_matching else None,
                    "birthdate": s.organ_matching.patient.birthdate.strftime('%Y-%m-%d') if s.organ_matching and s.organ_matching.patient.birthdate else None
                }
                for s in surgeries_qs
            ]
            

            patients_count = User.objects.filter(role='patient', hospital=h).count()
            donors_count = User.objects.filter(role='donor', hospital=h).count()

            # العمليات في المستشفى
            surgeries_count = Surgery.objects.filter(hospital=h).count()
            successful_surgeries_count = Surgery.objects.filter(hospital=h, status='مكتملة').count()

            # كل أنواع الأعضاء من الـ choices
            all_organs = [choice[0] for choice in OrganType.choices]

            # بيانات من الداتابيز
            organs_needed = Surgery.objects.filter(
                hospital=h,
                organ_matching__isnull=False
            ).values('organ_matching__organ_type') \
            .annotate(count=Count('organ_matching__organ_type'))

            # نحولها dict
            organs_dict = {
                o['organ_matching__organ_type']: o['count']
                for o in organs_needed
            }

            # نضمن إن كل الأعضاء موجودة
            organs_needed_list = [
                {
                    "organ": organ,
                    "count": organs_dict.get(organ, 0)  # 👈 لو مش موجود = 0
                }
                for organ in all_organs
            ]

            hospitals_data.append({
                "id": h.id,
                "name": h.name,
                "location": h.location,
                "hospital_type": h.hospital_type,
                "status": h.status,
                "phone": h.phone,
                "email": h.email,
                "patients_count": patients_count,
                "donors_count": donors_count,
                "total_surgeries": surgeries_count,
                "successful_surgeries": successful_surgeries_count,
                "success_percentage": round((successful_surgeries_count / surgeries_count) * 100, 2) if surgeries_count > 0 else 0,
                "organs_needed": organs_needed_list,
                "hospital_alerts": alerts_data,
                "surgeries": surgeries_list,
                # "latest_successful_surgeries": latest_successful,
            })
            hospitals_data.sort(key=lambda x: x['patients_count'], reverse=True)

            # إضافة حقل الترتيب لكل مستشفى
            for index, h_data in enumerate(hospitals_data, start=1):
                h_data['rank'] = index


        all_organs = [choice[0] for choice in OrganType.choices]

        organ_data = []

        for organ in all_organs:
            count = Surgery.objects.filter(
                organ_matching__organ_type=organ
            ).count()

            successful_count = Surgery.objects.filter(
                organ_matching__organ_type=organ,
                status='مكتملة'
            ).count()

            percentage = (
                (count / total_surgeries) * 100
                if total_surgeries > 0 else 0
            )

            success_percentage = (
                (successful_count / count) * 100
                if count > 0 else 0
            )

            organ_data.append({
                "organ": organ,
                "count": count,
                "percentage": round(percentage, 2),
                "successful_count": successful_count,
                "success_percentage": round(success_percentage, 2)
            })

        now = datetime.now()

        # 🟢 بداية آخر 6 شهور
        start_date = (now - relativedelta(months=5)).replace(day=1)

        # 📊 بيانات من الداتابيز
        monthly_stats = Surgery.objects.filter(created_at__gte=start_date) \
            .annotate(month=TruncMonth('created_at')) \
            .values('month') \
            .annotate(
                total=Count('id'),
                successful=Count('id', filter=Q(status='مكتملة'))
            )

        # نحولها dict (year, month)
        stats_dict = {
            (stat['month'].year, stat['month'].month): stat
            for stat in monthly_stats
        }

        # 📅 نلف على آخر 6 شهور
        monthly_data = []

        for i in range(6):
            current = start_date + relativedelta(months=i)
            key = (current.year, current.month)

            stat = stats_dict.get(key)

            if stat:
                total = stat['total']
                successful = stat['successful']
            else:
                total = 0
                successful = 0

            monthly_data.append({
                "month": format_date(current, format='MMMM', locale='ar'),
                "year": current.year,
                "month_number": current.month,
                "total_surgeries": total,
                "successful_surgeries": successful,
                "success_percentage": round((successful / total) * 100, 2) if total > 0 else 0
            })


        return Response({
            "total_hospitals": total_hospitals,
            "total_patients": total_patients,
            "total_donors": total_donors,
            "total_surgeries": total_surgeries,
            "successful_surgeries": successful_surgeries,
            "hospitals": hospitals_data,
            "organs_stats": organ_data,
            "monthly_surgery_stats": monthly_data,
            "ministry_alerts": ministry_alerts_data,
            "alerts_statistics": alerts_stats,
        })

# from rest_framework.permissions import AllowAny

# class MinistryAlertViewSet(viewsets.ModelViewSet):
#     queryset = MinistryAlert.objects.all()
#     serializer_class = MinistryAlertSerializer
#     # permission_classes = [permissions.IsAuthenticated]
#     permission_classes = [AllowAny]

#     # 🔹 فلترة حسب الوزارة
#     def get_queryset(self):
#         queryset = super().get_queryset()
#         ministry_id = self.request.query_params.get('ministry_id')
#         if ministry_id:
#             queryset = queryset.filter(ministry_id=ministry_id)
#         return queryset

#     # 🔹 عند الإنشاء
#     def perform_create(self, serializer):
#         ministry = Ministry.objects.first()
    
#         user = self.request.user
    
#         if user.is_authenticated and hasattr(user, 'hospital'):
#             serializer.save(
#                 ministry=ministry,
#                 sender_hospital=user.hospital
#             )
#         else:
#             serializer.save(
#                 ministry=ministry,
#                 sender_hospital=None
#             )

#     # 🔹 Mark as Read
#     @action(detail=True, methods=['patch'])
#     def mark_as_read(self, request, pk=None):
#         alert = self.get_object()
#         alert.read = True
#         alert.save()
#         return Response({"message": "تم قراءة التنبيه"})

from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import MinistryAlert, Ministry
from .serializers import MinistryAlertSerializer


class MinistryAlertViewSet(viewsets.ModelViewSet):
    queryset = MinistryAlert.objects.all()
    serializer_class = MinistryAlertSerializer
    permission_classes = [AllowAny]

    # 🔹 فلترة حسب الوزارة
    def get_queryset(self):
        queryset = super().get_queryset()
        ministry_id = self.request.query_params.get('ministry_id')
        if ministry_id:
            queryset = queryset.filter(ministry_id=ministry_id)
        return queryset

    # 🔹 عند الإنشاء
    def perform_create(self, serializer):
        ministry = Ministry.objects.first()

        # ✅ تأكد إن فيه وزارة
        if not ministry:
            raise ValueError("لا يوجد وزارة في النظام، من فضلك أضف وزارة أولاً")

        user = self.request.user

        # ✅ لو user مسجل وعنده hospital
        if user.is_authenticated and hasattr(user, 'hospital'):
            serializer.save(
                ministry=ministry,
                sender_hospital=user.hospital
            )
        else:
            # ✅ لو anonymous
            serializer.save(
                ministry=ministry,
                sender_hospital=None
            )

    # 🔹 Mark as Read
    @action(detail=True, methods=['patch'])
    def mark_as_read(self, request, pk=None):
        alert = self.get_object()
        alert.read = True
        alert.save()
        return Response({"message": "تم قراءة التنبيه"})





class CreateMinistryAlertView(generics.CreateAPIView):
    serializer_class = MinistryAlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # هتجيب الوزارة (بما إن عندك واحدة بس)
        ministry = Ministry.objects.first()

        serializer.save(
            ministry=ministry,
            hospital=self.request.user.hospital  # لو المستخدم تابع مستشفى
        )




class SendMinistryAlertView(APIView):
    authentication_classes = [HospitalTokenAuthentication]

    def post(self, request):
        try:
            hospital = request.user
            ministry = Ministry.objects.first()

            if not ministry:
                return Response({
                    "success": False,
                    "message": "لا يوجد وزارة مسجلة"
                }, status=status.HTTP_400_BAD_REQUEST)

            data = request.data

            # validation بسيط
            if not data.get("message_title") or not data.get("message"):
                return Response({
                    "success": False,
                    "message": "العنوان والرسالة مطلوبين"
                }, status=status.HTTP_400_BAD_REQUEST)

            alert = MinistryAlert.objects.create(
                ministry=ministry,
                sender_hospital=hospital,
                message_title=data.get("message_title"),
                message=data.get("message"),
                alert_type=data.get("alert_type"),
                ALERT_Status="قيد التحقيق",
                priority=data.get("priority", "متوسطة"),
            )

            return Response({
                "success": True,
                "message": "تم إرسال الإشعار للوزارة بنجاح",
                "data": {
                    "alert_id": alert.id
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                "success": False,
                "message": "حدث خطأ أثناء إرسال الإشعار",
                "errors": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
