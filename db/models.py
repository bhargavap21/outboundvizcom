from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, JSON, Enum
)
from sqlalchemy.orm import DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class SignalType(str, enum.Enum):
    new_hire = "new_hire"
    case_study = "case_study"
    client_win = "client_win"
    portfolio_update = "portfolio_update"


class SignalSource(str, enum.Enum):
    linkedin_job = "linkedin_job"
    linkedin_post = "linkedin_post"
    behance = "behance"
    artstation = "artstation"
    trade_press = "trade_press"
    google_news = "google_news"


class LeadStatus(str, enum.Enum):
    new = "new"
    watchlist = "watchlist"
    researching = "researching"
    content_ready = "content_ready"
    in_sequence = "in_sequence"
    warm = "warm"
    exhausted = "exhausted"
    suppressed = "suppressed"


class OutreachChannel(str, enum.Enum):
    email = "email"
    linkedin_connect = "linkedin_connect"
    linkedin_dm = "linkedin_dm"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    agency_name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    signal_type = Column(String, nullable=False)
    vertical_hint = Column(String)
    url = Column(String, unique=True)
    raw_text = Column(Text)
    detected_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    agency_name = Column(String, nullable=False)
    website = Column(String)
    linkedin_url = Column(String)
    contact_name = Column(String)
    contact_linkedin = Column(String)
    contact_email = Column(String)

    vertical = Column(String)
    team_size = Column(Integer)
    tool_stack = Column(JSON)   # list of tools found
    score = Column(Float)
    status = Column(String, default=LeadStatus.new)

    trigger_signal_id = Column(Integer)
    trigger_summary = Column(Text)
    agency_brief = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contacted_at = Column(DateTime)
    cooldown_until = Column(DateTime)


class OutreachEvent(Base):
    __tablename__ = "outreach_events"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, nullable=False)
    channel = Column(String, nullable=False)
    sequence_step = Column(Integer, default=1)
    subject = Column(String)
    body = Column(Text)
    variant = Column(String)    # A/B variant label

    sent_at = Column(DateTime)
    opened_at = Column(DateTime)
    replied_at = Column(DateTime)
    clicked_at = Column(DateTime)
    bounced = Column(Boolean, default=False)
    unsubscribed = Column(Boolean, default=False)

    response_type = Column(String)   # positive, objection, unsubscribe, no_response, bounce
    response_text = Column(Text)


class AgencyList(Base):
    """Static seed list of known boutique ID agencies."""
    __tablename__ = "agency_list"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    website = Column(String)
    linkedin_url = Column(String)
    country = Column(String)
    verticals = Column(JSON)
    is_existing_customer = Column(Boolean, default=False)
    source = Column(String)   # idsa, dexigner, designrush, manual
    added_at = Column(DateTime, default=datetime.utcnow)
