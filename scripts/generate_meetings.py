import random
import uuid
from datetime import datetime, timedelta, time
import requests
from sqlalchemy import create_engine, select, Table, Column, Text, DateTime, Enum, MetaData
from sqlalchemy.dialects.postgresql import UUID

DATABASE_URL = 'postgresql://spry:Ox[NGX>E4z1yGQpu@35.184.50.5/spry_v2'
engine = create_engine(DATABASE_URL)
metadata = MetaData()

organization_members = Table(
    'organization_members', metadata,
    Column('id', UUID(as_uuid=True)),
    Column('name', Text),
    Column('email', Text),
)

organization_member_calendars = Table(
    'organization_member_calendars', metadata,
    Column('id', UUID(as_uuid=True)),
    Column('member_id', UUID(as_uuid=True)),
    Column('calendar_email', Text),
    Column('access_token', Text),
    Column('access_token_expiry', DateTime),
    Column('refresh_token', Text),
    Column('type', Enum('GOOGLE', 'GOOGLE_SERVICES', name='calendartypeenum')),
)

WORK_START = time(9, 0)
WORK_END = time(18, 0)
MEETING_MINUTES = [30, 60]
COST_RANGE = (15, 50)

SUMMARY_TEMPLATES = [
    "{team} Weekly Sync",
    "{team} Standup",
    "{team} Sprint Planning",
    "{team} Retrospective",
    "{team} Demo Review",
    "Cross-team Strategy",
    "Client Discussion",
    "Project Kickoff - {team}",
    "One-on-One",
    "Brainstorming Session",
]

def random_meeting_time():
    hour = random.randint(WORK_START.hour, WORK_END.hour - 1)
    minute = random.choice([0, 30])
    return time(hour, minute)

def random_meeting_duration():
    return timedelta(minutes=random.choice(MEETING_MINUTES))

def random_date_range():
    start = datetime.utcnow() - timedelta(days=60)
    end = datetime.utcnow() + timedelta(days=60)
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

def generate_recurrence():
    return ["RRULE:FREQ=WEEKLY;COUNT=8"] if random.random() < 0.8 else None

def generate_summary(team: str, cross_team=False, external=False):
    if cross_team:
        return random.choice([
            "Cross-team Strategy",
            "Cross-team Planning",
            "Cross-team Sync",
        ])
    if external:
        return random.choice([
            "Client Discussion",
            "Partner Call",
            "External Sync",
        ])
    template = random.choice(SUMMARY_TEMPLATES)
    return template.format(team=team)

def create_google_calendar_event(
    access_token: str,
    summary: str,
    start_time: datetime,
    end_time: datetime,
    calendar_id: str = "primary",
    time_zone: str = "UTC",
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    recurrence: list[str] | None = None,
    create_google_meet: bool = False
) -> dict:
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events?conferenceDataVersion=1"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    event_data = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": time_zone
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": time_zone
        },
    }

    if attendees:
        event_data["attendees"] = [{"email": email} for email in attendees]

    if recurrence:
        event_data["recurrence"] = recurrence

    if create_google_meet:
        event_data["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet-{datetime.utcnow().timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"}
            }
        }

    response = requests.post(url, headers=headers, json=event_data)

    if response.status_code in (200, 201):
        return response.json()
    else:
        raise Exception(f"Failed to create event: {response.status_code} - {response.text}")



def generate_meetings(team_emails_dict, total_meetings=100):
    with engine.connect() as conn:
        team_calendars = {}
        for team_name, emails in team_emails_dict.items():
            result = conn.execute(
                select([
                    organization_member_calendars.c.id,
                    organization_member_calendars.c.member_id,
                    organization_member_calendars.c.calendar_email,
                    organization_member_calendars.c.access_token
                ]).where(organization_member_calendars.c.calendar_email.in_(emails))
            ).fetchall()
            team_calendars[team_name] = result

        all_calendars = [c for lst in team_calendars.values() for c in lst]

        for _ in range(total_meetings):
            organizer_team = random.choice(list(team_calendars.keys()))
            organizer = random.choice(team_calendars[organizer_team])
            cross_team = False
            external = False

            if random.random() < 0.3 and len(team_calendars) > 1:
                cross_team = True
                participants = []
                for t in random.sample(list(team_calendars.keys()), 2):
                    participants.extend(random.sample(team_calendars[t], k=1))
            else:
                participants = random.sample(team_calendars[organizer_team], k=random.randint(1, len(team_calendars[organizer_team]) - 1))

            participants = [p for p in participants if p != organizer]
            if not participants:
                continue

            date = random_date_range()
            start_dt = datetime.combine(date.date(), random_meeting_time())
            end_dt = start_dt + random_meeting_duration()
            if start_dt.weekday() >= 5:
                continue

            recurrence = generate_recurrence()
            summary = generate_summary(organizer_team, cross_team=cross_team, external=external)
            attendees = [p.calendar_email for p in participants]

            if random.random() < 0.05:
                external = True
                attendees.append(f"external{random.randint(1,100)}@gmail.com")
                summary = generate_summary(organizer_team, external=True)

            print(f"[INFO] {summary} | Organizer={organizer.calendar_email} | Attendees={len(attendees)} | Recurring={'Yes' if recurrence else 'No'}")

            create_google_calendar_event(
                organizer.access_token,
                summary=summary,
                start_time=start_dt,
                end_time=end_dt,
                attendees=attendees,
                recurrence=recurrence,
            )
            break

if __name__ == "__main__":
    team_emails_dict = {
        "Team 1": [
            "demo3-675@spry-398908.iam.gserviceaccount.com",
            "demo2-619@spry-398908.iam.gserviceaccount.com",
            "demo1-576@spry-398908.iam.gserviceaccount.com",
        ],
        "Team 2": [
            "demo8-455@spry-398908.iam.gserviceaccount.com",
            "demo6-150@spry-398908.iam.gserviceaccount.com",
            "demo4-832@spry-398908.iam.gserviceaccount.com",
            "demo7-895@spry-398908.iam.gserviceaccount.com",
            "demo5-483@spry-398908.iam.gserviceaccount.com",
        ],
        "Team 3": [
            "demo9-606@spry-398908.iam.gserviceaccount.com",
            "demo10@spry-398908.iam.gserviceaccount.com",
        ],
    }
    generate_meetings(team_emails_dict, total_meetings=120)
