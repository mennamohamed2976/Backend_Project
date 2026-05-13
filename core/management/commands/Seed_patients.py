"""
Management Command: seed_patients_from_csv
==========================================
Place this file at:
    your_app/management/commands/seed_patients_from_csv.py

Run:
    python manage.py seed_patients_from_csv
    python manage.py seed_patients_from_csv --file path/to/recipients.csv
    python manage.py seed_patients_from_csv --limit 1000
    python manage.py seed_patients_from_csv --clear
"""

import csv
import random
import math
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import (
    User, Hospital, Doctor,
    PatientMedicalProfile
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

ARABIC_FIRST_NAMES_M = [
    "أحمد", "محمد", "عمر", "علي", "خالد", "يوسف", "حسن", "مصطفى",
    "كريم", "طارق", "وليد", "عمرو", "إبراهيم", "سامي", "رامي",
]
ARABIC_FIRST_NAMES_F = [
    "فاطمة", "سارة", "نور", "ريم", "هند", "منى", "دينا", "رانيا",
    "أميرة", "ياسمين", "مروة", "شيماء", "نادية", "سمر", "هبة",
]
ARABIC_LAST_NAMES = [
    "السيد", "محمد", "عبد الله", "حسن", "إبراهيم", "علي", "حسين",
    "مصطفى", "عبد الرحمن", "الشريف", "فاروق", "سليمان", "ناصر",
    "جمال", "عبد العزيز", "رمضان", "عثمان", "قاسم",
]
CITIES = [
    "القاهرة", "الإسكندرية", "الجيزة", "أسيوط", "المنصورة",
    "الإسماعيلية", "بورسعيد", "سوهاج", "أسوان", "الأقصر",
]

def generate_national_id(index: int) -> str:
    """Generate a unique 14-digit national ID."""
    return f"2{str(index).zfill(13)}"

def generate_medical_record(index: int) -> str:
    return f"MRN-{str(index).zfill(7)}"

def sex_to_gender(sex: str) -> str:
    return "ذكر" if sex.strip().upper() == "M" else "انثي"

def cmv_to_bool(val: str) -> bool:
    return str(val).strip().lower() == "positive"

def safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def safe_int(val) -> int | None:
    try:
        f = float(val)
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None

def birthdate_from_age(age: int) -> str:
    """Return approximate birthdate string from age."""
    year = 2025 - age
    return f"{year}-06-15"


# ─────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed patients from recipients CSV file, distributed across hospitals and doctors."

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='recipients_30000__1_.csv',
            help='Path to the CSV file (default: recipients_30000__1_.csv)',
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
            help='Delete all existing patients before seeding.',
        )
        parser.add_argument(
            '--batch',
            type=int,
            default=500,
            help='Batch size for bulk_create (default: 500)',
        )

    def handle(self, *args, **options):
        csv_file   = options['file']
        limit      = options['limit']
        batch_size = options['batch']

        # ── Load hospitals & doctors ───────────────────────────────
        hospitals = list(Hospital.objects.all())
        doctors   = list(Doctor.objects.all())

        if not hospitals:
            self.stderr.write(self.style.ERROR(
                "❌  No hospitals found. Run seed_hospitals first."
            ))
            return
        if not doctors:
            self.stderr.write(self.style.ERROR(
                "❌  No doctors found. Run seed_hospitals first."
            ))
            return

        self.stdout.write(f"🏥  Found {len(hospitals)} hospitals, {len(doctors)} doctors")

        # ── Optional clear ─────────────────────────────────────────
        if options['clear']:
            self.stdout.write(self.style.WARNING("🗑️  Clearing existing patients..."))
            User.objects.filter(role='patient').delete()
            self.stdout.write(self.style.WARNING("    Done.\n"))

        # ── Read CSV ───────────────────────────────────────────────
        self.stdout.write(f"📂  Reading {csv_file} ...")
        try:
            with open(csv_file, newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"❌  File not found: {csv_file}"))
            return

        if limit:
            rows = rows[:limit]

        total = len(rows)
        self.stdout.write(f"📊  {total} rows to import\n")

        created   = 0
        skipped   = 0
        profiles  = []

        # ── Build existing national_id set for fast dedup ──────────
        existing_ids = set(
            User.objects.filter(role='patient')
            .values_list('national_id', flat=True)
        )
        existing_recipient_ids = set(
            PatientMedicalProfile.objects
            .exclude(recipient_id=None)
            .values_list('recipient_id', flat=True)
        )

        users_batch = []

        for i, row in enumerate(rows):
            global_index = i + 1

            recipient_id = row.get('recipient_id', '').strip()

            # Skip if recipient_id already imported
            if recipient_id in existing_recipient_ids:
                skipped += 1
                continue

            national_id = generate_national_id(global_index)
            # Ensure uniqueness (edge case)
            while national_id in existing_ids:
                global_index += 50000
                national_id = generate_national_id(global_index)
            existing_ids.add(national_id)

            sex    = row.get('sex', 'M')
            gender = sex_to_gender(sex)
            names  = ARABIC_FIRST_NAMES_M if gender == "ذكر" else ARABIC_FIRST_NAMES_F
            first_name = random.choice(names)
            last_name  = random.choice(ARABIC_LAST_NAMES)

            # Round-robin distribution
            hospital = hospitals[i % len(hospitals)]
            doctor   = doctors[i % len(doctors)]

            age       = safe_int(row.get('age', 30)) or 30
            birthdate = birthdate_from_age(age)

            user = User(
                national_id         = national_id,
                first_name          = first_name,
                last_name           = last_name,
                role                = 'patient',
                status              = 'قيد الانتظار',
                birthdate           = birthdate,
                height_cm           = safe_float(row.get('height_cm')),
                weight_kg           = safe_float(row.get('weight_kg')),
                blood_type          = row.get('blood_type', 'O').strip(),
                gender              = gender,
                medical_record_number = generate_medical_record(global_index),
                HLA_A_1             = row.get('HLA_A_1', '').strip() or None,
                HLA_A_2             = row.get('HLA_A_2', '').strip() or None,
                HLA_B_1             = row.get('HLA_B_1', '').strip() or None,
                HLA_B_2             = row.get('HLA_B_2', '').strip() or None,
                HLA_DR_1            = row.get('HLA_DR_1', '').strip() or None,
                HLA_DR_2            = row.get('HLA_DR_2', '').strip() or None,
                PRA                 = safe_float(row.get('PRA')),
                CMV_status          = cmv_to_bool(row.get('CMV_status', 'negative')),
                EBV_status          = cmv_to_bool(row.get('EBV_status', 'negative')),
                hospital            = hospital,
                supervisor_doctor   = doctor,
                city                = random.choice(CITIES),
                is_active           = True,
                is_staff            = False,
            )
            user.set_password(national_id[-4:])  # last 4 digits = password

            users_batch.append((user, row, recipient_id))

            # ── Flush batch ────────────────────────────────────────
            if len(users_batch) >= batch_size:
                count = self._flush_batch(users_batch, batch_size)
                created += count
                users_batch = []

                pct = round((i + 1) / total * 100, 1)
                self.stdout.write(f"    ✅  {i+1}/{total} ({pct}%) — {created} created so far")

        # Flush remainder
        if users_batch:
            count = self._flush_batch(users_batch, batch_size)
            created += count

        # ── Summary ────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"✅  Patients created : {created}"))
        self.stdout.write(self.style.WARNING(f"⏭️   Skipped          : {skipped}"))
        self.stdout.write(self.style.SUCCESS("\n🎉  Seeding complete!"))
        self.stdout.write("💡  Password for each patient = last 4 digits of their national_id")

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────

    def _flush_batch(self, users_batch, batch_size):
        """
        Save Users one-by-one (to get PKs reliably on all DB backends),
        then bulk_create their PatientMedicalProfiles in one shot.
        """
        profiles = []

        with transaction.atomic():
            for user_obj, row, recipient_id in users_batch:
                # save() guarantees PK is set on every backend (SQLite, PostgreSQL, MySQL)
                user_obj.save()

                profiles.append(PatientMedicalProfile(
                    patient                = user_obj,
                    organ_needed           = row.get('organ_needed', 'kidney').strip(),
                    recipient_id           = recipient_id or None,
                    urgency_level          = row.get('urgency_level', 'medium').strip() or None,
                    waitlist_time_days     = safe_int(row.get('waitlist_time_days')),
                    dialysis_duration_days = safe_int(row.get('dialysis_duration_days')),
                    MELD_score             = safe_float(row.get('MELD_score')),
                    lung_severity_score    = safe_float(row.get('lung_severity_score')),
                ))

            # Now all PKs are set — safe to bulk_create profiles
            PatientMedicalProfile.objects.bulk_create(profiles, batch_size=batch_size)

        return len(users_batch)


def safe_float(val):
    import math
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def safe_int(val):
    import math
    try:
        f = float(val)
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None