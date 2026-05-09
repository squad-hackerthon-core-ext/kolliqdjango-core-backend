from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import uuid


class UserManager(BaseUserManager):
    def create_user(self, phone, **extra_fields):
        if not phone:
            raise ValueError('Phone number is required')
        user = self.model(phone=phone, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        WORKER = 'worker', 'Worker'
        TRADER = 'trader', 'Trader'
        EMPLOYER = 'employer', 'Employer'

    class Skill(models.TextChoices):
        DELIVERY = 'delivery', 'Delivery/Dispatch'
        COOKING = 'cooking', 'Cooking/Catering'
        CONSTRUCTION = 'construction', 'Construction/Labour'
        MARKET = 'market', 'Market Assistant'
        CLEANING = 'cleaning', 'Cleaning'
        SECURITY = 'security', 'Security'
        TEACHING = 'teaching', 'Teaching/Tutoring'
        OTHER = 'other', 'Other'

    class Availability(models.TextChoices):
        MORNINGS = 'mornings', 'Mornings'
        AFTERNOONS = 'afternoons', 'Afternoons'
        EVENINGS = 'evenings', 'Evenings'
        FULL_DAY = 'full_day', 'Full Day'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.WORKER)

    # Location
    location_area = models.CharField(max_length=200, blank=True)
    location_city = models.CharField(max_length=100, blank=True, default='Lagos')
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Worker-specific
    skills = models.JSONField(default=list, blank=True)          # list of Skill values
    languages = models.JSONField(default=list, blank=True)       # ['english', 'yoruba', ...]
    has_vehicle = models.BooleanField(default=False)
    vehicle_type = models.CharField(
        max_length=20,
        choices=[('bike', 'Bike'), ('car', 'Car'), ('none', 'None')],
        default='none'
    )
    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.FULL_DAY
    )

    # Trader-specific
    trade_category = models.CharField(max_length=100, blank=True)
    market_name = models.CharField(max_length=200, blank=True)
    weekly_income_range = models.CharField(max_length=50, blank=True)

    # Employer-specific
    business_name = models.CharField(max_length=200, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.TextField(blank=True)

    # Onboarding
    onboarding_complete = models.BooleanField(default=False)
    channel = models.CharField(
        max_length=20,
        choices=[('app', 'App'), ('ussd', 'USSD'), ('whatsapp', 'WhatsApp')],
        default='app'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['role']),
            models.Index(fields=['location_city']),
        ]

    def __str__(self):
        return f"{self.full_name or 'Unknown'} ({self.phone}) — {self.role}"

    @property
    def display_name(self):
        return self.full_name or self.phone

    @property
    def primary_skill(self):
        return self.skills[0] if self.skills else None