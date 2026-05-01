from src.modules.agenda.model import AgendaBeta  # noqa: F401
from src.modules.calendar.models import (  # noqa: F401
    CalendarCacheMetadata,
    CalendarEvent,
    CalendarEventAttendee,
    OrganizationMemberCalendar,
    UserCalendar,
)
from src.modules.feedback.model import Feedback  # noqa: F401
from src.modules.invitation.model import Invitation  # noqa: F401
from src.modules.organization.model import (  # noqa: F401
    Organization,
    OrganizationCurrency,
)
from src.modules.organization_member.model import OrganizationMember  # noqa: F401
from src.modules.organization_team.model import (  # noqa: F401
    OrganizationTeam,
    OrganizationTeamMember,
)
from src.modules.super_admin.model import SuperAdmin  # noqa: F401
from src.modules.user.model import User  # noqa: F401


def compile_orm() -> None:
    pass
