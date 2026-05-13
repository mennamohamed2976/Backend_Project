# # -*- coding: utf-8 -*-
# from django.core.management.base import BaseCommand
# from django.utils import timezone
# import random
# from faker import Faker

# from core.models import *

# fake = Faker("ar_EG")

# AR_FIRST_NAMES = ["محمد", "أحمد", "محمود", "علي", "يوسف", "عمر", "سارة", "مريم", "نور", "آية"]
# AR_LAST_NAMES = ["حسن", "إبراهيم", "عبدالله", "السيد", "خالد", "محمود", "سالم", "فتحي", "سعد", "رمضان"]

# HOSPITALS = [
#     ("مستشفى القصر العيني", "القاهرة"),
#     ("مستشفى السلام الدولي", "الجيزة"),
#     ("مستشفى عين شمس التخصصي", "القاهرة"),
#     ("مستشفى المنصورة الجامعي", "الدقهلية"),
# ]

# DISEASES = ["سكر", "ضغط", "فشل كلوي", "أمراض كبد", "ربو", "قلب"]

# class Command(BaseCommand):
#     help = "Seed Arabic fake data for all models"

#     def handle(self, *args, **options):
#         self.stdout.write("⏳ Seeding data...")

#         # =========================
#         # Hospitals
#         # =========================
#         hospitals = []
#         for name, city in HOSPITALS:
#             hospital, _ = Hospital.objects.get_or_create(
#                 name=name,
#                 defaults={
#                     "city": city,
#                     "location": fake.address(),
#                     "phone": fake.phone_number(),
#                     "emergency_phone": fake.phone_number(),
#                     "email": f"{fake.user_name()}@hospital.com",
#                     "hospital_type": random.choice(["public", "private"]),
#                 }
#             )
#             hospital.set_password("12345678")
#             hospitals.append(hospital)

#         # =========================
#         # Doctors
#         # =========================
#         doctors = []
#         for i in range(6):
#             doctor = Doctor.objects.create(
#                 name=f"د. {random.choice(AR_FIRST_NAMES)} {random.choice(AR_LAST_NAMES)}",
#                 specialty=random.choice(["جراحة", "قلب", "كلى", "كبد"]),
#                 phone=fake.phone_number(),
#                 hospital=random.choice(hospitals)
#             )
#             doctors.append(doctor)

#         # =========================
#         # Chronic Diseases
#         # =========================
#         diseases = []
#         for d in DISEASES:
#             disease, _ = ChronicDisease.objects.get_or_create(name=d)
#             diseases.append(disease)

#         # =========================
#         # Users (Patients & Donors)
#         # =========================
#         users = []
#         for i in range(20):
#             role = random.choice(["patient", "donor"])
#             national_id = f"{random.randint(10000000000000, 99999999999999)}"
#             user = User.objects.create(
#                 national_id=national_id,
#                 first_name=random.choice(AR_FIRST_NAMES),
#                 last_name=random.choice(AR_LAST_NAMES),
#                 role=role,
#                 status="approved",
#                 birthdate=fake.date_of_birth(minimum_age=18, maximum_age=65),
#                 height_cm=random.randint(150, 190),
#                 weight_kg=random.randint(50, 110),
#                 blood_type=random.choice(["A+", "A-", "B+", "O+", "O-", "AB+"]),
#                 gender=random.choice(["male", "female"]),
#                 hospital=random.choice(hospitals),
#                 supervisor_doctor=random.choice(doctors),
#             )
#             user.set_password("1234")
#             user.save()
#             users.append(user)

#             # Profile
#             if role == "patient":
#                 PatientMedicalProfile.objects.create(
#                     patient=user,
#                     organ_needed=random.choice([o.value for o in OrganType])
#                 )
#             else:
#                 DonorMedicalProfile.objects.create(
#                     donor=user,
#                     organ_available=random.choice([o.value for o in OrganType])
#                 )

#             # Chronic diseases
#             for _ in range(random.randint(0, 2)):
#                 UserChronicDisease.objects.create(
#                     user=user,
#                     disease=random.choice(diseases),
#                     severity=random.choice(["low", "medium", "high"])
#                 )

#         # =========================
#         # Appointments
#         # =========================
#         for i in range(10):
#             Appointment.objects.create(
#                 patient=random.choice(users),
#                 doctor=random.choice(doctors),
#                 hospital=random.choice(hospitals),
#                 appointment_date=timezone.now() + timezone.timedelta(days=random.randint(1, 15)),
#                 reason="كشف دوري"
#             )

#         # =========================
#         # Organ Matching + Surgery + Reports + Vitals
#         # =========================
#         patients = [u for u in users if u.role == "patient"]
#         donors = [u for u in users if u.role == "donor"]

#         for i in range(min(len(patients), len(donors))):
#             match = OrganMatching.objects.create(
#                 patient=patients[i],
#                 donor=donors[i],
#                 organ_type=random.choice([o.value for o in OrganType]),
#                 match_percentage=random.randint(40, 95),
#                 status="pending"
#             )

#             surgery = Surgery.objects.create(
#                 surgery_number=f"SURG-{i+1}",
#                 organ_matching=match,
#                 hospital=random.choice(hospitals),
#                 doctor=random.choice(doctors),
#                 scheduled_date=timezone.now() + timezone.timedelta(days=7),
#                 duration_minutes=random.randint(60, 180),
#                 operation_room=f"OR-{random.randint(1,5)}"
#             )

#             report = SurgeryReport.objects.create(
#                 surgery=surgery,
#                 result_summary="تمت العملية بنجاح",
#                 complications="لا يوجد",
#                 doctor_notes="المريض في حالة مستقرة"
#             )

#             for _ in range(3):
#                 VitalSign.objects.create(
#                     surgery_report=report,
#                     temperature_c=round(random.uniform(36.5, 38.0), 1),
#                     heart_rate=random.randint(60, 120),
#                     blood_pressure_systolic=random.randint(110, 140),
#                     blood_pressure_diastolic=random.randint(70, 90),
#                     respiratory_rate=random.randint(12, 22),
#                     oxygen_saturation=round(random.uniform(92, 99), 1),
#                 )

#         # =========================
#         # Alerts + Priorities + User Reports
#         # =========================
#         for u in users:
#             Alert.objects.create(
#                 user=u,
#                 message="تم تحديث بياناتك الطبية.",
#                 alert_type=random.choice(["info", "medical", "warning"])
#             )

#             PatientPriority.objects.get_or_create(
#                 patient=u,
#                 defaults={"score": random.randint(10, 90), "level": random.choice(["low", "medium", "high", "critical"])}
#             )

#             UserReport.objects.create(
#                 patient=u,
#                 report_type="Blood Test",
#                 description="نتيجة تحليل الدم"
#             )

#         if __name__ == "__main__":
#             print("DONE – Arabic Fake Data for ALL MODELS created")




