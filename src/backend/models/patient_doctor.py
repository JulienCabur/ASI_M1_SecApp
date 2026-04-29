"""
Ce module définit le modèle patient et docteur pour l'application.
Il utilise SQLAlchemy pour créer des classes qui représentent les tables de la base de données. Chaque classe correspond à une table, et les attributs de la classe correspondent aux colonnes de la table..
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Date, Table
from sqlalchemy.orm import relationship
from core.database import Base

patient_doctor_association = Table(
    'patient_doctor',
    Base.metadata,
    Column('patient_id', Integer, ForeignKey('patients.id'), primary_key=True),
    Column('doctor_id', Integer, ForeignKey('doctors.id'), primary_key=True)
)

class Patient(Base):
    __tablename__ = 'patients'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, unique=True)
    birth_date = Column(Date, nullable=True)
    
    doctors = relationship(
        "Doctor",
        secondary=patient_doctor_association,
        back_populates="patients"
    )

class Doctor(Base):
    __tablename__ = 'doctors'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, unique=True)
    specialty = Column(String, nullable=True)
    
    patients = relationship(
        "Patient",
        secondary=patient_doctor_association,
        back_populates="doctors"
    )