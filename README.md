# RehabEase backend (reconstructed)

This replaces the lost server. Built to match the exact contract implied
by the Android app's code (`ApiService.kt`, `ApiRepository.kt`,
`Patient.kt`, `Program.kt`, and the ViewModels), verified with a live
end-to-end test (register doctor -> login -> create patient -> create
program -> attach -> patient fetches program).

## Run it

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
uvicorn main:app --host 0.0.0.0 --port 80
```

SQLite file `rehabease.db` is created automatically on first run in the
working directory. Interactive API docs at `http://<host>/docs`.

Then point the Android app at this server: in `ApiService.kt`,

```kotlin
private const val BASE_URL = "http://<your-server-ip>/"
```

## How auth works (matches the client exactly)

`/login` does **not** return the token in the JSON body. The Android
client's `tokenInterceptor` reads it from the `Authorization` *response
header*, and its `authInterceptor` sends that same string back as the
`Authorization` *request header* on every later call. This server does
exactly that (see `main.py`'s `login()` and `require_auth()`).

## Endpoints

All 18 endpoints from `ApiService.kt` are implemented 1:1 (paths, request
bodies, response shapes) — see `schemas.py` for the full field-by-field
mapping and the reasoning behind each casing quirk (`doctorID` vs
`patientid`/`programid`, `_id` vs `programid`, etc.), all confirmed
against the real `@SerializedName` annotations in `Patient.kt`/`Program.kt`.

## Known gaps / things to double check against the real production data

1. **No recovered database** — this is a fresh schema (SQLite via
   SQLAlchemy) inferred from client usage, not a restore. Any patients,
   doctors, or programs that existed before are gone unless you have a
   backup somewhere.
2. **Doctor creation (`/doctor/set`) is implemented but was never called
   by the app** — originally doctors were created directly on the old
   server (admin script/DB insert/separate panel). Use this endpoint (or
   the `/docs` UI) to seed your first doctor account for testing, but
   consider locking it down before going live since it's currently open
   with no auth.
3. **`condition` on `Patient` is always empty right now** —
   `AddPatientFragment.kt` collects a "condition" value in the UI but
   never actually includes it in the `/patient/set` request body. That's
   a pre-existing bug in the Android app, not something missing here. Fix
   it client-side (add `condition` to `PatientSetRequest` and the
   Retrofit call) if you want it to persist.
4. **`/program/info` is implemented but unused** by any Fragment/ViewModel
   we've seen — lower confidence on its exact shape since there's no real
   call site to verify against.
5. **Passwords/tokens**: uses bcrypt + JWT (30-day expiry, `HS256`). Set
   `REHABEASE_JWT_SECRET` as an environment variable in production instead
   of the default.
6. **Original backend was almost certainly Node.js + Express + MongoDB
   (Mongoose)** — confirmed by the `_id` and `__v` fields in the real
   Kotlin model files. This Python/FastAPI rebuild replicates the JSON
   wire format exactly, but internally uses SQLite/SQLAlchemy instead. If
   you'd rather match the original stack 1:1 (e.g. because you find old
   Mongoose schema files later), this can be ported to Node without
   changing anything on the Android side.

## Also flagged earlier (unrelated but important)

`RetrofitClient.kt` has a **live OpenAI API key hardcoded in plaintext**.
Since it's been shared in this conversation, treat it as compromised and
rotate it in the OpenAI dashboard regardless of what happens with this
backend.
