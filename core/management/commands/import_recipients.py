# """
# Management Command: import_recipients
# ======================================
# Place this file at:
#     your_app/management/commands/import_recipients.py

# Make sure these files exist (can be empty):
#     your_app/management/__init__.py
#     your_app/management/commands/__init__.py

# Run:
#     python manage.py import_recipients /full/path/to/recipients.csv
#     python manage.py import_recipients /full/path/to/recipients.csv --hospital-id 1 --doctor-id 2
#     python manage.py import_recipients /full/path/to/recipients.csv --limit 100   # for testing
# """

# import pandas as pd
# import random
# import string
# from datetime import date
# from django.core.management.base import BaseCommand
# from django.db import transaction
# from core.models import (
#     User, PatientMedicalProfile, Hospital, Doctor
# )
# import random

# # ─────────────────────────────────────────────
# # Helper functions
# # ─────────────────────────────────────────────

# def random_national_id():
#     """Generate a unique random 14-digit national ID."""
#     while True:
#         nid = ''.join(random.choices(string.digits, k=14))
#         if not User.objects.filter(national_id=nid).exists():
#             return nid


# def age_to_birthdate(age: int) -> date:
#     """Convert age (int) → approximate birthdate."""
#     today = date.today()
#     try:
#         return today.replace(year=today.year - age)
#     except ValueError:
#         # Handle Feb 29 edge case
#         return today.replace(year=today.year - age, day=28)


# def parse_gender(sex: str) -> str:
#     """M/F  →  Arabic gender choices used in the User model."""
#     return 'ذكر' if str(sex).strip().upper() == 'M' else 'انثي'


# def parse_blood_type(bt) -> str:
#     """Normalize blood type value."""
#     if pd.isna(bt):
#         return 'O'
#     return str(bt).strip().upper()


# def parse_bool_status(value) -> bool:
#     """'positive' → True, 'negative' / NaN → False."""
#     if pd.isna(value):
#         return False
#     return str(value).strip().lower() == 'positive'


# def parse_float(value):
#     """Return float or None for NaN."""
#     if pd.isna(value):
#         return None
#     return float(value)


# def parse_int(value):
#     """Return int or None for NaN."""
#     if pd.isna(value):
#         return None
#     return int(float(value))


# def normalize_organ(organ: str) -> str:
#     """
#     Map CSV organ values → OrganType choices in the model.

#     CSV has two values not in OrganType:
#       - 'lung_left'        → mapped to 'lung_right'  (closest available)
#       - 'pancreas_segment' → mapped to 'pancreas'
#     """
#     mapping = {
#         'lung_left':        'lung_right',
#         'pancreas_segment': 'pancreas',
#     }
#     return mapping.get(organ.strip(), organ.strip())


# # ─────────────────────────────────────────────
# # Management Command
# # ─────────────────────────────────────────────

# class Command(BaseCommand):
#     help = "Import recipients from a CSV file into the database as patients."

#     def add_arguments(self, parser):
#         parser.add_argument(
#             'csv_path',
#             type=str,
#             help='Absolute path to the recipients CSV file.',
#         )
#         parser.add_argument(
#             '--hospital-id',
#             type=int,
#             default=None,
#             help='Hospital ID to assign to all imported patients (optional).',
#         )
#         parser.add_argument(
#             '--doctor-id',
#             type=int,
#             default=None,
#             help='Doctor ID to assign as supervisor for all patients (optional).',
#         )
#         parser.add_argument(
#             '--limit',
#             type=int,
#             default=None,
#             help='Max number of rows to import — useful for testing.',
#         )

#     def handle(self, *args, **options):
#         csv_path    = options['csv_path']
#         hospital_id = options['hospital_id']
#         doctor_id   = options['doctor_id']
#         limit       = options['limit']

#         # ── Load CSV ──────────────────────────────────────────────
#         self.stdout.write(self.style.NOTICE(f"\n📂  Loading: {csv_path}"))
#         df = pd.read_csv(csv_path, nrows=limit)
#         self.stdout.write(self.style.NOTICE(f"📊  Rows to process: {len(df)}\n"))

#         # ── Optional FK lookups ───────────────────────────────────
#         hospital = None
#         doctor   = None

#         if hospital_id:
#             try:
#                 hospital = Hospital.objects.get(pk=hospital_id)
#                 self.stdout.write(f"🏥  Hospital : {hospital.name}")
#             except Hospital.DoesNotExist:
#                 self.stderr.write(self.style.ERROR(f"Hospital ID {hospital_id} not found."))
#                 return

#         if doctor_id:
#             try:
#                 doctor = Doctor.objects.get(pk=doctor_id)
#                 self.stdout.write(f"👨‍⚕️  Doctor   : {doctor.name}")
#             except Doctor.DoesNotExist:
#                 self.stderr.write(self.style.ERROR(f"Doctor ID {doctor_id} not found."))
#                 return

#         # ── Collect existing recipient_ids (to skip duplicates) ───
#         existing_ids = set(
#             PatientMedicalProfile.objects
#             .filter(recipient_id__isnull=False)
#             .values_list('recipient_id', flat=True)
#         )
#         self.stdout.write(f"ℹ️   Already imported: {len(existing_ids)} recipients\n")

#         # ── Counters ──────────────────────────────────────────────
#         created = 0
#         skipped = 0
#         errors  = 0

#         # ── Main loop ─────────────────────────────────────────────
#         for idx, row in df.iterrows():
#             recipient_id = str(row['recipient_id']).strip()

#             # Skip already-imported recipients
#             if recipient_id in existing_ids:
#                 skipped += 1
#                 continue

#             try:
#                 with transaction.atomic():

#                     # ── Generate unique national_id ───────────────
#                     national_id = random_national_id()

#                     # ── Create User ───────────────────────────────
#                     user = User(
#                         national_id           = national_id,
#                         first_name            = recipient_id,       # placeholder
#                         last_name             = 'Dataset',
#                         role                  = 'patient',
#                         birthdate             = age_to_birthdate(int(row['age'])),
#                         gender                = parse_gender(row['sex']),
#                         height_cm             = parse_float(row['height_cm']),
#                         weight_kg             = parse_float(row['weight_kg']),
#                         blood_type            = parse_blood_type(row['blood_type']),
#                         HLA_A_1               = str(row['HLA_A_1']).strip() if pd.notna(row['HLA_A_1']) else None,
#                         HLA_A_2               = str(row['HLA_A_2']).strip() if pd.notna(row['HLA_A_2']) else None,
#                         HLA_B_1               = str(row['HLA_B_1']).strip() if pd.notna(row['HLA_B_1']) else None,
#                         HLA_B_2               = str(row['HLA_B_2']).strip() if pd.notna(row['HLA_B_2']) else None,
#                         HLA_DR_1              = str(row['HLA_DR_1']).strip() if pd.notna(row['HLA_DR_1']) else None,
#                         HLA_DR_2              = str(row['HLA_DR_2']).strip() if pd.notna(row['HLA_DR_2']) else None,
#                         PRA                   = parse_float(row['PRA']),
#                         CMV_status            = parse_bool_status(row['CMV_status']),
#                         EBV_status            = parse_bool_status(row['EBV_status']),
#                         medical_record_number = recipient_id,
#                         hospital              = hospital,
#                         supervisor_doctor     = doctor,
#                     )
#                     user.set_password(national_id[-4:])   # password = last 4 digits
#                     user.save()                            # BMI auto-calculated in User.save()

#                     # ── Create PatientMedicalProfile ──────────────
#                     PatientMedicalProfile.objects.create(
#                         patient                = user,
#                         organ_needed           = normalize_organ(str(row['organ_needed'])),
#                         recipient_id           = recipient_id,
#                         urgency_level          = str(row['urgency_level']).strip().lower() if pd.notna(row['urgency_level']) else None,
#                         waitlist_time_days     = parse_int(row['waitlist_time_days']),
#                         dialysis_duration_days = parse_int(row['dialysis_duration_days']),
#                         MELD_score             = parse_float(row['MELD_score']),
#                         lung_severity_score    = parse_float(row['lung_severity_score']),
#                     )

#                     created += 1
#                     existing_ids.add(recipient_id)

#                     if created % 500 == 0:
#                         self.stdout.write(f"  ✅  {created} patients imported so far...")

#             except Exception as e:
#                 errors += 1
#                 self.stderr.write(
#                     self.style.ERROR(f"  ❌  Row {idx} ({recipient_id}): {e}")
#                 )

#         # ── Final summary ─────────────────────────────────────────
#         self.stdout.write("")
#         self.stdout.write(self.style.SUCCESS(f"✅  Created : {created}"))
#         self.stdout.write(self.style.WARNING(f"⏭️   Skipped : {skipped}  (already existed)"))
#         if errors:
#             self.stdout.write(self.style.ERROR(f"❌  Errors  : {errors}"))
#         self.stdout.write(self.style.SUCCESS("\n🎉  Import complete!"))


import pandas as pd
import random
import string

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    User,
    PatientMedicalProfile,
    Hospital,
    Doctor
)

# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────

def random_national_id():
    """Generate a unique random 14-digit national ID."""
    while True:
        nid = ''.join(random.choices(string.digits, k=14))
        if not User.objects.filter(national_id=nid).exists():
            return nid


def age_to_birthdate(age: int) -> date:
    """Convert age → approximate birthdate."""
    today = date.today()
    try:
        return today.replace(year=today.year - age)
    except ValueError:
        return today.replace(year=today.year - age, day=28)


def parse_gender(sex: str) -> str:
    return 'ذكر' if str(sex).strip().upper() == 'M' else 'انثي'


def parse_blood_type(bt) -> str:
    if pd.isna(bt):
        return 'O'
    return str(bt).strip().upper()


def parse_bool_status(value) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip().lower() == 'positive'


def parse_float(value):
    if pd.isna(value):
        return None
    return float(value)


def parse_int(value):
    if pd.isna(value):
        return None
    return int(float(value))


def normalize_organ(organ: str) -> str:
    mapping = {
        'lung_left': 'lung_right',
        'pancreas_segment': 'pancreas',
    }
    return mapping.get(organ.strip(), organ.strip())


# ─────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────

class Command(BaseCommand):

    help = "Import recipients from CSV."

    def add_arguments(self, parser):

        parser.add_argument(
            'csv_path',
            type=str,
            help='Path to CSV file'
        )

        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit rows for testing'
        )

        # ✅ NEW FLAG
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing patient data before import'
        )

    def handle(self, *args, **options):

        csv_path = options['csv_path']
        limit = options['limit']
        clear = options['clear']

        # ─────────────────────────────────────
        # Clear old data (if requested)
        # ─────────────────────────────────────
        if clear:
            self.stdout.write(self.style.WARNING("⚠️ Clearing existing recipient data..."))

            PatientMedicalProfile.objects.all().delete()
            User.objects.filter(role='patient').delete()

            self.stdout.write(self.style.SUCCESS("🧹 Old data cleared!\n"))

        # ─────────────────────────────────────
        # Load CSV
        # ─────────────────────────────────────
        self.stdout.write(self.style.NOTICE(f"📂 Loading: {csv_path}"))

        df = pd.read_csv(csv_path, nrows=limit)

        self.stdout.write(self.style.NOTICE(f"📊 Rows: {len(df)}\n"))

        # ─────────────────────────────────────
        # Hospitals
        # ─────────────────────────────────────
        hospitals = list(Hospital.objects.all())

        if not hospitals:
            self.stderr.write(self.style.ERROR("❌ No hospitals found"))
            return

        # ─────────────────────────────────────
        # Existing recipients
        # ─────────────────────────────────────
        existing_ids = set(
            PatientMedicalProfile.objects
            .filter(recipient_id__isnull=False)
            .values_list('recipient_id', flat=True)
        )

        created = 0
        skipped = 0
        errors = 0

        # ─────────────────────────────────────
        # Main loop
        # ─────────────────────────────────────
        for idx, row in df.iterrows():

            recipient_id = str(row['recipient_id']).strip()

            if recipient_id in existing_ids:
                skipped += 1
                continue

            try:
                with transaction.atomic():

                    hospital = random.choice(hospitals)

                    doctors = list(Doctor.objects.filter(hospital=hospital))
                    doctor = random.choice(doctors) if doctors else None

                    national_id = random_national_id()

                    user = User(
                        national_id=national_id,
                        first_name=recipient_id,
                        last_name='Dataset',
                        role='patient',
                        birthdate=age_to_birthdate(int(row['age'])),
                        gender=parse_gender(row['sex']),
                        height_cm=parse_float(row['height_cm']),
                        weight_kg=parse_float(row['weight_kg']),
                        blood_type=parse_blood_type(row['blood_type']),

                        HLA_A_1=str(row['HLA_A_1']).strip() if pd.notna(row['HLA_A_1']) else None,
                        HLA_A_2=str(row['HLA_A_2']).strip() if pd.notna(row['HLA_A_2']) else None,
                        HLA_B_1=str(row['HLA_B_1']).strip() if pd.notna(row['HLA_B_1']) else None,
                        HLA_B_2=str(row['HLA_B_2']).strip() if pd.notna(row['HLA_B_2']) else None,
                        HLA_DR_1=str(row['HLA_DR_1']).strip() if pd.notna(row['HLA_DR_1']) else None,
                        HLA_DR_2=str(row['HLA_DR_2']).strip() if pd.notna(row['HLA_DR_2']) else None,

                        PRA=parse_float(row['PRA']),
                        CMV_status=parse_bool_status(row['CMV_status']),
                        EBV_status=parse_bool_status(row['EBV_status']),

                        medical_record_number=recipient_id,
                        hospital=hospital,
                        supervisor_doctor=doctor,
                    )

                    user.set_password(national_id[-4:])
                    user.save()

                    PatientMedicalProfile.objects.create(
                        patient=user,
                        organ_needed=normalize_organ(str(row['organ_needed'])),
                        recipient_id=recipient_id,
                        urgency_level=str(row['urgency_level']).strip().lower() if pd.notna(row['urgency_level']) else None,
                        waitlist_time_days=parse_int(row['waitlist_time_days']),
                        dialysis_duration_days=parse_int(row['dialysis_duration_days']),
                        MELD_score=parse_float(row['MELD_score']),
                        lung_severity_score=parse_float(row['lung_severity_score']),
                    )

                    created += 1
                    existing_ids.add(recipient_id)

                    if created % 500 == 0:
                        self.stdout.write(f"✅ {created} imported...")

            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"❌ Row {idx}: {e}"))

        # ─────────────────────────────────────
        # Summary
        # ─────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"✅ Created: {created}"))
        self.stdout.write(self.style.WARNING(f"⏭️ Skipped: {skipped}"))
        self.stdout.write(self.style.ERROR(f"❌ Errors: {errors}"))
        self.stdout.write(self.style.SUCCESS("\n🎉 Done!"))