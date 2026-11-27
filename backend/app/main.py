from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import appointments, auth, chat, doctor, doctors, fact, staff, summary, urgent

app = FastAPI(
    title="NetraCare Clinic API",
    version="0.1.0",
    description="Synthetic classroom clinic API. Passwordless login is not production security.",
)

# Headless API — no UI in-tree pending rebuild. CORS left open for local clients.
# allow_credentials is False: browsers reject wildcard origins with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(staff.router)
app.include_router(doctor.router)
app.include_router(urgent.router)
app.include_router(fact.router)
app.include_router(summary.router)
app.include_router(chat.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
