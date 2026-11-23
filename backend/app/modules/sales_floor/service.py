"""Read-only aggregation for today's sales priorities and team activity.

UTC day boundaries match the existing follow-up categories. No source rows are
created or mutated. Installment promises are deliberately absent on this base.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.bookings.models import Booking, BookingStatus, VisitSlot
from app.modules.conversations.models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageSenderType,
)
from app.modules.follow_ups.models import FollowUp, FollowUpStatus
from app.modules.leads.models import Lead, LeadAssignment, LeadStatus
from app.modules.leads.schemas import normalize_email, normalize_phone
from app.modules.projects.models import Project
from app.modules.sales_floor.prioritization import WorkItem, prioritize
from app.modules.sales_floor.schemas import (
    ExecutiveActivity,
    FunnelAverage,
    FunnelCounts,
    MyDayItem,
    MyDayResponse,
    ProjectFunnel,
    RoutingCandidate,
    RoutingLead,
    RoutingSuggestionResponse,
    SourceCount,
    WarRoomResponse,
)
from app.modules.users.models import Role, RoleName, User

FIRST_RESPONSE_AGE = timedelta(hours=2)
CLOSED_LEAD_STATUSES = (
    LeadStatus.CONVERTED.value,
    LeadStatus.LOST.value,
    LeadStatus.NOT_INTERESTED.value,
)
PRIORITY_EXPLANATION = (
    "Deterministic urgency bands: overdue follow-ups (4000) > due-today visits (3000) "
    "> leads older than two hours without a first response and unanswered buyer messages (2000) "
    "> pending approvals requested by you (1000). Earlier recorded timestamps and UUIDs break ties. "
    "Promises are omitted because installment_promises does not exist on this base."
)
ROUTING_RULES = [
    "Only active sales executives in the lead's tenant are candidates.",
    "Current load is active assignments excluding converted, lost and not-interested leads; fewer loads score higher.",
    "Prior assignments (including ended ones) in this project add one point per lead, capped at ten.",
    "The lead language and contact methods are returned for review. No executive-language or channel capability is stored, so neither is scored or claimed as a match.",
    "Rank by score descending, current load ascending, then executive UUID; assignment remains a separate operation.",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _hours_between(now: datetime, value: datetime) -> float:
    return round(max(0.0, (_as_utc(now) - _as_utc(value)).total_seconds() / 3600), 1)


def _assignment_scope(tenant_id: UUID, executive_id: UUID | None):
    statement = select(LeadAssignment.lead_id).where(
        LeadAssignment.tenant_id == tenant_id,
        LeadAssignment.unassigned_at.is_(None),
    )
    if executive_id is not None:
        statement = statement.where(LeadAssignment.executive_id == executive_id)
    return statement


def _first_unanswered_buyer_messages(tenant_id: UUID):
    """Latest buyer message per conversation that has no later staff/assistant reply."""

    messages = (
        select(
            Message.conversation_id.label("conversation_id"),
            Message.sender_type.label("sender_type"),
            Message.created_at.label("created_at"),
            func.row_number()
            .over(partition_by=Message.conversation_id, order_by=(Message.created_at.desc(), Message.id.desc()))
            .label("position"),
        )
        .where(Message.tenant_id == tenant_id)
        .subquery("sales_floor_ranked_messages")
    )
    first = (
        select(messages.c.conversation_id, messages.c.sender_type, messages.c.created_at)
        .where(messages.c.position == 1)
        .subquery("sales_floor_latest_messages")
    )
    return select(first.c.conversation_id, first.c.created_at.label("due_at")).where(
        first.c.sender_type == MessageSenderType.BUYER.value
    ).subquery("sales_floor_unanswered_messages")


def _my_day_items(
    session: Session, *, actor: User, now: datetime
) -> list[MyDayItem]:
    tenant_id = actor.tenant_id
    is_personal = actor.role.name == RoleName.SALES_EXECUTIVE.value
    executive_id = actor.id if is_personal else None
    start = _as_utc(now).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    assigned_leads = _assignment_scope(tenant_id, executive_id)
    items: list[WorkItem] = []

    follow_ups = session.execute(
        select(FollowUp, Lead.full_name, Project.name)
        .join(Lead, (Lead.id == FollowUp.lead_id) & (Lead.tenant_id == tenant_id))
        .join(Project, (Project.id == FollowUp.project_id) & (Project.tenant_id == tenant_id))
        .where(
            FollowUp.tenant_id == tenant_id,
            FollowUp.status == FollowUpStatus.PENDING.value,
            FollowUp.scheduled_at < end,
            or_(FollowUp.executive_id == executive_id, FollowUp.lead_id.in_(assigned_leads))
            if executive_id is not None else FollowUp.id.is_not(None),
        )
    ).all()
    for follow_up, buyer_name, project_name in follow_ups:
        overdue = _as_utc(follow_up.scheduled_at) < start
        items.append(
            WorkItem(
                kind="FOLLOW_UP", id=follow_up.id,
                urgency="OVERDUE" if overdue else "DUE_TODAY",
                title=f"{follow_up.type.title()} follow-up with {buyer_name}",
                reason=f"Pending {follow_up.priority.lower()} priority follow-up; {'overdue' if overdue else 'due today'} at {_as_utc(follow_up.scheduled_at).isoformat()}.",
                due_at=follow_up.scheduled_at, waiting_hours=_hours_between(now, follow_up.scheduled_at),
                lead_id=follow_up.lead_id, project_id=follow_up.project_id, project_name=project_name,
            )
        )

    visits = session.execute(
        select(Booking, VisitSlot.start_time, Lead.full_name, Project.name)
        .join(VisitSlot, (VisitSlot.id == Booking.slot_id) & (VisitSlot.tenant_id == tenant_id))
        .join(Lead, (Lead.id == Booking.lead_id) & (Lead.tenant_id == tenant_id))
        .join(Project, (Project.id == Booking.project_id) & (Project.tenant_id == tenant_id))
        .where(
            Booking.tenant_id == tenant_id,
            Booking.status.in_((BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value)),
            VisitSlot.start_time >= start,
            VisitSlot.start_time < end,
            Booking.executive_id == executive_id if executive_id is not None else Booking.id.is_not(None),
        )
    ).all()
    for booking, due_at, buyer_name, project_name in visits:
        items.append(
            WorkItem(
                kind="VISIT", id=booking.id, urgency="DUE_TODAY",
                title=f"Site visit with {buyer_name}",
                reason=f"Confirmed or pending site visit scheduled today at {_as_utc(due_at).isoformat()}.",
                due_at=due_at, waiting_hours=_hours_between(now, due_at),
                lead_id=booking.lead_id, project_id=booking.project_id, project_name=project_name,
            )
        )

    activity = (
        select(Message.id)
        .join(Conversation, (Conversation.id == Message.conversation_id) & (Conversation.tenant_id == tenant_id))
        .where(Message.tenant_id == tenant_id, Conversation.lead_id == Lead.id)
    )
    responded = activity.union(
        select(FollowUp.id).where(FollowUp.tenant_id == tenant_id, FollowUp.lead_id == Lead.id),
        select(Booking.id).where(Booking.tenant_id == tenant_id, Booking.lead_id == Lead.id),
        select(Lead.id).where(Lead.status != LeadStatus.NEW.value),
    ).exists()
    latest_buyer_messages = _first_unanswered_buyer_messages(tenant_id)
    awaiting_conversation_reply = (
        select(latest_buyer_messages.c.conversation_id)
        .join(
            Conversation,
            (Conversation.id == latest_buyer_messages.c.conversation_id)
            & (Conversation.tenant_id == tenant_id),
        )
        .where(
            Conversation.lead_id == Lead.id,
            Conversation.status == ConversationStatus.ACTIVE.value,
        )
        .exists()
    )
    first_response = session.execute(
        select(Lead, Project.name)
        .join(Project, (Project.id == Lead.project_id) & (Project.tenant_id == tenant_id))
        .where(
            Lead.tenant_id == tenant_id,
            Lead.id.in_(assigned_leads),
            Lead.created_at < now - FIRST_RESPONSE_AGE,
            ~responded,
            ~awaiting_conversation_reply,
        )
    ).all()
    for lead, project_name in first_response:
        items.append(
            WorkItem(
                kind="FIRST_RESPONSE", id=lead.id, urgency="AGING_SILENCE",
                title=f"First response to {lead.full_name}",
                reason=f"Assigned lead is more than two hours old with no conversation activity, follow-up, visit or status change recorded.",
                due_at=lead.created_at, waiting_hours=_hours_between(now, lead.created_at),
                lead_id=lead.id, project_id=lead.project_id, project_name=project_name,
            )
        )

    unanswered = _first_unanswered_buyer_messages(tenant_id)
    conversations = session.execute(
        select(Conversation, unanswered.c.due_at, Lead.full_name, Project.name)
        .join(unanswered, unanswered.c.conversation_id == Conversation.id)
        .join(Lead, (Lead.id == Conversation.lead_id) & (Lead.tenant_id == tenant_id))
        .join(Project, (Project.id == Conversation.project_id) & (Project.tenant_id == tenant_id))
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.status == ConversationStatus.ACTIVE.value,
            Conversation.lead_id.in_(assigned_leads),
        )
    ).all()
    for conversation, due_at, buyer_name, project_name in conversations:
        items.append(
            WorkItem(
                kind="CONVERSATION", id=conversation.id, urgency="AGING_SILENCE",
                title=f"Reply to {buyer_name}",
                reason="Latest message is from the buyer; no later staff or assistant reply is recorded.",
                due_at=due_at, waiting_hours=_hours_between(now, due_at),
                lead_id=conversation.lead_id, project_id=conversation.project_id, project_name=project_name,
            )
        )

    approvals = session.scalars(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == tenant_id,
            ApprovalRequest.status == ApprovalStatus.PENDING.value,
            ApprovalRequest.requested_by_id.is_not(None) if executive_id is None
            else ApprovalRequest.requested_by_id == executive_id,
        )
    ).all()
    for approval in approvals:
        items.append(
            WorkItem(
                kind="APPROVAL", id=approval.id, urgency="PENDING_APPROVAL",
                title=f"{approval.request_type.replace('_', ' ').title()} approval pending",
                reason=f"Requested {approval.request_type} approval is still pending; requested at {_as_utc(approval.created_at).isoformat()}.",
                due_at=approval.created_at, waiting_hours=_hours_between(now, approval.created_at),
            )
        )

    links = {
        "FOLLOW_UP": lambda item: f"/sales/follow-ups?lead_id={item.lead_id}",
        "VISIT": lambda item: f"/sales/visits?lead_id={item.lead_id}",
        "FIRST_RESPONSE": lambda item: f"/sales/leads?lead_id={item.lead_id}",
        "CONVERSATION": lambda item: f"/sales/conversations?lead_id={item.lead_id}",
        "APPROVAL": lambda item: f"/admin/approvals?request_id={item.id}" if not is_personal
        else f"/sales/myday?approval_id={item.id}",
    }
    return [
        MyDayItem(**item.__dict__, priority_score=item.priority_score, link=links[item.kind](item))
        for item in prioritize(items)
    ]


def get_my_day(session: Session, *, actor: User) -> MyDayResponse:
    now = _now()
    items = _my_day_items(session, actor=actor, now=now)
    return MyDayResponse(
        date=now.date(),
        scope="PERSONAL" if actor.role.name == RoleName.SALES_EXECUTIVE.value else "TEAM",
        items=items,
        counts=dict(Counter(item.kind for item in items)),
        priority_explanation=PRIORITY_EXPLANATION,
        promises_included=False,
    )


def _count(session: Session, statement) -> int:
    return int(session.scalar(statement) or 0)


def get_war_room(session: Session, *, actor: User) -> WarRoomResponse:
    tenant_id = actor.tenant_id
    now = _now()
    start = _as_utc(now).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    comparison_start = start - timedelta(days=6)
    executives = session.scalars(
        select(User).join(Role, Role.id == User.role_id).where(
            User.tenant_id == tenant_id,
            Role.name == RoleName.SALES_EXECUTIVE.value,
            User.is_active.is_(True),
        ).order_by(User.full_name, User.id)
    ).all()
    activity = []
    for executive in executives:
        activity.append(ExecutiveActivity(
            executive_id=executive.id,
            full_name=executive.full_name,
            visits_today=_count(session, select(func.count(Booking.id)).select_from(Booking).join(
                VisitSlot, (VisitSlot.id == Booking.slot_id) & (VisitSlot.tenant_id == tenant_id)
            ).where(
                Booking.tenant_id == tenant_id, Booking.executive_id == executive.id,
                Booking.status.in_((BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value)),
                VisitSlot.start_time >= start, VisitSlot.start_time < end,
            )),
            new_leads=_count(session, select(func.count(Lead.id)).join(
                LeadAssignment, (LeadAssignment.lead_id == Lead.id) & (LeadAssignment.tenant_id == tenant_id)
            ).where(
                Lead.tenant_id == tenant_id, LeadAssignment.executive_id == executive.id,
                LeadAssignment.assigned_at >= start, LeadAssignment.assigned_at < end,
                Lead.created_at >= start, Lead.created_at < end,
            )),
            bookings_created=_count(session, select(func.count(Booking.id)).where(
                Booking.tenant_id == tenant_id, Booking.executive_id == executive.id,
                Booking.status != BookingStatus.CANCELLED.value,
                Booking.created_at >= start, Booking.created_at < end,
            )),
        ))

    sources = session.execute(
        select(Lead.source, func.count(Lead.id)).where(
            Lead.tenant_id == tenant_id, Lead.created_at >= start, Lead.created_at < end,
        ).group_by(Lead.source).order_by(Lead.source)
    ).all()
    visits_today = _count(session, select(func.count(Booking.id)).select_from(Booking).join(
        VisitSlot, (VisitSlot.id == Booking.slot_id) & (VisitSlot.tenant_id == tenant_id)
    ).where(
        Booking.tenant_id == tenant_id,
        Booking.status.in_((BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value)),
        VisitSlot.start_time >= start, VisitSlot.start_time < end,
    ))
    bookings_created = _count(session, select(func.count(Booking.id)).where(
        Booking.tenant_id == tenant_id, Booking.status != BookingStatus.CANCELLED.value,
        Booking.created_at >= start, Booking.created_at < end,
    ))
    pending_discounts = _count(session, select(func.count(ApprovalRequest.id)).where(
        ApprovalRequest.tenant_id == tenant_id,
        ApprovalRequest.request_type == "DISCOUNT",
        ApprovalRequest.status == ApprovalStatus.PENDING.value,
    ))
    unassigned = _count(session, select(func.count(Lead.id)).where(
        Lead.tenant_id == tenant_id,
        Lead.status.not_in(CLOSED_LEAD_STATUSES),
        ~select(LeadAssignment.id).where(
            LeadAssignment.tenant_id == tenant_id,
            LeadAssignment.lead_id == Lead.id,
            LeadAssignment.unassigned_at.is_(None),
        ).exists(),
    ))

    today_by_project: dict[UUID, dict[str, int]] = defaultdict(lambda: {"enquiries": 0, "visits": 0, "bookings": 0})
    comparison_by_project: dict[UUID, dict[str, int]] = defaultdict(lambda: {"enquiries": 0, "visits": 0, "bookings": 0})
    lead_rows = session.execute(
        select(Lead.project_id, Lead.created_at).where(
            Lead.tenant_id == tenant_id, Lead.created_at >= comparison_start, Lead.created_at < end,
        )
    ).all()
    booking_rows = session.execute(
        select(Booking.project_id, Booking.created_at, VisitSlot.start_time).join(
            VisitSlot, (VisitSlot.id == Booking.slot_id) & (VisitSlot.tenant_id == tenant_id)
        ).where(
            Booking.tenant_id == tenant_id,
            Booking.status != BookingStatus.CANCELLED.value,
            or_(
                (Booking.created_at >= comparison_start) & (Booking.created_at < end),
                (VisitSlot.start_time >= comparison_start) & (VisitSlot.start_time < end),
            ),
        )
    ).all()
    for project_id, created_at in lead_rows:
        comparison_by_project[project_id]["enquiries"] += 1
        if _as_utc(created_at) >= start:
            today_by_project[project_id]["enquiries"] += 1
    for project_id, created_at, visit_at in booking_rows:
        created_at_utc = _as_utc(created_at)
        visit_at_utc = _as_utc(visit_at)
        if comparison_start <= created_at_utc < end:
            comparison_by_project[project_id]["bookings"] += 1
        if comparison_start <= visit_at_utc < end:
            comparison_by_project[project_id]["visits"] += 1
        if created_at_utc >= start:
            today_by_project[project_id]["bookings"] += 1
        if visit_at_utc >= start:
            today_by_project[project_id]["visits"] += 1

    projects = session.execute(
        select(Project).where(
            Project.tenant_id == tenant_id,
            Project.id.in_(set(today_by_project) | set(comparison_by_project)),
        ).order_by(Project.name, Project.id)
    ).scalars().all()
    funnels = []
    for project in projects:
        today = today_by_project[project.id]
        comparison = comparison_by_project[project.id]
        funnels.append(ProjectFunnel(
            project_id=project.id, project_name=project.name,
            today=FunnelCounts(**today),
            seven_day_average=FunnelAverage(**{
                key: round(comparison[key] / 7, 2) for key in ("enquiries", "visits", "bookings")
            }),
        ))

    return WarRoomResponse(
        date=now.date(), comparison_start=comparison_start,
        executive_activity=activity,
        new_leads_by_source=[SourceCount(source=source, count=count) for source, count in sources],
        new_leads_total=sum(count for _, count in sources),
        visits_today=visits_today, bookings_created_today=bookings_created,
        pending_discount_approvals=pending_discounts, unassigned_leads_count=unassigned,
        project_funnels=funnels,
    )


def suggest_lead_routing(
    session: Session, *, actor: User, lead_id: UUID
) -> RoutingSuggestionResponse:
    """Rank active executives, without persisting an assignment or guessing skills."""

    lead = session.scalar(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == actor.tenant_id))
    if lead is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Lead not found.")
    executives = session.scalars(
        select(User).join(Role, Role.id == User.role_id).where(
            User.tenant_id == actor.tenant_id,
            User.is_active.is_(True),
            Role.name == RoleName.SALES_EXECUTIVE.value,
        ).order_by(User.id)
    ).all()
    current_load = Counter()
    project_history: dict[UUID, set[UUID]] = defaultdict(set)
    for executive_id, project_id, status, active, assigned_lead_id in session.execute(
        select(LeadAssignment.executive_id, Lead.project_id, Lead.status, LeadAssignment.unassigned_at.is_(None), Lead.id).join(
            Lead, (Lead.id == LeadAssignment.lead_id) & (Lead.tenant_id == actor.tenant_id)
        ).where(LeadAssignment.tenant_id == actor.tenant_id)
    ).all():
        if active and status not in CLOSED_LEAD_STATUSES:
            current_load[executive_id] += 1
        if project_id == lead.project_id:
            project_history[executive_id].add(assigned_lead_id)
    candidates = []
    for executive in executives:
        load = current_load[executive.id]
        history = min(len(project_history[executive.id]), 10)
        candidates.append(RoutingCandidate(
            executive_id=executive.id, full_name=executive.full_name,
            current_open_leads=load, prior_project_leads=history,
            score=history - load,
            reasons=[
                f"{load} current open assigned lead(s); lower load ranks higher",
                f"{len(project_history[executive.id])} prior assigned lead(s) in this project (familiarity contribution capped at 10)",
            ],
        ))
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.current_open_leads, str(candidate.executive_id)))
    methods = [kind for kind, value in (("email", lead.email), ("phone", lead.phone)) if value]
    return RoutingSuggestionResponse(
        lead=RoutingLead(id=lead.id, project_id=lead.project_id, language=lead.language, contact_methods=methods),
        candidates=candidates,
        language_matching_available=False,
        rules=ROUTING_RULES,
    )
