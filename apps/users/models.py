import uuid
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


class UserManager(BaseUserManager):
    """Custom manager — phone is the unique identifier, not username."""

    def create_user(self, phone, pin=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number is required.")
        user = self.model(phone=phone, **extra_fields)
        if pin:
            user.set_pin(pin)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, pin=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone, pin=pin, **extra_fields)


class User(AbstractBaseUser):
    """
    Custom user model.
    - Phone is the login identifier.
    - PIN is hashed (not password) — use set_pin / check_pin.
    - Token-based auth via DRF's TokenAuthentication.
    """

    # ------------------------------------------------------------------ #
    #  Choices
    # ------------------------------------------------------------------ #
    class Role(models.TextChoices):
        WORKER = 'worker', 'Worker'
        EMPLOYER = 'employer', 'Employer'
        ADMIN = 'admin', 'Admin'

    class Availability(models.TextChoices):
        FULL_DAY = 'full_day', 'Full Day'
        MORNING = 'morning', 'Morning'
        AFTERNOON = 'afternoon', 'Afternoon'
        EVENING = 'evening', 'Evening'
        WEEKENDS = 'weekends', 'Weekends'

    class Gender(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'
        OTHER = 'O', 'Other'

    # ------------------------------------------------------------------ #
    #  Core identity
    # ------------------------------------------------------------------ #
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True, db_index=True)
    pin = models.CharField(max_length=128, blank=True)  # Hashed PIN

    # ------------------------------------------------------------------ #
    #  Profile
    # ------------------------------------------------------------------ #
    full_name = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.WORKER)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    bvn = models.CharField(max_length=11, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # ------------------------------------------------------------------ #
    #  Location
    # ------------------------------------------------------------------ #
    location_area = models.CharField(max_length=255, blank=True, default='')
    location_city = models.CharField(max_length=255, blank=True, default='Lagos')
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    # ------------------------------------------------------------------ #
    #  Work profile
    # ------------------------------------------------------------------ #
    skills = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    has_vehicle = models.BooleanField(default=False)
    vehicle_type = models.CharField(max_length=50, blank=True, default='none')
    availability = models.CharField(
        max_length=20, choices=Availability.choices, default=Availability.FULL_DAY
    )
    trade_category = models.CharField(max_length=255, blank=True, default='')
    market_name = models.CharField(max_length=255, blank=True, default='')
    weekly_income_range = models.CharField(max_length=100, blank=True, default='')
    business_name = models.CharField(max_length=255, blank=True, default='')

    # ------------------------------------------------------------------ #
    #  Meta / acquisition
    # ------------------------------------------------------------------ #
    channel = models.CharField(max_length=50, blank=True, default='app')
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=False)

    # ------------------------------------------------------------------ #
    #  Squad virtual account
    # ------------------------------------------------------------------ #
    squad_account_number = models.CharField(max_length=20, blank=True, null=True)
    squad_bank_name = models.CharField(max_length=100, blank=True, null=True)
    squad_account_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[('active', 'Active'), ('failed', 'Failed'), ('pending', 'Pending')]
    )
    squad_account_created_at = models.DateTimeField(blank=True, null=True)

    # ------------------------------------------------------------------ #
    #  Timestamps
    # ------------------------------------------------------------------ #
    last_login = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ------------------------------------------------------------------ #
    #  Auth config
    # ------------------------------------------------------------------ #
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name or self.phone} ({self.role})"

    # ------------------------------------------------------------------ #
    #  PIN helpers  (NOT Django's password field)
    # ------------------------------------------------------------------ #
    def set_pin(self, raw_pin: str):
        """Hash and store a PIN."""
        self.pin = make_password(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        """Return True if raw_pin matches the stored hash."""
        return check_password(raw_pin, self.pin)

    # ------------------------------------------------------------------ #
    #  Django permission shim (required by AbstractBaseUser)
    # ------------------------------------------------------------------ #
    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser