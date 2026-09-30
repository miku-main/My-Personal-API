from fastapi import FastAPI

app = FastAPI(title="My Personal API")

@app.get("/")
def root():
    return {"message": "Welcome to My Personal API!"}

@app.get("/me")
def about_me():
    return {
        "name": "John Doe",
        "role": "Student",
        "interests": ["Programming", "Reading", "Traveling"],
    }