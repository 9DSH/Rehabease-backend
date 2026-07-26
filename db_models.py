"""
ORM tables.

Field choices are inferred from how the Android client uses these
objects (ApiRepository.kt / ApiService.kt). Not from a recovered schema
-- there wasn't one. Adjust if you find any trace of the real schema
later (old .sql dump, ORM migration folder, etc.).
"""
import uuid
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String, primary_key=True, default=gen_id)
    firstname = Column(String, nullable=False)
    lastname = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    enable = Column(Boolean, default=True)

    patients = relationship("Patient", back_populates="doctor")
    programs = relationship("Program", back_populates="doctor")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=gen_id)
    firstname = Column(String, nullable=False)
    lastname = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    condition = Column(String, nullable=False, default="")  # matches Patient.kt's `condition` field
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=True)
    enable = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="patients")
    programs = relationship("Program", back_populates="patient")


class Program(Base):
    __tablename__ = "programs"

    id = Column(String, primary_key=True, default=gen_id)  # serialized as both "_id" and "programid"
    title = Column(String, nullable=False, default="")
    details = Column(String, nullable=True)
    usage = Column(String, nullable=True)
    affected_part = Column(String, nullable=True)
    active = Column(Boolean, default=False)
    duration = Column(Integer, nullable=False)
    remaining_days = Column(Integer, nullable=False)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=True)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=True)

    patient = relationship("Patient", back_populates="programs")
    doctor = relationship("Doctor", back_populates="programs")
