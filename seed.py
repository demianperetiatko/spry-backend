"""
Seed script for local development — rich demo data.
Run: docker compose exec web python seed.py
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import sessionmanager

import src.modules.agenda.model  # noqa
import src.modules.feedback.model  # noqa
import src.modules.invitation.model  # noqa
import src.modules.super_admin.model  # noqa

from src.modules.enums import (
    CalendarAttendeeResponseStatusEnum,
    CalendarEventStatusEnum,
    CalendarSyncStatusEnum,
    CalendarTypeEnum,
    OrganizationCostPeriodEnum,
    OrganizationCostTypeEnum,
    OrganizationCostVisibilityEnum,
    OrganizationMemberRoleEnum,
    OrganizationMemberStatusEnum,
    OrganizationTeamMemberTypeEnum,
    UserStatusEnum,
)
from src.modules.calendar.models import (
    CalendarCacheMetadata,
    CalendarEvent,
    CalendarEventAttendee,
    OrganizationMemberCalendar,
    UserCalendar,
)
from src.modules.organization.model import Organization, OrganizationCurrency
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_team.model import OrganizationTeam, OrganizationTeamMember
from src.modules.user.model import User, UserAccessInfo


# ── People ────────────────────────────────────────────────────────────────────
USERS = [
    {"name": "Alice Kovalenko",  "email": "alice@spry.demo",   "role": OrganizationMemberRoleEnum.ADMIN,  "hourly": 95, "photo": "https://i.pravatar.cc/150?img=47"},
    {"name": "Bob Marchenko",    "email": "bob@spry.demo",     "role": OrganizationMemberRoleEnum.MEMBER, "hourly": 75, "photo": "https://i.pravatar.cc/150?img=12"},
    {"name": "Carol Sydorenko",  "email": "carol@spry.demo",   "role": OrganizationMemberRoleEnum.MEMBER, "hourly": 80, "photo": None},
    {"name": "Dan Petrenko",     "email": "dan@spry.demo",     "role": OrganizationMemberRoleEnum.MEMBER, "hourly": 70, "photo": "https://i.pravatar.cc/150?img=33"},
    {"name": "Eva Bondarenko",   "email": "eva@spry.demo",     "role": OrganizationMemberRoleEnum.MEMBER, "hourly": 65, "photo": None},
    {"name": "Frank Lysenko",    "email": "frank@spry.demo",   "role": OrganizationMemberRoleEnum.MEMBER, "hourly": 60, "photo": "https://i.pravatar.cc/150?img=52"},
    {"name": "Grace Tkachenko",  "email": "grace@spry.demo",   "role": OrganizationMemberRoleEnum.MEMBER, "hourly": 72, "photo": None},
    {"name": "Henry Shevchenko", "email": "henry@spry.demo",   "role": OrganizationMemberRoleEnum.MEMBER, "hourly": 68, "photo": "https://i.pravatar.cc/150?img=68"},
]

# ── Meeting templates: (title, min_attendees, max_attendees, durations_min) ──
MEETING_TYPES = [
    # 1-on-1s
    ("1:1 Alice & Bob",          2, 2, [30]),
    ("1:1 Alice & Carol",        2, 2, [30]),
    ("1:1 Alice & Dan",          2, 2, [30]),
    # Standups
    ("Engineering Standup",      3, 5, [15, 15, 15]),
    ("Design Standup",           2, 3, [15]),
    ("Marketing Standup",        3, 4, [15]),
    # Planning
    ("Sprint Planning",          4, 8, [90, 120]),
    ("Sprint Review",            4, 8, [60, 90]),
    ("Retrospective",            4, 6, [60]),
    ("Backlog Grooming",         3, 6, [60, 90]),
    # Reviews
    ("Design Review",            3, 5, [45, 60]),
    ("Code Review Session",      2, 4, [30, 60]),
    ("UX Research Readout",      3, 6, [60]),
    ("Product Demo",             4, 8, [45, 60]),
    # Strategy
    ("Quarterly OKR Review",     5, 8, [90, 120]),
    ("Roadmap Planning",         4, 8, [90]),
    ("Engineering All-Hands",    6, 8, [60]),
    ("Company All-Hands",        6, 8, [90, 120]),
    # Ops
    ("Marketing Sync",           3, 5, [30, 45]),
    ("Sales Pipeline Review",    3, 6, [60]),
    ("Customer Interview",       2, 3, [45, 60]),
    ("Client Onboarding",        2, 4, [60, 90]),
    ("Incident Postmortem",      3, 6, [60]),
    ("Budget Review",            3, 5, [60, 90]),
    ("Hiring Interview",         2, 3, [45, 60]),
]

TEAM_DEFS = {
    "Engineering": {"members": ["bob@spry.demo", "carol@spry.demo", "henry@spry.demo"], "manager": "bob@spry.demo"},
    "Design":      {"members": ["dan@spry.demo", "grace@spry.demo"],                    "manager": "dan@spry.demo"},
    "Marketing":   {"members": ["eva@spry.demo", "frank@spry.demo"],                    "manager": "eva@spry.demo"},
}

WORK_HOURS = [(9, 0), (10, 0), (11, 0), (13, 0), (14, 0), (15, 0), (16, 0)]
TZ = timezone.utc

AGENDAS = [
    "1. Status updates\n2. Blockers\n3. Next steps",
    "- Review last sprint goals\n- Demo completed features\n- Q&A",
    "Agenda:\n1. OKR progress review\n2. Risks & blockers\n3. Action items",
    "Topics:\n• Design feedback on new flows\n• Component library updates\n• Open questions",
    "1. Pipeline review\n2. Deal updates\n3. Forecast for next quarter",
    "• What went well\n• What can be improved\n• Action items for next sprint",
    "1. Engineering updates\n2. Upcoming releases\n3. Tech debt discussion",
    "Agenda:\n1. Marketing campaign results\n2. Content calendar review\n3. Budget discussion",
    "1. Customer feedback summary\n2. Product priorities\n3. Roadmap adjustments",
    "• Standup updates\n• Blockers\n• Focus for today",
]

# Recurring series: (title, weekday 0=Mon, hour, duration_min, attendees_emails_indices, rrule, freq_weeks)
# attendees_indices refer to USERS list indices
RECURRING_SERIES = [
    # Daily standups
    {
        "title": "Engineering Standup",
        "hour": 9, "minute": 30, "duration": 15,
        "attendees": [0, 1, 2, 6],
        "organizer": 1,  # Bob
        "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
        "freq_days": 1, "days": [0, 1, 2, 3, 4],
    },
    {
        "title": "Design Standup",
        "hour": 9, "minute": 45, "duration": 15,
        "attendees": [0, 3, 6],
        "organizer": 3,  # Dan
        "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR",
        "freq_days": None, "days": [0, 2, 4],
    },
    {
        "title": "Marketing Standup",
        "hour": 10, "minute": 0, "duration": 15,
        "attendees": [0, 4, 5],
        "organizer": 4,  # Eva
        "rrule": "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
        "freq_days": 1, "days": [0, 1, 2, 3, 4],
    },
    # Weekly 1:1s — Alice as organizer
    {
        "title": "1:1 with Bob",
        "hour": 11, "minute": 0, "duration": 30,
        "attendees": [0, 1],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY",
        "freq_days": 7, "days": [1],
    },
    {
        "title": "1:1 with Carol",
        "hour": 10, "minute": 0, "duration": 30,
        "attendees": [0, 2],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY",
        "freq_days": 7, "days": [3],
    },
    {
        "title": "1:1 with Dan",
        "hour": 14, "minute": 0, "duration": 30,
        "attendees": [0, 3],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY",
        "freq_days": 7, "days": [2],
    },
    {
        "title": "1:1 with Eva",
        "hour": 15, "minute": 0, "duration": 30,
        "attendees": [0, 4],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY",
        "freq_days": 7, "days": [4],
    },
    # Biweekly sprint ceremonies — Alice organizes
    {
        "title": "Sprint Planning",
        "hour": 10, "minute": 0, "duration": 120,
        "attendees": [0, 1, 2, 3, 6],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY;INTERVAL=2",
        "freq_days": 14, "days": [0],
    },
    {
        "title": "Sprint Review",
        "hour": 14, "minute": 0, "duration": 60,
        "attendees": [0, 1, 2, 3, 4, 6],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY;INTERVAL=2",
        "freq_days": 14, "days": [4],
    },
    {
        "title": "Retrospective",
        "hour": 16, "minute": 0, "duration": 60,
        "attendees": [0, 1, 2, 3, 6],
        "organizer": 1,  # Bob
        "rrule": "RRULE:FREQ=WEEKLY;INTERVAL=2",
        "freq_days": 14, "days": [4],
    },
    {
        "title": "Backlog Grooming",
        "hour": 13, "minute": 0, "duration": 60,
        "attendees": [0, 1, 2, 3],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY;INTERVAL=2",
        "freq_days": 14, "days": [2],
    },
    # Weekly team syncs
    {
        "title": "Marketing Weekly Sync",
        "hour": 11, "minute": 0, "duration": 45,
        "attendees": [0, 4, 5],
        "organizer": 4,  # Eva
        "rrule": "RRULE:FREQ=WEEKLY",
        "freq_days": 7, "days": [1],
    },
    {
        "title": "Product Roadmap Review",
        "hour": 13, "minute": 0, "duration": 60,
        "attendees": [0, 1, 3, 4],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY",
        "freq_days": 7, "days": [3],
    },
    # Monthly
    {
        "title": "Company All-Hands",
        "hour": 17, "minute": 0, "duration": 60,
        "attendees": [0, 1, 2, 3, 4, 5, 6, 7],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY;INTERVAL=4",
        "freq_days": 28, "days": [4],
    },
    {
        "title": "Quarterly OKR Review",
        "hour": 14, "minute": 0, "duration": 120,
        "attendees": [0, 1, 2, 3, 4, 5, 6, 7],
        "organizer": 0,  # Alice
        "rrule": "RRULE:FREQ=WEEKLY;INTERVAL=13",
        "freq_days": 91, "days": [1],
    },
]


def make_recurring_events(
    series: dict,
    weeks_back: int,
    weeks_ahead: int,
    calendar_by_email: dict,
    all_emails: list[str],
) -> list[tuple[CalendarEvent, list[CalendarEventAttendee]]]:
    results = []
    now = datetime.now(TZ)
    monday = now - timedelta(days=now.weekday())
    start_bound = monday - timedelta(weeks=weeks_back)
    end_bound = monday + timedelta(weeks=weeks_ahead)

    organizer_email = USERS[series["organizer"]]["email"]
    attendee_emails = [USERS[i]["email"] for i in series["attendees"]]
    recurring_id = f"recurring_{uuid.uuid4().hex}"
    freq_days = series.get("freq_days")
    target_days = series["days"]

    # iterate day by day through the range
    current = start_bound
    last_occurrence: dict[int, datetime] = {}  # weekday -> last date generated

    while current <= end_bound:
        weekday = current.weekday()
        if weekday in target_days:
            # check frequency (for biweekly etc.)
            skip = False
            if freq_days and freq_days > 7 and weekday in last_occurrence:
                days_since = (current - last_occurrence[weekday]).days
                if days_since < freq_days:
                    skip = True

            if not skip:
                start_dt = current.replace(
                    hour=series["hour"], minute=series["minute"],
                    second=0, microsecond=0, tzinfo=TZ,
                )
                end_dt = start_dt + timedelta(minutes=series["duration"])
                last_occurrence[weekday] = current

                # create event for each attendee's calendar
                for email in attendee_emails:
                    if email not in calendar_by_email:
                        continue
                    cal_id = calendar_by_email[email].id
                    event_instance_id = f"{recurring_id}_{current.strftime('%Y%m%d')}"

                    event = CalendarEvent(
                        id=uuid.uuid4(),
                        google_event_id=f"{event_instance_id}_{email[:4]}",
                        summary=series["title"],
                        start_datetime=start_dt,
                        end_datetime=end_dt,
                        start_timezone="Europe/Kyiv",
                        end_timezone="Europe/Kyiv",
                        status=CalendarEventStatusEnum.CONFIRMED,
                        organizer_email=organizer_email,
                        creator_email=organizer_email,
                        user_calendar_id=cal_id,
                        is_self_created=(email == organizer_email),
                        hangout_link=f"https://meet.google.com/rec-{uuid.uuid4().hex[:10]}",
                        recurring_event_id=recurring_id,
                        recurrence=[series["rrule"]],
                        description=random.choice(AGENDAS) if random.random() < 0.45 else None,
                        synced_at=datetime.now(TZ),
                    )

                    attendees = [
                        CalendarEventAttendee(
                            id=uuid.uuid4(),
                            calendar_event_id=event.id,
                            email=ae,
                            display_name=ae.split("@")[0].title(),
                            response_status=CalendarAttendeeResponseStatusEnum.ACCEPTED,
                            organizer=(ae == organizer_email),
                        )
                        for ae in attendee_emails
                    ]
                    results.append((event, attendees))

        current += timedelta(days=1)

    return results


def pick_attendees(meeting_type: dict, all_emails: list[str], organizer: str) -> list[str]:
    title, min_a, max_a, _ = meeting_type
    k = random.randint(min_a, min(max_a, len(all_emails)))
    pool = [e for e in all_emails if e != organizer]
    chosen = random.sample(pool, k=min(k - 1, len(pool)))
    return [organizer] + chosen


def make_week_events(
    week_start: datetime,
    calendar_id: uuid.UUID,
    organizer_email: str,
    all_emails: list[str],
    meetings_per_week: int,
) -> list[tuple[CalendarEvent, list[CalendarEventAttendee]]]:
    results = []
    used_slots: list[tuple[datetime, datetime]] = []

    candidates = random.sample(MEETING_TYPES, k=min(meetings_per_week + 5, len(MEETING_TYPES)))

    for meeting_type in candidates:
        if len(results) >= meetings_per_week:
            break

        title, _, _, durations = meeting_type
        duration = random.choice(durations)

        # pick a random weekday + hour
        day_offset = random.randint(0, 4)  # Mon–Fri
        hour, minute = random.choice(WORK_HOURS)
        base = week_start + timedelta(days=day_offset)
        start_dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=TZ)
        end_dt = start_dt + timedelta(minutes=duration)

        # avoid overlaps
        overlap = any(s < end_dt and e > start_dt for s, e in used_slots)
        if overlap:
            continue

        used_slots.append((start_dt, end_dt))
        attendees_emails = pick_attendees(meeting_type, all_emails, organizer_email)

        event = CalendarEvent(
            id=uuid.uuid4(),
            google_event_id=f"fake_{uuid.uuid4().hex}",
            summary=title,
            start_datetime=start_dt,
            end_datetime=end_dt,
            start_timezone="Europe/Kyiv",
            end_timezone="Europe/Kyiv",
            status=CalendarEventStatusEnum.CONFIRMED,
            organizer_email=organizer_email,
            creator_email=organizer_email,
            user_calendar_id=calendar_id,
            is_self_created=True,
            hangout_link=f"https://meet.google.com/fake-{uuid.uuid4().hex[:10]}",
            description=random.choice(AGENDAS) if random.random() < 0.4 else None,
            synced_at=datetime.now(TZ),
        )

        attendees = []
        for email in attendees_emails:
            resp = CalendarAttendeeResponseStatusEnum.ACCEPTED
            if email != organizer_email and random.random() < 0.1:
                resp = CalendarAttendeeResponseStatusEnum.TENTATIVE
            attendees.append(CalendarEventAttendee(
                id=uuid.uuid4(),
                calendar_event_id=event.id,
                email=email,
                display_name=email.split("@")[0].replace(".", " ").title(),
                response_status=resp,
                organizer=(email == organizer_email),
            ))

        results.append((event, attendees))

    return results


async def seed(session: AsyncSession) -> None:
    from sqlalchemy import text

    print("🧹 Clearing old data...")
    for table in [
        "calendar_event_attendees", "calendar_events", "calendar_cache_metadata",
        "organization_member_calendars", "user_calendars",
        "organization_team_members", "organization_teams",
        "organization_members", "users_access_info",
        "organizations", "organizations_currency",
    ]:
        await session.execute(text(f"DELETE FROM {table}"))
    await session.execute(text("DELETE FROM users WHERE email LIKE '%@spry.demo'"))
    await session.commit()

    print("🏢 Creating organization...")
    currency = OrganizationCurrency(
        id=uuid.uuid4(),
        cost_is_active=True,
        cost_type=OrganizationCostTypeEnum.AVERAGE,
        cost_period=OrganizationCostPeriodEnum.HOUR,
        cost_visibility=OrganizationCostVisibilityEnum.ALL,
        cost_avg=75,
    )
    session.add(currency)

    org = Organization(id=uuid.uuid4(), name="Spry Demo Corp", organizations_currency_id=currency.id)
    session.add(org)
    await session.flush()

    print("👥 Creating users, members & calendars...")
    all_emails = [u["email"] for u in USERS]
    member_by_email: dict[str, OrganizationMember] = {}
    calendar_by_email: dict[str, UserCalendar] = {}

    for u_data in USERS:
        user = User(
            id=uuid.uuid4(),
            name=u_data["name"],
            email=u_data["email"],
            photo_url=u_data.get("photo"),
            status=UserStatusEnum.ACTIVE,
        )
        session.add(user)
        await session.flush()

        access_info = UserAccessInfo(
            id=uuid.uuid4(),
            user_id=user.id,
            calendar_email=u_data["email"],
            type=CalendarTypeEnum.GOOGLE,
            access_token="demo_token",
            refresh_token="demo_refresh",
        )
        session.add(access_info)
        await session.flush()

        calendar = UserCalendar(
            id=uuid.uuid4(),
            user_access_info_id=access_info.id,
            calendar_email=u_data["email"],
            name=f"{u_data['name']}'s Calendar",
            is_primary=True,
            type=CalendarTypeEnum.GOOGLE,
        )
        session.add(calendar)
        await session.flush()

        session.add(CalendarCacheMetadata(
            id=uuid.uuid4(),
            user_calendar_id=calendar.id,
            timezone="Europe/Kyiv",
            sync_status=CalendarSyncStatusEnum.SUCCESS,
            last_sync_at=datetime.now(TZ),
        ))

        member = OrganizationMember(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org.id,
            status=OrganizationMemberStatusEnum.ACTIVE,
            role=u_data["role"],
            hourly_cost=u_data["hourly"],
        )
        session.add(member)
        await session.flush()

        session.add(OrganizationMemberCalendar(
            id=uuid.uuid4(),
            organization_member_id=member.id,
            user_calendar_id=calendar.id,
        ))

        member_by_email[u_data["email"]] = member
        calendar_by_email[u_data["email"]] = calendar

    print("📅 Creating recurring events (standups, 1:1s, sprints)...")
    total_events = 0
    for series in RECURRING_SERIES:
        pairs = make_recurring_events(series, weeks_back=8, weeks_ahead=3, calendar_by_email=calendar_by_email, all_emails=all_emails)
        for event, attendees in pairs:
            session.add(event)
            await session.flush()
            for att in attendees:
                att.calendar_event_id = event.id
                session.add(att)
            total_events += 1

    print(f"   Created ~{total_events} recurring event instances")

    print("📅 Creating one-off events (8 weeks back + 3 weeks ahead)...")
    now = datetime.now(TZ)
    monday = now - timedelta(days=now.weekday())
    oneoff_count = 0

    for week_offset in range(-8, 4):
        week_start = monday + timedelta(weeks=week_offset)
        base_load = random.choice([4, 5, 5, 6, 6, 7, 8])

        for u_data in USERS:
            email = u_data["email"]
            cal_id = calendar_by_email[email].id
            load = max(2, base_load + random.randint(-1, 1))
            # Alice organizes ~40% of her one-off meetings
            organizer = email if (email != "alice@spry.demo" or random.random() > 0.4) else "alice@spry.demo"
            events = make_week_events(week_start, cal_id, email, all_emails, load)
            for event, attendees in events:
                session.add(event)
                await session.flush()
                for att in attendees:
                    att.calendar_event_id = event.id
                    session.add(att)
                oneoff_count += 1

    total_events += oneoff_count
    print(f"   Created ~{oneoff_count} one-off events")

    print(f"   Created ~{total_events} events")

    print("🏷️  Creating teams...")
    for team_name, tdef in TEAM_DEFS.items():
        team = OrganizationTeam(id=uuid.uuid4(), name=team_name, organization_id=org.id)
        session.add(team)
        await session.flush()

        for email in tdef["members"]:
            if email not in member_by_email:
                continue
            session.add(OrganizationTeamMember(
                id=uuid.uuid4(),
                team_id=team.id,
                organization_member_id=member_by_email[email].id,
                type=(
                    OrganizationTeamMemberTypeEnum.MANAGER
                    if email == tdef["manager"]
                    else OrganizationTeamMemberTypeEnum.MEMBER
                ),
            ))

    await session.commit()

    print("\n✅ Seed complete!")
    print(f"   Org      : Spry Demo Corp")
    print(f"   Users    : {len(USERS)} ({', '.join(u['name'].split()[0] for u in USERS)})")
    print(f"   Teams    : {', '.join(TEAM_DEFS.keys())}")
    print(f"   Events   : ~{total_events} total (recurring + one-off) across 11 weeks")
    print(f"\n   👉 http://localhost:8000/auth/demo/?email=alice@spry.demo")


async def main() -> None:
    async with sessionmanager.session() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
