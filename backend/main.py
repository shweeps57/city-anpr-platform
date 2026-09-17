from fastapi import FastAPI
import psycopg
import redis

app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    with psycopg.connect(
        "host=postgres dbname=anpr user=anpr password=anpr_dev_password"
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            postgres = cur.fetchone()[0]

    r = redis.Redis(host="redis", port=6379)

    return {
        "postgres": postgres == 1,
        "redis": r.ping()
    }