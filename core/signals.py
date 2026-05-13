# signals.py
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver
from .models import (
    User, PatientMedicalProfile, DonorMedicalProfile,
    PatientPriority, VitalSign, Alert, OrganMatching
)

# ==========================
# 1️⃣ Patient Priority Helper
# ==========================
def calculate_patient_priority(patient):
    score = 0
    if patient.chronic_diseases.exists():
        score += patient.chronic_diseases.count() * 10
    if hasattr(patient, 'patient_profile') and patient.patient_profile.organ_needed:
        score += 20

    level = 'low'
    if score >= 50:
        level = 'critical'
    elif score >= 30:
        level = 'high'
    elif score >= 10:
        level = 'medium'

    priority, created = PatientPriority.objects.get_or_create(
        patient=patient, defaults={"score": score, "level": level}
    )
    if not created:
        priority.score = score
        priority.level = level
        priority.save()


# ==========================
# 1a. Update Priority on Profile Save
# ==========================
@receiver(post_save, sender=PatientMedicalProfile)
def recalc_patient_priority(sender, instance, **kwargs):
    calculate_patient_priority(instance.patient)

# ==========================
# 1b. Update Priority on chronic_diseases change
# ==========================
@receiver(m2m_changed, sender=User.chronic_diseases.through)
def recalc_priority_on_disease_change(sender, instance, **kwargs):
    calculate_patient_priority(instance)


# ==========================
# 2️⃣ VitalSign Alerts + Priority
# ==========================
@receiver(post_save, sender=VitalSign)
def vital_sign_alert_and_priority(sender, instance, created, **kwargs):
    if not created:
        return

    surgery = instance.surgery_report.surgery
    patient = surgery.organ_matching.patient

    alerts = []
    critical = False
    score_delta = 0

    if instance.oxygen_saturation is not None and instance.oxygen_saturation < 92:
        alerts.append("انخفاض نسبة الأكسجين")
        critical = True
        score_delta += 15

    if instance.temperature_c is not None and instance.temperature_c >= 38:
        alerts.append("ارتفاع درجة الحرارة")
        score_delta += 10

    if instance.heart_rate is not None and instance.heart_rate > 120:
        alerts.append("ارتفاع معدل ضربات القلب")
        score_delta += 10

    if instance.blood_pressure and instance.blood_pressure > 160:
        alerts.append("ارتفاع ضغط الدم")
        score_delta += 10

    if alerts:
        Alert.objects.create(
            user=patient,
            message="تحذير بعد العملية: " + "، ".join(alerts),
            alert_type="critical" if critical else "medical"
        )

    # تحديث Patient Priority
    priority, _ = PatientPriority.objects.get_or_create(
        patient=patient, defaults={"score": 0, "level": "low"}
    )
    priority.score += score_delta
    if priority.score >= 70:
        priority.level = "critical"
    elif priority.score >= 40:
        priority.level = "high"
    elif priority.score >= 20:
        priority.level = "medium"
    else:
        priority.level = "low"
    priority.save()


# ==========================
# 3️⃣ Smart OrganMatching Signal
# ==========================
@receiver(post_save, sender=OrganMatching)
def smart_match_status_handler(sender, instance, **kwargs):
    """
    إدارة ذكية لكل تغييرات الـ Match:
    - التأكيد → تحديث حالات + Alerts
    - الإلغاء → إعادة الحالة + Alerts
    - تعديل → تحديث Alerts
    """
    patient = instance.patient
    donor = instance.donor
    hospital = getattr(patient, 'hospital', None)

    # الحالة الافتراضية لكل من المريض والمتبرع
    patient_status = 'قيد الانتظار'
    donor_status = 'قيد الانتظار'

    if instance.status == 'match_confirmed':
        patient_status = 'تأكيد'
        donor_status = 'محجوز'
        patient_alert = f"تم تأكيد حالتك بعد الحصول على Match للعضو: {instance.organ_type}"
        donor_alert = f"تم تأكيد عملية التبرع للعضو: {instance.organ_type}"
        hospital_alert = f"تم تأكيد Match للعضو {instance.organ_type} بين المريض {patient.first_name} {patient.last_name} والمتبرع {donor.first_name} {donor.last_name}"
        alert_type = 'medical'

    elif instance.status == 'match_cancelled':
        patient_status = 'قيد الانتظار'
        donor_status = 'قيد الانتظار'
        patient_alert = f"تم إلغاء Match للعضو: {instance.organ_type}"
        donor_alert = f"تم إلغاء Match للعضو: {instance.organ_type}"
        hospital_alert = f"تم إلغاء Match للعضو {instance.organ_type} بين المريض {patient.first_name} {patient.last_name} والمتبرع {donor.first_name} {donor.last_name}"
        alert_type = 'warning'

    else:
        # أي حالة أخرى → تحديث Alerts فقط
        patient_alert = f"تم تعديل Match للعضو: {instance.organ_type}"
        donor_alert = f"تم تعديل Match للعضو: {instance.organ_type}"
        hospital_alert = f"تم تعديل Match للعضو {instance.organ_type} بين المريض {patient.first_name} {patient.last_name} والمتبرع {donor.first_name} {donor.last_name}"
        alert_type = 'info'

    # تحديث المريض
    try:
        profile = patient.patient_profile
        profile.status = patient_status
        profile.save()
    except PatientMedicalProfile.DoesNotExist:
        pass

    # تحديث المتبرع
    try:
        donor_profile = donor.donor_profile
        donor_profile.status = donor_status
        donor_profile.save()
    except DonorMedicalProfile.DoesNotExist:
        pass

    # إرسال Alerts
    Alert.objects.create(user=patient, message=patient_alert, alert_type=alert_type)
    Alert.objects.create(user=donor, message=donor_alert, alert_type=alert_type)
    if hospital:
        Alert.objects.create(hospital=hospital, message=hospital_alert, alert_type='hospital')
