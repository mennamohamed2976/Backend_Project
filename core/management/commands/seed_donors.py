# # =============================================================
# # المسار: your_app/management/commands/seed_donors.py
# #
# # لو مش موجود الـ folder، اعمليه يدوياً:
# #   mkdir -p your_app/management/commands
# #   touch your_app/management/__init__.py
# #   touch your_app/management/commands/__init__.py
# #
# # تشغيل:
# #   python manage.py seed_donors --csv path/to/donors_10000_living_deceased_organs.csv
# #   python manage.py seed_donors --csv path/to/file.csv --limit 500   # لو عايزة تجربي بعدد أقل
# #   python manage.py seed_donors --csv path/to/file.csv --clear       # يمسح القديم ويبدأ من الأول
# # =============================================================

# import csv
# import random
# import string
# from datetime import date, timedelta

# from django.core.management.base import BaseCommand, CommandError
# from django.db import transaction

# # ⚠️ غيري اسم الـ app لو مختلف
# from core.models import (
#     User,
#     Hospital,
#     DonorMedicalProfile,
#     OrganType,
#     OrganPortion,
# )


# # ---------- helpers ----------

# BLOOD_MAP = {
#     'A': 'A', 'B': 'B', 'O': 'O', 'AB': 'AB',
#     'A+': 'A', 'B+': 'B', 'O+': 'O', 'AB+': 'AB',
#     'A-': 'A', 'B-': 'B', 'O-': 'O', 'AB-': 'AB',
# }

# GENDER_MAP = {
#     'M': 'ذكر',
#     'F': 'انثي',
#     'male': 'ذكر',
#     'female': 'انثي',
# }

# ORGAN_MAP = {
#     'kidney': OrganType.KIDNEY,
#     'kidney_right': OrganType.KIDNEY_RIGHT,
#     'kidney_left': OrganType.KIDNEY_LEFT,
#     'liver': OrganType.LIVER,
#     'liver_lobe': OrganType.LIVER_LOBE,
#     'heart': OrganType.HEART,
#     'lung_right': OrganType.LUNG_RIGHT,
#     'lung_lobe': OrganType.LUNG_LOBE,
#     'lung_left': OrganType.LUNG_RIGHT,       # fallback: أقرب نوع موجود في الـ model
#     'pancreas': OrganType.PANCREAS,
#     'pancreas_segment': OrganType.PANCREAS,   # fallback: segment غير مدعوم → full pancreas
# }

# # الـ organs اللي بيُقبل KDPI فيها (كل أنواع الكُلى)
# KIDNEY_ORGANS = {'kidney', 'kidney_right', 'kidney_left'}

# PORTION_MAP = {
#     'full': OrganPortion.FULL,
#     'segment': OrganPortion.SEGMENT,
#     'lobe': OrganPortion.LOBE,
# }


# def _rand_national_id():
#     """يولّد رقم قومي مصري وهمي (14 رقم)."""
#     return ''.join(random.choices(string.digits, k=14))


# def _rand_medical_record():
#     return 'MR-' + ''.join(random.choices(string.digits, k=6))


# def _age_to_birthdate(age_str):
#     """يحوّل العمر لتاريخ ميلاد تقريبي."""
#     try:
#         age = int(age_str)
#         return date.today() - timedelta(days=age * 365)
#     except (ValueError, TypeError):
#         return date(1990, 1, 1)


# def _parse_float(val):
#     try:
#         return float(val) if val and val.strip() else None
#     except ValueError:
#         return None


# def _parse_int(val):
#     try:
#         return int(float(val)) if val and val.strip() else None
#     except ValueError:
#         return None


# def _parse_bool(val):
#     return val.strip().lower() == 'positive' if val else False


# # ---------- Command ----------

# class Command(BaseCommand):
#     help = 'Seed the database with donors from the CSV dataset'

#     def add_arguments(self, parser):
#         parser.add_argument(
#             '--csv',
#             type=str,
#             required=True,
#             help='Full path to donors CSV file',
#         )
#         parser.add_argument(
#             '--limit',
#             type=int,
#             default=None,
#             help='Max number of rows to import (default: all)',
#         )
#         parser.add_argument(
#             '--clear',
#             action='store_true',
#             help='Delete all existing seeded donors before importing',
#         )
#         parser.add_argument(
#             '--hospital-id',
#             type=int,
#             default=None,
#             help='Assign all donors to a specific hospital ID (optional)',
#         )

#     def handle(self, *args, **options):
#         csv_path = options['csv']
#         limit = options['limit']
#         clear = options['clear']
#         hospital_id = options['hospital_id']

#         # --- اختياري: جيب مستشفى لو حددتِ ID ---
#         hospital = None
#         if hospital_id:
#             try:
#                 hospital = Hospital.objects.get(pk=hospital_id)
#                 self.stdout.write(f'✅ Hospital: {hospital.name}')
#             except Hospital.DoesNotExist:
#                 raise CommandError(f'Hospital with id={hospital_id} not found.')

#         # --- امسح القديم لو --clear ---
#         if clear:
#             deleted_profiles = DonorMedicalProfile.objects.filter(
#                 donor_code__isnull=False
#             ).count()
#             # امسح الـ User بتاع كل profile معمول من seed
#             User.objects.filter(
#                 donor_profile__donor_code__isnull=False
#             ).delete()
#             self.stdout.write(
#                 self.style.WARNING(f'🗑  Cleared {deleted_profiles} existing seeded donors.')
#             )

#         # --- افتح الـ CSV ---
#         try:
#             f = open(csv_path, encoding='utf-8')
#         except FileNotFoundError:
#             raise CommandError(f'File not found: {csv_path}')

#         reader = csv.DictReader(f)
#         rows = list(reader)
#         f.close()

#         if limit:
#             rows = rows[:limit]

#         self.stdout.write(f'📂 Rows to import: {len(rows)}')

#         created = 0
#         skipped = 0
#         errors = 0

#         with transaction.atomic():
#             for i, row in enumerate(rows, start=1):

#                 donor_code = row.get('donor_id', '').strip()
#                 if not donor_code:
#                     skipped += 1
#                     continue

#                 # تجاهل لو موجود بالفعل
#                 if DonorMedicalProfile.objects.filter(donor_code=donor_code).exists():
#                     skipped += 1
#                     continue

#                 # --- map الـ organ ---
#                 organ_raw = row.get('organ_type', '').strip().lower()
#                 organ = ORGAN_MAP.get(organ_raw)
#                 if not organ:
#                     self.stderr.write(f'Row {i}: unknown organ "{organ_raw}" — skipped')
#                     skipped += 1
#                     continue

#                 # --- map الـ portion ---
#                 portion_raw = row.get('organ_full_or_partial', 'full').strip().lower()
#                 portion = PORTION_MAP.get(portion_raw, OrganPortion.FULL)

#                 # --- partial validation ---
#                 PARTIAL_ALLOWED = {'kidney', 'liver'}
#                 if portion != OrganPortion.FULL and organ_raw not in PARTIAL_ALLOWED:
#                     portion = OrganPortion.FULL  # fallback

#                 # --- gender ---
#                 sex_raw = row.get('sex', '').strip()
#                 gender = GENDER_MAP.get(sex_raw, 'ذكر')

#                 # --- blood type ---
#                 blood_raw = row.get('blood_type', '').strip()
#                 blood_type = BLOOD_MAP.get(blood_raw, 'O')

#                 # --- national id (unique وهمي) ---
#                 national_id = _rand_national_id()
#                 while User.objects.filter(national_id=national_id).exists():
#                     national_id = _rand_national_id()

#                 try:
#                     # إنشاء الـ User
#                     user = User.objects.create(
#                         national_id=national_id,
#                         first_name=f'Donor',
#                         last_name=donor_code,
#                         role='donor',
#                         birthdate=_age_to_birthdate(row.get('age')),
#                         height_cm=_parse_float(row.get('height_cm')),
#                         weight_kg=_parse_float(row.get('weight_kg')),
#                         blood_type=blood_type,
#                         gender=gender,
#                         medical_record_number=_rand_medical_record(),
#                         HLA_A_1=row.get('HLA_A_1', '').strip() or None,
#                         HLA_A_2=row.get('HLA_A_2', '').strip() or None,
#                         HLA_B_1=row.get('HLA_B_1', '').strip() or None,
#                         HLA_B_2=row.get('HLA_B_2', '').strip() or None,
#                         HLA_DR_1=row.get('HLA_DR_1', '').strip() or None,
#                         HLA_DR_2=row.get('HLA_DR_2', '').strip() or None,
#                         PRA=_parse_float(row.get('PRA')),
#                         CMV_status=_parse_bool(row.get('CMV_status')),
#                         EBV_status=_parse_bool(row.get('EBV_status')),
#                         hospital=hospital,
#                         status='قيد الانتظار',
#                     )
#                     user.set_password(national_id[-4:])
#                     user.save()

#                     # KDPI بيُحسب بس للكُلى — تجاهله لأي organ تاني
#                     kdpi = _parse_float(row.get('kdpi_score')) if organ_raw in KIDNEY_ORGANS else None

#                     # إنشاء الـ DonorMedicalProfile
#                     DonorMedicalProfile.objects.create(
#                         donor=user,
#                         organ_available=organ,
#                         organ_full_or_partial=portion,
#                         donation_type=row.get('donation_type', 'living').strip(),
#                         kdpi_score=kdpi,
#                         donor_code=donor_code,
#                         distance_km=_parse_float(row.get('distance_km')),
#                         cold_ischemia_limit_hours=_parse_int(row.get('cold_ischemia_limit_hours')),
#                     )

#                     created += 1

#                     if created % 500 == 0:
#                         self.stdout.write(f'   ... {created} donors created so far')

#                 except Exception as e:
#                     self.stderr.write(f'Row {i} ({donor_code}): ERROR — {e}')
#                     errors += 1

#         # --- Summary ---
#         self.stdout.write(self.style.SUCCESS(
#             f'\n🎉 Done!\n'
#             f'   ✅ Created : {created}\n'
#             f'   ⏭  Skipped : {skipped}\n'
#             f'   ❌ Errors  : {errors}\n'
#         ))




# # =============================================================
# # المسار: your_app/management/commands/seed_donors.py
# #
# # لو مش موجود الـ folder، اعمليه يدوياً:
# #   mkdir -p your_app/management/commands
# #   touch your_app/management/__init__.py
# #   touch your_app/management/commands/__init__.py
# #
# # تشغيل:
# #   python manage.py seed_donors --csv path/to/donors_10000_living_deceased_organs.csv
# #   python manage.py seed_donors --csv path/to/file.csv --limit 500   # لو عايزة تجربي بعدد أقل
# #   python manage.py seed_donors --csv path/to/file.csv --clear       # يمسح القديم ويبدأ من الأول
# # =============================================================



# =============================================================
# المسار: your_app/management/commands/seed_donors.py
#
# لو مش موجود الـ folder، اعمليه يدوياً:
#   mkdir -p your_app/management/commands
#   touch your_app/management/__init__.py
#   touch your_app/management/commands/__init__.py
#
# تشغيل:
#   python manage.py seed_donors --csv path/to/donors_10000_living_deceased_organs.csv
#   python manage.py seed_donors --csv path/to/file.csv --limit 500   # لو عايزة تجربي بعدد أقل
#   python manage.py seed_donors --csv path/to/file.csv --clear       # يمسح القديم ويبدأ من الأول
# =============================================================

import csv
import random
import string
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# ⚠️ غيري اسم الـ app لو مختلف
from core.models import (
    User,
    Hospital,
    DonorMedicalProfile,
    OrganType,
    OrganPortion,
)


# ---------- helpers ----------

BLOOD_MAP = {
    'A': 'A', 'B': 'B', 'O': 'O', 'AB': 'AB',
    'A+': 'A', 'B+': 'B', 'O+': 'O', 'AB+': 'AB',
    'A-': 'A', 'B-': 'B', 'O-': 'O', 'AB-': 'AB',
}

GENDER_MAP = {
    'M': 'ذكر',
    'F': 'انثي',
    'male': 'ذكر',
    'female': 'انثي',
}

ORGAN_MAP = {
    'kidney': OrganType.KIDNEY,
    'kidney_right': OrganType.KIDNEY_RIGHT,
    'kidney_left': OrganType.KIDNEY_LEFT,
    'liver': OrganType.LIVER,
    'liver_lobe': OrganType.LIVER_LOBE,
    'heart': OrganType.HEART,
    'lung_right': OrganType.LUNG_RIGHT,
    'lung_lobe': OrganType.LUNG_LOBE,
    'lung_left': OrganType.LUNG_RIGHT,       # fallback: أقرب نوع موجود في الـ model
    'pancreas': OrganType.PANCREAS,
    'pancreas_segment': OrganType.PANCREAS,   # fallback: segment غير مدعوم → full pancreas
}

# الـ organs اللي بيُقبل KDPI فيها (كل أنواع الكُلى)
KIDNEY_ORGANS = {'kidney', 'kidney_right', 'kidney_left'}

PORTION_MAP = {
    'full': OrganPortion.FULL,
    'segment': OrganPortion.SEGMENT,
    'lobe': OrganPortion.LOBE,
}


def _rand_national_id():
    """يولّد رقم قومي مصري وهمي (14 رقم)."""
    return ''.join(random.choices(string.digits, k=14))


def _rand_medical_record():
    return 'MR-' + ''.join(random.choices(string.digits, k=6))


def _age_to_birthdate(age_str):
    """يحوّل العمر لتاريخ ميلاد تقريبي."""
    try:
        age = int(age_str)
        return date.today() - timedelta(days=age * 365)
    except (ValueError, TypeError):
        return date(1990, 1, 1)


def _parse_float(val):
    try:
        return float(val) if val and val.strip() else None
    except ValueError:
        return None


def _parse_int(val):
    try:
        return int(float(val)) if val and val.strip() else None
    except ValueError:
        return None


def _parse_bool(val):
    return val.strip().lower() == 'positive' if val else False


# ---------- Command ----------

class Command(BaseCommand):
    help = 'Seed the database with donors from the CSV dataset'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            required=True,
            help='Full path to donors CSV file',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Max number of rows to import (default: all)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing seeded donors before importing',
        )
        parser.add_argument(
            '--hospital-id',
            type=int,
            default=None,
            help='Assign all donors to a specific hospital ID (optional)',
        )

    def handle(self, *args, **options):
        csv_path = options['csv']
        limit = options['limit']
        clear = options['clear']
        hospital_id = options['hospital_id']

        # --- جيب كل المستشفيات المتاحة ---
        if hospital_id:
            hospitals = list(Hospital.objects.filter(pk=hospital_id))
            if not hospitals:
                raise CommandError(f'Hospital with id={hospital_id} not found.')
            self.stdout.write(f'✅ Using hospital: {hospitals[0].name}')
        else:
            hospitals = list(Hospital.objects.all())

        if not hospitals:
            raise CommandError('❌ No hospitals found. Run: python manage.py seed_hospitals first.')

        self.stdout.write(f'🏥 Found {len(hospitals)} hospital(s) — distributing donors across them.')

        # doctors_map = { hospital_id: [doctor, ...] }
        doctors_map = {}
        for h in hospitals:
            docs = list(h.doctors.all())
            if docs:
                doctors_map[h.id] = docs

        # --- امسح القديم لو --clear ---
        if clear:
            deleted_profiles = DonorMedicalProfile.objects.filter(
                donor_code__isnull=False
            ).count()
            # امسح الـ User بتاع كل profile معمول من seed
            User.objects.filter(
                donor_profile__donor_code__isnull=False
            ).delete()
            self.stdout.write(
                self.style.WARNING(f'🗑  Cleared {deleted_profiles} existing seeded donors.')
            )

        # --- افتح الـ CSV ---
        try:
            f = open(csv_path, encoding='utf-8')
        except FileNotFoundError:
            raise CommandError(f'File not found: {csv_path}')

        reader = csv.DictReader(f)
        rows = list(reader)
        f.close()

        if limit:
            rows = rows[:limit]

        self.stdout.write(f'📂 Rows to import: {len(rows)}')

        created = 0
        skipped = 0
        errors = 0

        # --- ملف لحفظ بيانات الدخول ---
        credentials_path = csv_path.replace('.csv', '_credentials.csv')
        cred_file = open(credentials_path, 'w', newline='', encoding='utf-8')
        cred_writer = csv.writer(cred_file)
        cred_writer.writerow(['donor_code', 'national_id', 'password'])

        with transaction.atomic():
            for i, row in enumerate(rows, start=1):

                donor_code = row.get('donor_id', '').strip()
                if not donor_code:
                    skipped += 1
                    continue

                # تجاهل لو موجود بالفعل
                if DonorMedicalProfile.objects.filter(donor_code=donor_code).exists():
                    skipped += 1
                    continue

                # --- map الـ organ ---
                organ_raw = row.get('organ_type', '').strip().lower()
                organ = ORGAN_MAP.get(organ_raw)
                if not organ:
                    self.stderr.write(f'Row {i}: unknown organ "{organ_raw}" — skipped')
                    skipped += 1
                    continue

                # --- map الـ portion ---
                portion_raw = row.get('organ_full_or_partial', 'full').strip().lower()
                portion = PORTION_MAP.get(portion_raw, OrganPortion.FULL)

                # --- partial validation ---
                PARTIAL_ALLOWED = {'kidney', 'liver'}
                if portion != OrganPortion.FULL and organ_raw not in PARTIAL_ALLOWED:
                    portion = OrganPortion.FULL  # fallback

                # --- gender ---
                sex_raw = row.get('sex', '').strip()
                gender = GENDER_MAP.get(sex_raw, 'ذكر')

                # --- blood type ---
                blood_raw = row.get('blood_type', '').strip()
                blood_type = BLOOD_MAP.get(blood_raw, 'O')

                # --- national id (unique وهمي) ---
                national_id = _rand_national_id()
                while User.objects.filter(national_id=national_id).exists():
                    national_id = _rand_national_id()

                # --- توزيع round-robin على المستشفيات ---
                assigned_hospital = hospitals[i % len(hospitals)]
                # اختار دكتور من نفس المستشفى لو موجود
                hospital_doctors = doctors_map.get(assigned_hospital.id, [])
                assigned_doctor = hospital_doctors[i % len(hospital_doctors)] if hospital_doctors else None

                try:
                    # إنشاء الـ User
                    user = User.objects.create(
                        national_id=national_id,
                        first_name='Donor',
                        last_name=donor_code,
                        role='donor',
                        birthdate=_age_to_birthdate(row.get('age')),
                        height_cm=_parse_float(row.get('height_cm')),
                        weight_kg=_parse_float(row.get('weight_kg')),
                        blood_type=blood_type,
                        gender=gender,
                        medical_record_number=_rand_medical_record(),
                        HLA_A_1=row.get('HLA_A_1', '').strip() or None,
                        HLA_A_2=row.get('HLA_A_2', '').strip() or None,
                        HLA_B_1=row.get('HLA_B_1', '').strip() or None,
                        HLA_B_2=row.get('HLA_B_2', '').strip() or None,
                        HLA_DR_1=row.get('HLA_DR_1', '').strip() or None,
                        HLA_DR_2=row.get('HLA_DR_2', '').strip() or None,
                        PRA=_parse_float(row.get('PRA')),
                        CMV_status=_parse_bool(row.get('CMV_status')),
                        EBV_status=_parse_bool(row.get('EBV_status')),
                        hospital=assigned_hospital,
                        supervisor_doctor=assigned_doctor,
                        status='قيد الانتظار',
                    )
                    user.set_password(national_id[-4:])
                    user.save()

                    # KDPI بيُحسب بس للكُلى — تجاهله لأي organ تاني
                    kdpi = _parse_float(row.get('kdpi_score')) if organ_raw in KIDNEY_ORGANS else None

                    # إنشاء الـ DonorMedicalProfile
                    DonorMedicalProfile.objects.create(
                        donor=user,
                        organ_available=organ,
                        organ_full_or_partial=portion,
                        donation_type=row.get('donation_type', 'living').strip(),
                        kdpi_score=kdpi,
                        donor_code=donor_code,
                        distance_km=_parse_float(row.get('distance_km')),
                        cold_ischemia_limit_hours=_parse_int(row.get('cold_ischemia_limit_hours')),
                    )

                    created += 1
                    cred_writer.writerow([donor_code, national_id, national_id[-4:]])

                    if created % 500 == 0:
                        self.stdout.write(f'   ... {created} donors created so far')

                except Exception as e:
                    self.stderr.write(f'Row {i} ({donor_code}): ERROR — {e}')
                    errors += 1

        # --- Summary ---
        cred_file.close()
        self.stdout.write(self.style.SUCCESS(
            f'\n🎉 Done!\n'
            f'   ✅ Created : {created}\n'
            f'   ⏭  Skipped : {skipped}\n'
            f'   ❌ Errors  : {errors}\n'
            f'   🔑 Credentials saved to: {credentials_path}\n'
        ))