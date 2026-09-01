from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False)

    cv_profiles = relationship("CVProfile", back_populates="user", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="user", cascade="all, delete-orphan")


class CVProfile(Base):
    __tablename__ = "cv_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    raw_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    filename = Column(String(512), nullable=True)
    status = Column(String(50), nullable=False, default='pending')
    extraction_method = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    structured_data = Column(Text, nullable=True)  # JSON string
    ats_score = Column(Integer, nullable=True)
    ats_issues = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="cv_profiles")
    analysis_results = relationship("AnalysisResult", back_populates="cv_profile", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="cv_profile")


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    company = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(1024), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_raw = Column(String(255), nullable=True)
    external_id = Column(String(255), nullable=True, index=True)
    source = Column(String(50), nullable=True, default='adzuna')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    cv_id = Column(Integer, ForeignKey('cv_profiles.id', ondelete='CASCADE'), nullable=False)
    result = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False)

    cv_profile = relationship("CVProfile", back_populates="analysis_results")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    cv_id = Column(Integer, ForeignKey('cv_profiles.id', ondelete='SET NULL'), nullable=True)
    role = Column(String(255), nullable=True)  # target role under interview
    difficulty = Column(String(32), nullable=True, default='junior')
    status = Column(String(32), nullable=False, default='pending')  # pending|active|completed|abandoned
    in_progress = Column(Boolean, default=True, nullable=False)
    history_json = Column(Text, nullable=True)  # list[InterviewTurn]
    running_score = Column(Float, nullable=True)
    overall_feedback = Column(Text, nullable=True)
    state_json = Column(Text, nullable=True)  # full InterviewGraphState snapshot for resume
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="interview_sessions")
    cv_profile = relationship("CVProfile", back_populates="interview_sessions")
