from __future__ import annotations

import enum


class OrganizationCostPeriodEnum(str, enum.Enum):
    YEAR = "year"
    MONTH = "month"
    HOUR = "hour"


class OrganizationCostVisibilityEnum(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ALL = "all"


class OrganizationCostTypeEnum(str, enum.Enum):
    PER_MEMBER = "per_member"
    AVERAGE = "average"


class OrganizationMemberStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"


class OrganizationMemberRoleEnum(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class CalendarTypeEnum(str, enum.Enum):
    GOOGLE = "google"
    GOOGLE_SERVICE = "google_service"


class CalendarSyncStatusEnum(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


class CalendarEventStatusEnum(str, enum.Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class CalendarAttendeeResponseStatusEnum(str, enum.Enum):
    NEEDS_ACTION = "needsAction"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"


class CalendarSyncLogStatusEnum(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class CalendarSyncTypeEnum(str, enum.Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    EVENT_UPDATE = "event_update"


class OrganizationTeamMemberTypeEnum(str, enum.Enum):
    MEMBER = "member"
    MANAGER = "manager"


class InvitationStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"


class UserStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
