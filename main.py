from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from routers import auth, jobs, ai, resumes, analytics
from db.database import create_tables
from fastapi.openapi.utils import get_openapi

security = HTTPBearer()

app = FastAPI(
    title="Job Tracker API",
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True}
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Job Tracker API",
        version="1.0.0",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
        }
    }
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://job-tracker-frontend-self.vercel.app","http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(ai.router,   prefix="/ai",   tags=["AI"])
app.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

@app.on_event("startup")
async def startup():
    await create_tables()

@app.get("/")
async def root():
    return {"message": "Job Tracker API is running"}
