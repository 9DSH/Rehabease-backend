"""
Pydantic schemas. Field names/casing are copied verbatim from the real
Kotlin sources (ApiRepository.kt, ApiService.kt, Patient.kt, Program.kt,
and how UserInfo is consumed in DoctorViewModel.kt / PatientViewModel.kt),
because Gson serializes by exact property name / @SerializedName value.

Confirmed ground truth (from @SerializedName annotations, not guesses):

Patient.kt fields -> JSON keys:
    patientId  -> "patientid"
    firstName  -> "firstname"
    lastName   -> "lastname"
    condition  -> "condition"
    username   -> "username"
    (local Room `id: Int` is NOT annotated -- it's a local-only cache key,
    defaults to 1, never meaningfully round-tripped through the API)

Program.kt fields -> JSON keys (note the casing is NOT uniform -- this is
real, not a typo, and must be preserved):
    id           -> "_id"            (Mongo ObjectId string -- confirms the
                                       original backend was Mongo/Mongoose)
    title        -> "title"
    details      -> "details"
    usage        -> "usage"
    affectedPart -> "affectedPart"
    active       -> "active"
    programId    -> "programid"      (lowercase -- the *business* id used in
                                       every program-related request)
    duration     -> "duration"
    remainingDays-> "remainingDays"
    patientId    -> "patientid"      (lowercase)
    doctorId     -> "doctorID"       (capital ID -- inconsistent with the
                                       other two, but that's what's in the
                                       real Program.kt, so we replicate it)

UserInfo (in ApiRepository.kt) is used by BOTH DoctorViewModel.login() and
PatientViewModel.login() to parse the message field of /doctor/info and
/patient/info -- i.e. both endpoints return the SAME shape, not two
different ones as I originally assumed:
    doctorid, patientid, firstname, lastname, role, username, enable, __v
(the "__v" key is Mongoose's version key -- another Mongo fingerprint,
kept here purely for wire-format compatibility; it has no real meaning
in this reconstructed backend and is always 0)
"""
from typing import Optional
from pydantic import BaseModel, Field


# ==================== Generic ====================
class BaseResponse(BaseModel):
    state: bool = False
    status: int = 0
    message: str = ""


# ==================== Auth ====================
class LoginRequest(BaseModel):
    username: str
    password: str
    role: str  # "doctor" | "patient"


class LoginResponse(BaseModel):
    state: bool
    status: int
    message: str
    id: Optional[str] = None          # doctor id, when role == doctor
    patientid: Optional[str] = None   # patient id, when role == patient


class UserInfo(BaseModel):
    doctorid: str
    patientid: str
    firstname: str
    lastname: str
    role: str
    username: str
    enable: bool
    v: int = Field(0, alias="__v")

    class Config:
        populate_by_name = True


# ==================== Doctor ====================
class DoctorSetRequest(BaseModel):
    firstname: str
    lastname: str
    username: str
    password: str


class DoctorSetMessage(BaseModel):
    username: str
    doctorid: str


class DoctorSetResponse(BaseModel):
    state: bool
    status: int
    id: str
    message: DoctorSetMessage


class DoctorDeleteRequest(BaseModel):
    doctorID: str


class DoctorEditRequest(BaseModel):
    firstname: str
    lastname: str
    doctorID: str


class DoctorInfoRequest(BaseModel):
    doctorID: str


class DoctorInfoResponse(BaseModel):
    state: bool
    status: int
    message: str  # JSON-encoded UserInfo (see module docstring)


class DoctorPatientsRequest(BaseModel):
    doctorID: str


class PatientOut(BaseModel):
    """Matches Patient.kt exactly (only the fields that round-trip via API)."""
    patientid: str
    firstname: str
    lastname: str
    condition: str = ""
    username: str


class DoctorPatientsResponse(BaseModel):
    state: bool = False
    status: int = 0
    message: str  # JSON-encoded array of PatientOut


class DoctorProgramsRequest(BaseModel):
    doctorID: str


# ==================== Patient ====================
class PatientSetRequest(BaseModel):
    firstname: str
    lastname: str
    username: str
    password: str
    doctorID: str
    # NOTE: AddPatientFragment.kt collects a "condition" value from the UI
    # and validates it, but never actually includes it in the request body
    # sent to the API (looks like a pre-existing bug/incomplete feature in
    # the original app, not something missing from our reconstruction).
    # Patients created via this endpoint will have an empty "condition"
    # until the Android app is fixed to send it.


class PatientSetResponse(BaseModel):
    state: bool
    status: int
    message: str  # JSON-encoded {username, patientid} -- not parsed by the
                  # client today (it only checks `.state`), kept informational


class PatientDeleteRequest(BaseModel):
    patientID: str


class PatientEditRequest(BaseModel):
    firstname: str
    lastname: str
    doctorID: str
    patientID: str


class PatientInfoRequest(BaseModel):
    patientID: str


class PatientInfoResponse(BaseModel):
    state: bool
    status: int
    message: str  # JSON-encoded UserInfo (same shape as /doctor/info)


class PatientProgramsRequest(BaseModel):
    patientID: str


# ==================== Program ====================
class Program(BaseModel):
    """Exact mirror of models.Program (Kotlin), including its casing quirk."""
    id: str = Field("", alias="_id")
    title: str
    details: Optional[str] = None
    usage: Optional[str] = None
    affectedPart: Optional[str] = None
    active: bool = False
    programid: Optional[str] = None
    duration: int
    remainingDays: int
    patientid: Optional[str] = None
    doctorID: Optional[str] = None

    class Config:
        populate_by_name = True


class ProgramsResponse(BaseModel):
    state: bool
    status: int
    message: str  # JSON-encoded array of Program


class ProgramSetResponse(BaseModel):
    state: bool
    status: int
    message: str  # JSON-encoded single Program (parsed by getProgram())


class ProgramDeleteRequest(BaseModel):
    programID: str


class ProgramEditRequest(BaseModel):
    duration: str
    remainingDays: str
    details: str
    programID: str


class ProgramInfoRequest(BaseModel):
    programID: str


class ProgramInfoMessage(BaseModel):
    programid: str
    duration: str
    remainingDays: str
    details: str
    patientid: str
    doctorid: str


class ProgramInfoResponse(BaseModel):
    # NOTE: getProgramInfo() isn't called anywhere in the Fragments/
    # ViewModels we've seen, so this shape is lower-confidence / not
    # exercised by the real app flow. Kept for contract completeness.
    state: bool
    status: int
    message: ProgramInfoMessage


class ProgramAttachRequest(BaseModel):
    programID: str
    patientID: str


class ProgramDeattachRequest(BaseModel):
    programID: str
