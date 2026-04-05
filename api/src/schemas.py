"""Pydantic request/response schemas."""

import uuid
from datetime import datetime

from fastapi_users import schemas
from pydantic import BaseModel

# --- Auth schemas (fastapi-users) ---

class UserRead(schemas.BaseUser[uuid.UUID]):
    tenant_id: uuid.UUID | None = None
    role: str = "member"


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


# --- Profile schemas ---

class ContactInfo(BaseModel):
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class ExperienceEntry(BaseModel):
    company: str
    title: str
    dates: str | None = None
    bullets: list[str] = []


class EducationEntry(BaseModel):
    school: str
    degree: str
    dates: str | None = None


class ProjectEntry(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    tech: list[str] = []


class ProfileRead(BaseModel):
    id: uuid.UUID
    full_name: str | None = None
    contact: ContactInfo | None = None
    summary: str | None = None
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    skills: list[str] = []
    certifications: list[str] = []
    projects: list[ProjectEntry] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    contact: ContactInfo | None = None
    summary: str | None = None
    experience: list[ExperienceEntry] | None = None
    education: list[EducationEntry] | None = None
    skills: list[str] | None = None
    certifications: list[str] | None = None
    projects: list[ProjectEntry] | None = None


# --- Job schemas ---

class JobRead(BaseModel):
    id: int
    url: str
    title: str
    company: str
    location: str | None = None
    salary_range: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    description: str | None = None
    requirements: list = []
    responsibilities: list = []
    benefits: list = []
    application_url: str | None = None
    date_posted: str | None = None
    scraped_at: datetime

    model_config = {"from_attributes": True}


class JobScrapeRequest(BaseModel):
    url: str


class AnalysisRead(BaseModel):
    id: int
    job_id: int
    fit_score: int
    base_score: int | None = None
    penalties: list = []
    fit_reasoning: str | None = None
    matching_skills: list = []
    gaps: list = []
    keywords: list = []
    tailoring_strategy: str | None = None
    analyzed_at: datetime

    model_config = {"from_attributes": True}


# --- Task schemas ---

class TaskRead(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    progress: int = 0
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    type: str
    input: dict | None = None


# --- Discovery schemas ---

class SearchConfigRead(BaseModel):
    id: int
    name: str
    config_type: str
    config: dict
    is_active: bool
    last_run_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchConfigCreate(BaseModel):
    name: str
    config_type: str  # 'search_query' or 'career_page'
    config: dict


class SearchConfigUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


# --- Answer schemas ---

class AnswerRead(BaseModel):
    id: int
    question: str
    answer: str
    source: str = "manual"
    category: str | None = None
    times_used: int = 0
    last_used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerCreate(BaseModel):
    question: str
    answer: str
    category: str | None = None


class AnswerUpdate(BaseModel):
    answer: str | None = None
    category: str | None = None


# --- Billing schemas ---

class PlanRead(BaseModel):
    plan: str
    limits: dict


class UsageRead(BaseModel):
    period_start: datetime
    period_end: datetime
    scrapes: int = 0
    analyses: int = 0
    generations: int = 0
    tokens_used: int = 0
    cost_estimate: float = 0.0


# --- Skill schemas ---

class SkillCount(BaseModel):
    skill: str
    count: int


class SkillGap(BaseModel):
    skill: str
    demand_count: int


# --- Telegram schemas ---

class TelegramLinkCodeResponse(BaseModel):
    code: str
    deep_link: str


class TelegramStatusResponse(BaseModel):
    linked: bool
    username: str | None = None
    chat_id: int | None = None
    is_active: bool = False


# --- Notification schemas ---

class NotificationPreferencesRead(BaseModel):
    telegram_enabled: bool = True

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    telegram_enabled: bool
