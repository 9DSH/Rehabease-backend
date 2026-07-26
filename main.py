"""
RehabEase backend -- reconstructed to match the contract implied by the
Android client (ApiService.kt / ApiRepository.kt / Patient.kt / Program.kt
/ DoctorViewModel.kt / PatientViewModel.kt).

Run:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 80 --reload

Then point ApiService.kt's BASE_URL at this server, e.g.:
    private const val BASE_URL = "http://<your-server-ip>/"
"""
import json
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # must run before importing auth, which reads env vars at import time

from fastapi import FastAPI, Depends, HTTPException, Header, Response
from sqlalchemy.orm import Session

import admin
import auth
import db_models
import schemas
from database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RehabEase API (reconstructed)")
app.include_router(admin.router)


# ==================== Auth dependency ====================
def require_auth(authorization: Optional[str] = Header(None)) -> dict:
    """
    Mirrors the client's tokenInterceptor: it sends back whatever string
    the server returned in the Authorization header at login time.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    payload = auth.decode_token(authorization)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# ==================== Serialization helpers ====================
def _program_to_dict(p: db_models.Program) -> dict:
    """Matches Program.kt's @SerializedName mapping exactly, including the
    doctorID (capital ID) vs patientid/programid (lowercase) inconsistency."""
    return {
        "_id": p.id,
        "title": p.title,
        "details": p.details,
        "usage": p.usage,
        "affectedPart": p.affected_part,
        "active": p.active,
        "programid": p.id,
        "duration": p.duration,
        "remainingDays": p.remaining_days,
        "patientid": p.patient_id,
        "doctorID": p.doctor_id,
    }


def _patient_to_dict(p: db_models.Patient) -> dict:
    """Matches Patient.kt's @SerializedName mapping exactly."""
    return {
        "patientid": p.id,
        "firstname": p.firstname,
        "lastname": p.lastname,
        "condition": p.condition or "",
        "username": p.username,
    }


def _user_info_dict(*, doctorid: str, patientid: str, firstname: str,
                     lastname: str, role: str, username: str, enable: bool) -> dict:
    """Matches UserInfo in ApiRepository.kt, used by BOTH /doctor/info and
    /patient/info (confirmed by DoctorViewModel.login / PatientViewModel.login
    both parsing their info response into UserInfo)."""
    return {
        "doctorid": doctorid,
        "patientid": patientid,
        "firstname": firstname,
        "lastname": lastname,
        "role": role,
        "username": username,
        "enable": enable,
        "__v": 0,  # Mongoose version key -- cosmetic only, kept for wire compatibility
    }


# ==================== Login ====================
@app.post("/login", response_model=schemas.LoginResponse)
def login(body: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    if body.role == "doctor":
        user = db.query(db_models.Doctor).filter_by(username=body.username).first()
    elif body.role == "patient":
        user = db.query(db_models.Patient).filter_by(username=body.username).first()
    else:
        return schemas.LoginResponse(state=False, status=400, message="Unknown role")

    if not user or not auth.verify_password(body.password, user.password_hash):
        return schemas.LoginResponse(state=False, status=401, message="Invalid username or password")

    if not user.enable:
        return schemas.LoginResponse(state=False, status=403, message="Account disabled")

    token = auth.create_token(user.id, body.role)
    response.headers["Authorization"] = token  # client reads the token from here, not the body

    if body.role == "doctor":
        return schemas.LoginResponse(state=True, status=200, message="Login successful", id=user.id)
    else:
        return schemas.LoginResponse(state=True, status=200, message="Login successful", patientid=user.id)


# ==================== Doctor endpoints ====================
@app.post("/doctor/set", response_model=schemas.DoctorSetResponse)
def set_doctor(body: schemas.DoctorSetRequest, db: Session = Depends(get_db)):
    """
    NOTE: nothing in the Android app actually calls this endpoint -- doctor
    accounts were created directly on the old server. It's kept here for
    API contract completeness, but it is UNAUTHENTICATED and open to
    anyone who finds the URL. Use the password-protected /admin panel
    (see admin.py) to create doctors in practice. Consider removing this
    endpoint, or locking it down, before going to production.
    """
    if db.query(db_models.Doctor).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    doctor = db_models.Doctor(
        firstname=body.firstname,
        lastname=body.lastname,
        username=body.username,
        password_hash=auth.hash_password(body.password),
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return schemas.DoctorSetResponse(
        state=True, status=200, id=doctor.id,
        message=schemas.DoctorSetMessage(username=doctor.username, doctorid=doctor.id),
    )


@app.post("/doctor/delete", response_model=schemas.BaseResponse)
def delete_doctor(body: schemas.DoctorDeleteRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    doctor = db.query(db_models.Doctor).filter_by(id=body.doctorID).first()
    if not doctor:
        return schemas.BaseResponse(state=False, status=404, message="Doctor not found")
    db.delete(doctor)
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Doctor deleted")


@app.post("/doctor/edit", response_model=schemas.BaseResponse)
def edit_doctor(body: schemas.DoctorEditRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    doctor = db.query(db_models.Doctor).filter_by(id=body.doctorID).first()
    if not doctor:
        return schemas.BaseResponse(state=False, status=404, message="Doctor not found")
    doctor.firstname = body.firstname
    doctor.lastname = body.lastname
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Doctor updated")


@app.post("/doctor/info", response_model=schemas.DoctorInfoResponse)
def get_doctor_info(body: schemas.DoctorInfoRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    doctor = db.query(db_models.Doctor).filter_by(id=body.doctorID).first()
    if not doctor:
        return schemas.DoctorInfoResponse(state=False, status=404, message="Doctor not found")
    payload = _user_info_dict(
        doctorid=doctor.id, patientid="", firstname=doctor.firstname,
        lastname=doctor.lastname, role="doctor", username=doctor.username,
        enable=doctor.enable,
    )
    return schemas.DoctorInfoResponse(state=True, status=200, message=json.dumps(payload))


@app.post("/doctor/patients", response_model=schemas.DoctorPatientsResponse)
def get_doctor_patients(body: schemas.DoctorPatientsRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    patients = db.query(db_models.Patient).filter_by(doctor_id=body.doctorID).all()
    payload = [_patient_to_dict(p) for p in patients]
    return schemas.DoctorPatientsResponse(state=True, status=200, message=json.dumps(payload))


@app.post("/doctor/programes", response_model=schemas.ProgramsResponse)
def get_doctor_programs(body: schemas.DoctorProgramsRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    programs = db.query(db_models.Program).filter_by(doctor_id=body.doctorID).all()
    payload = [_program_to_dict(p) for p in programs]
    return schemas.ProgramsResponse(state=True, status=200, message=json.dumps(payload))


# ==================== Patient endpoints ====================
@app.post("/patient/set", response_model=schemas.PatientSetResponse)
def set_patient(body: schemas.PatientSetRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    if db.query(db_models.Patient).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if not db.query(db_models.Doctor).filter_by(id=body.doctorID).first():
        return schemas.PatientSetResponse(state=False, status=404, message="Doctor not found")
    patient = db_models.Patient(
        firstname=body.firstname,
        lastname=body.lastname,
        username=body.username,
        password_hash=auth.hash_password(body.password),
        doctor_id=body.doctorID,
        condition="",  # AddPatientFragment doesn't send this today -- see schemas.py note
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    payload = {"username": patient.username, "patientid": patient.id}
    return schemas.PatientSetResponse(state=True, status=200, message=json.dumps(payload))


@app.post("/patient/delete", response_model=schemas.BaseResponse)
def delete_patient(body: schemas.PatientDeleteRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    patient = db.query(db_models.Patient).filter_by(id=body.patientID).first()
    if not patient:
        return schemas.BaseResponse(state=False, status=404, message="Patient not found")
    db.delete(patient)
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Patient deleted")


@app.post("/patient/edit", response_model=schemas.BaseResponse)
def edit_patient(body: schemas.PatientEditRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    patient = db.query(db_models.Patient).filter_by(id=body.patientID).first()
    if not patient:
        return schemas.BaseResponse(state=False, status=404, message="Patient not found")
    patient.firstname = body.firstname
    patient.lastname = body.lastname
    patient.doctor_id = body.doctorID
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Patient updated")


@app.post("/patient/info", response_model=schemas.PatientInfoResponse)
def get_patient_info(body: schemas.PatientInfoRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    patient = db.query(db_models.Patient).filter_by(id=body.patientID).first()
    if not patient:
        return schemas.PatientInfoResponse(state=False, status=404, message="Patient not found")
    payload = _user_info_dict(
        doctorid=patient.doctor_id or "", patientid=patient.id,
        firstname=patient.firstname, lastname=patient.lastname,
        role="patient", username=patient.username, enable=patient.enable,
    )
    return schemas.PatientInfoResponse(state=True, status=200, message=json.dumps(payload))


@app.post("/patient/programes", response_model=schemas.ProgramsResponse)
def get_patient_programs(body: schemas.PatientProgramsRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    programs = db.query(db_models.Program).filter_by(patient_id=body.patientID).all()
    payload = [_program_to_dict(p) for p in programs]
    return schemas.ProgramsResponse(state=True, status=200, message=json.dumps(payload))


# ==================== Program endpoints ====================
@app.post("/program/set", response_model=schemas.ProgramSetResponse)
def set_program(body: schemas.Program, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """
    Body is the full Program object (AddProgramFragment sends `id=""`,
    `programId=""` placeholders on create -- we ignore any client-supplied
    id and always generate a fresh one server-side).
    """
    program = db_models.Program(
        title=body.title,
        details=body.details,
        usage=body.usage,
        affected_part=body.affectedPart,
        active=body.active,
        duration=body.duration,
        remaining_days=body.remainingDays,
        patient_id=body.patientid or None,
        doctor_id=body.doctorID or None,
    )
    db.add(program)
    db.commit()
    db.refresh(program)
    return schemas.ProgramSetResponse(state=True, status=200, message=json.dumps(_program_to_dict(program)))


@app.post("/program/delete", response_model=schemas.BaseResponse)
def delete_program(body: schemas.ProgramDeleteRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    program = db.query(db_models.Program).filter_by(id=body.programID).first()
    if not program:
        return schemas.BaseResponse(state=False, status=404, message="Program not found")
    db.delete(program)
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Program deleted")


@app.post("/program/edit", response_model=schemas.BaseResponse)
def edit_program(body: schemas.ProgramEditRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    program = db.query(db_models.Program).filter_by(id=body.programID).first()
    if not program:
        return schemas.BaseResponse(state=False, status=404, message="Program not found")
    program.duration = int(body.duration)
    program.remaining_days = int(body.remainingDays)
    program.details = body.details
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Program updated")


@app.post("/program/info", response_model=schemas.ProgramInfoResponse)
def get_program_info(body: schemas.ProgramInfoRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    program = db.query(db_models.Program).filter_by(id=body.programID).first()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    info = schemas.ProgramInfoMessage(
        programid=program.id,
        duration=str(program.duration),
        remainingDays=str(program.remaining_days),
        details=program.details or "",
        patientid=program.patient_id or "",
        doctorid=program.doctor_id or "",
    )
    return schemas.ProgramInfoResponse(state=True, status=200, message=info)


@app.post("/program/attach", response_model=schemas.BaseResponse)
def attach_program(body: schemas.ProgramAttachRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    program = db.query(db_models.Program).filter_by(id=body.programID).first()
    if not program:
        return schemas.BaseResponse(state=False, status=404, message="Program not found")
    program.patient_id = body.patientID
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Program attached")


@app.post("/program/deattach", response_model=schemas.BaseResponse)
def deattach_program(body: schemas.ProgramDeattachRequest, auth_payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    program = db.query(db_models.Program).filter_by(id=body.programID).first()
    if not program:
        return schemas.BaseResponse(state=False, status=404, message="Program not found")
    program.patient_id = None
    db.commit()
    return schemas.BaseResponse(state=True, status=200, message="Program detached")