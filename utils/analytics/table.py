from sqlalchemy.orm import Session
from collections import defaultdict
from typing import List, Dict

from utils.analytics.calendar_stats import calculate_recurring_events_cost, calculate_recurring_events_duration, \
    calculate_total_events_duration, calculate_total_events_cost
from models.repositories.organization_repository import OrganizationTeamRepository, OrganizationTeamMemberRepository


def process_recurring_events(events: List[Dict], members) -> List[Dict]:
    recurring_events_summary = []

    grouped_events = defaultdict(list)
    for event in events:
        recurring_id = event.get("recurringEventId")
        if recurring_id:
            grouped_events[recurring_id].append(event)

    for recurring_id, event_group in grouped_events.items():
        recurring_events_summary.append({
            "id": recurring_id,
            "meeting_name": event_group[0].get('summary'),
            "attendees": len(event_group[0].get('attendees', [])),
            "cancellation_rate": 0,
            "total_time": calculate_recurring_events_duration(event_group),
            "total_cost": calculate_recurring_events_cost(event_group, members),
        })

    return recurring_events_summary


def process_teams_collab(events: List[Dict], organization_id, main_team_id, db):
    org_team_repository = OrganizationTeamRepository(db)
    org_team_member_repository = OrganizationTeamMemberRepository(db)

    main_team_members = org_team_member_repository.find_by_team_id(main_team_id)
    main_team_emails = [member.email for member in main_team_members]

    result = []

    for team in org_team_repository.find_by_organization_id(organization_id):
        if team.id == main_team_id:
            continue

        team_members = org_team_member_repository.find_by_team_id(team.id)
        team_member_emails = [member.email for member in team_members]

        combined_members = team_members + main_team_members
        event_collab = []

        for event in events:
            attendees = event.get('attendees', [])
            attendee_emails = [attendee.get('email') for attendee in attendees if 'email' in attendee]

            found = False
            for email in attendee_emails:
                if email in team_member_emails and email not in main_team_emails:
                    found = True
                    break

            if found:
                event_collab.append(event)

        info = {
            "id": team.id,
            "team_name": team.name,
            "manager_name": team.manager_name,
            "manager_email": team.manager_email,
            "manager_photo_url": team.manager_photo,
            "collab_time": calculate_total_events_duration(event_collab),
            "collab_cost": calculate_total_events_cost(event_collab, combined_members),
        }
        result.append(info)

    return result
