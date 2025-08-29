import uvicorn

def main():
    uvicorn.run(
        "ai_dial_interceptor_google.app:app",
        host="0.0.0.0",
        port=5555,
        env_file="./.env",
        reload=True
    )

if __name__ == "__main__":
    main()
