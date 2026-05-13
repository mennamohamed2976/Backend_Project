"""
Management Command: seed_hospitals
====================================
Place this file at:
    your_app/management/commands/seed_hospitals.py

Run:
    python manage.py seed_hospitals
    python manage.py seed_hospitals --hospitals 5 --doctors-per-hospital 3
    python manage.py seed_hospitals --clear   # deletes existing data first
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Hospital, Doctor
import random


# ─────────────────────────────────────────────
# Static fake data pools
# ─────────────────────────────────────────────

HOSPITALS_DATA = [
    {
        "name": "مستشفى القاهرة التخصصي",
        "city": "القاهرة",
        "location": "شارع التحرير، وسط البلد، القاهرة",
        "license_number": "LIC-2001-CAI",
        "phone": "0223456789",
        "emergency_phone": "0223456799",
        "email": "cairo.specialized@hospital.eg",
        "working_hours": "24/7",
        "hospital_type": "حكومي",
        "password": "hospital123",
    },
    {
        "name": "مستشفى النيل الدولي",
        "city": "القاهرة",
        "location": "كورنيش النيل، المعادي، القاهرة",
        "license_number": "LIC-2005-NIL",
        "phone": "0227891234",
        "emergency_phone": "0227891299",
        "email": "nile.international@hospital.eg",
        "working_hours": "السبت - الخميس: 8ص - 10م",
        "hospital_type": "خاص",
        "password": "hospital123",
    },
    {
        "name": "مستشفى الإسكندرية الجامعي",
        "city": "الإسكندرية",
        "location": "شارع الحرية، سموحة، الإسكندرية",
        "license_number": "LIC-1998-ALX",
        "phone": "0345678901",
        "emergency_phone": "0345678999",
        "email": "alex.university@hospital.eg",
        "working_hours": "24/7",
        "hospital_type": "حكومي",
        "password": "hospital123",
    },
    {
        "name": "مستشفى الشفاء الخاص",
        "city": "الجيزة",
        "location": "شارع الهرم، الجيزة",
        "license_number": "LIC-2010-GIZ",
        "phone": "0238765432",
        "emergency_phone": "0238765499",
        "email": "shifa.private@hospital.eg",
        "working_hours": "السبت - الجمعة: 7ص - 11م",
        "hospital_type": "خاص",
        "password": "hospital123",
    },
    {
        "name": "مستشفى أسيوط المركزي",
        "city": "أسيوط",
        "location": "شارع جمال عبد الناصر، أسيوط",
        "license_number": "LIC-2003-ASY",
        "phone": "0882345678",
        "emergency_phone": "0882345699",
        "email": "asyut.central@hospital.eg",
        "working_hours": "24/7",
        "hospital_type": "حكومي",
        "password": "hospital123",
    },
]


DOCTORS_DATA = [
    # Kidney specialists
    {"name": "أحمد محمد السيد",      "specialty": "زراعة الكلى",        "phone": "01001234501"},
    {"name": "سارة عبد الله حسن",    "specialty": "زراعة الكلى",        "phone": "01001234502"},
    {"name": "محمود إبراهيم علي",    "specialty": "زراعة الكلى",        "phone": "01001234503"},
    # Liver specialists
    {"name": "فاطمة خالد عمر",       "specialty": "زراعة الكبد",        "phone": "01001234504"},
    {"name": "كريم يوسف ناصر",       "specialty": "زراعة الكبد",        "phone": "01001234505"},
    {"name": "نور الدين حسين",       "specialty": "زراعة الكبد",        "phone": "01001234506"},
    # Heart specialists
    {"name": "منى سامي عبد الرحمن",  "specialty": "زراعة القلب",        "phone": "01001234507"},
    {"name": "طارق مصطفى محمد",      "specialty": "زراعة القلب",        "phone": "01001234508"},
    # Lung specialists
    {"name": "هند رامي عبد العزيز",  "specialty": "زراعة الرئة",        "phone": "01001234509"},
    {"name": "عمر جمال الدين",       "specialty": "زراعة الرئة",        "phone": "01001234510"},
    # Pancreas & General
    {"name": "ريم أشرف سليمان",      "specialty": "زراعة البنكرياس",    "phone": "01001234511"},
    {"name": "وليد حمدي فاروق",      "specialty": "جراحة عامة وزراعة أعضاء", "phone": "01001234512"},
]


class Command(BaseCommand):
    help = "Seed fake hospitals and doctors into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing hospitals and doctors before seeding.',
        )

    def handle(self, *args, **options):

        # ── Optional: clear existing data ─────────────────────────
        if options['clear']:
            self.stdout.write(self.style.WARNING("🗑️  Clearing existing hospitals and doctors..."))
            Doctor.objects.all().delete()
            Hospital.objects.all().delete()
            self.stdout.write(self.style.WARNING("    Done.\n"))

        hospitals_created = 0
        doctors_created   = 0
        skipped           = 0

        with transaction.atomic():
            created_hospitals = []

            # ── Create Hospitals ───────────────────────────────────
            self.stdout.write(self.style.NOTICE("🏥  Creating hospitals..."))

            for data in HOSPITALS_DATA:
                password = data.pop('password')

                hospital, created = Hospital.objects.get_or_create(
                    email=data['email'],
                    defaults={**data, 'status': 'نشط'}
                )

                if created:
                    hospital.set_password(password)
                    hospitals_created += 1
                    self.stdout.write(f"    ✅  {hospital.name}")
                else:
                    skipped += 1
                    self.stdout.write(f"    ⏭️   {hospital.name} (already exists)")

                created_hospitals.append(hospital)

            # ── Create Doctors (distributed across hospitals) ──────
            self.stdout.write(self.style.NOTICE("\n👨‍⚕️  Creating doctors..."))

            for i, doc_data in enumerate(DOCTORS_DATA):
                # Distribute doctors across hospitals in round-robin
                hospital = created_hospitals[i % len(created_hospitals)]

                # Make phone unique per hospital to avoid conflicts
                phone = doc_data['phone'][:-2] + f"{i:02d}"

                doctor, created = Doctor.objects.get_or_create(
                    name=doc_data['name'],
                    hospital=hospital,
                    defaults={
                        'specialty': doc_data['specialty'],
                        'phone': phone,
                    }
                )

                if created:
                    doctors_created += 1
                    self.stdout.write(f"    ✅  Dr. {doctor.name}  →  {hospital.name}  ({doctor.specialty})")
                else:
                    skipped += 1
                    self.stdout.write(f"    ⏭️   Dr. {doctor.name} (already exists)")

        # ── Summary ────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"✅  Hospitals created : {hospitals_created}"))
        self.stdout.write(self.style.SUCCESS(f"✅  Doctors created   : {doctors_created}"))
        self.stdout.write(self.style.WARNING(f"⏭️   Skipped           : {skipped}"))
        self.stdout.write(self.style.SUCCESS("\n🎉  Seeding complete!"))
        self.stdout.write("")
        self.stdout.write("💡  Login credentials for all hospitals:")
        self.stdout.write("    Password: hospital123")
        self.stdout.write("    Email:    (see above list)")