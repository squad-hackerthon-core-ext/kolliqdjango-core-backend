"""
Row-Level Security (RLS) utilities for enforcing data access control at the model level.

This module provides mixins and managers for automatically filtering querysets
to ensure users can only access records they own or are authorized to access.
"""

from django.db import models
from django.core.exceptions import PermissionDenied
from django.db.models import Q


class UserOwnedQuerySet(models.QuerySet):
    """
    QuerySet that automatically filters records by the current user.
    Use with UserOwnedManager.
    """

    def for_user(self, user):
        """Filter records accessible by the given user."""
        if user.is_staff or user.is_superuser:
            return self
        return self.filter(user=user)


class UserOwnedManager(models.Manager):
    """
    Manager for user-owned models. Automatically filters by current user
    when accessed through the manager.
    """

    def get_queryset(self):
        return UserOwnedQuerySet(self.model, using=self._db)

    def for_user(self, user):
        """Get records accessible by the given user."""
        return self.get_queryset().for_user(user)


class RelatedUserOwnedQuerySet(models.QuerySet):
    """
    QuerySet for models related to User through a foreign key (not necessarily named 'user').
    Filters by the related user field.
    """

    def for_user(self, user, user_field='user'):
        """Filter records accessible by the given user."""
        if user.is_staff or user.is_superuser:
            return self
        return self.filter(**{user_field: user})


class RelatedUserOwnedManager(models.Manager):
    """
    Manager for models with a related user field. Specify the field name
    in the manager instantiation.
    """

    def __init__(self, user_field='user'):
        super().__init__()
        self.user_field = user_field

    def get_queryset(self):
        return RelatedUserOwnedQuerySet(self.model, using=self._db)

    def for_user(self, user):
        """Get records accessible by the given user."""
        return self.get_queryset().for_user(user, self.user_field)


class UserOwnedModel(models.Model):
    """
    Abstract base class for models that are owned by a single user.
    Provides automatic row-level security filtering.
    """

    objects = UserOwnedManager()

    class Meta:
        abstract = True

    def is_accessible_by(self, user):
        """Check if the given user can access this record."""
        if user.is_staff or user.is_superuser:
            return True
        return self.user_id == user.id


class UserOrganizedModel(models.Model):
    """
    Abstract base class for models where multiple users (employer/worker/trader)
    can access the same record. Override can_access_record() for custom logic.
    """

    class Meta:
        abstract = True

    def can_access_record(self, user):
        """
        Override in child classes to define access rules.
        Return True if user can access this record, False otherwise.
        """
        if user.is_staff or user.is_superuser:
            return True
        return False


class RLSPermissionMixin:
    """
    Mixin for views/viewsets to enforce row-level security.
    Must be used with views that have a get_object() method.
    """

    def get_object(self):
        """Override to enforce RLS checks."""
        obj = super().get_object()
        
        # Check if object has RLS method
        if hasattr(obj, 'is_accessible_by'):
            if not obj.is_accessible_by(self.request.user):
                raise PermissionDenied("You do not have permission to access this resource.")
        elif hasattr(obj, 'can_access_record'):
            if not obj.can_access_record(self.request.user):
                raise PermissionDenied("You do not have permission to access this resource.")
        
        return obj

    def get_queryset(self):
        """Filter queryset for current user."""
        qs = super().get_queryset()
        
        # Apply RLS filtering if manager supports it
        if hasattr(qs, 'for_user'):
            return qs.for_user(self.request.user)
        
        return qs


class RLSSerializerMixin:
    """
    Mixin for serializers to enforce row-level security in DRF.
    """

    def validate(self, attrs):
        """Ensure user owns the object being updated."""
        instance = self.instance
        if instance and hasattr(instance, 'is_accessible_by'):
            if not instance.is_accessible_by(self.context['request'].user):
                raise PermissionDenied("You do not have permission to modify this resource.")
        return attrs
