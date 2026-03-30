"""fix_calendar_events

Revision ID: 5868d25316df
Revises: 036785a13265
Create Date: 2026-03-30 18:05:32.901448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5868d25316df'
down_revision: Union[str, Sequence[str], None] = '036785a13265'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
   op.execute("TRUNCATE TABLE calendar_event_attendees")
   op.execute("TRUNCATE TABLE calendar_events CASCADE")
   op.execute("TRUNCATE TABLE calendar_cache_metadata")
   
   op.execute(
       "UPDATE calendar_cache_metadata SET sync_token = NULL, "
       "sync_status = 'SUCCESS', sync_error = NULL"
   )
   
   op.drop_constraint(
       "calendar_event_attendees_calendar_event_id_fkey",
       "calendar_event_attendees",
       type_="foreignkey",
   )
   
   op.drop_index("ix_calendar_event_attendees_calendar_event_id", table_name="calendar_event_attendees")
   
   op.drop_constraint("calendar_events_pkey", "calendar_events", type_="primary")
   
   op.alter_column(
       "calendar_events",
       "id",
       type_=sa.UUID(),
       existing_type=sa.String(255),
       postgresql_using="gen_random_uuid()",
       nullable=False,
   )
   
   op.create_primary_key("calendar_events_pkey", "calendar_events", ["id"])

   op.alter_column(
       "calendar_event_attendees",
       "calendar_event_id",
       type_=sa.UUID(),
       existing_type=sa.String(255),
       postgresql_using="gen_random_uuid()",
       nullable=False,
   )
   
   op.create_foreign_key(
       "calendar_event_attendees_calendar_event_id_fkey",
       "calendar_event_attendees",
       "calendar_events",
       ["calendar_event_id"],
       ["id"],
       ondelete="CASCADE",
   )
   
   op.create_index(
       "ix_calendar_event_attendees_calendar_event_id",
       "calendar_event_attendees",
       ["calendar_event_id"],
       unique=False,
   )


def downgrade() -> None:

   op.execute("TRUNCATE TABLE calendar_events CASCADE")
   op.drop_constraint(
       "calendar_event_attendees_calendar_event_id_fkey",
       "calendar_event_attendees",
       type_="foreignkey",
   )
   op.drop_index("ix_calendar_event_attendees_calendar_event_id", table_name="calendar_event_attendees")
   op.drop_constraint("calendar_events_pkey", "calendar_events", type_="primary")
   op.alter_column(
       "calendar_events",
       "id",
       type_=sa.String(255),
       existing_type=sa.UUID(),
       postgresql_using="id::text",
       nullable=False,
   )
   op.create_primary_key("calendar_events_pkey", "calendar_events", ["id"])
   op.alter_column(
       "calendar_event_attendees",
       "calendar_event_id",
       type_=sa.String(255),
       existing_type=sa.UUID(),
       postgresql_using="calendar_event_id::text",
       nullable=False,
   )
   op.create_foreign_key(
       "calendar_event_attendees_calendar_event_id_fkey",
       "calendar_event_attendees",
       "calendar_events",
       ["calendar_event_id"],
       ["id"],
       ondelete="CASCADE",
   )
   op.create_index(
       "ix_calendar_event_attendees_calendar_event_id",
       "calendar_event_attendees",
       ["calendar_event_id"],
       unique=False,
   )

