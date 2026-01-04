import os
import time
import uuid
import requests
import pyodbc
from requests.auth import HTTPBasicAuth


def env(name: str, default: str = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


def get_var(vars_dict: dict, name: str, default=None):
    try:
        return vars_dict.get(name, {}).get("value", default)
    except Exception:
        return default


def sql_conn():
    server = env("AZURE_SQL_SERVER")
    database = env("AZURE_SQL_DATABASE")
    user = env("AZURE_SQL_USER")
    password = env("AZURE_SQL_PASSWORD")

    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        f"Uid={user};"
        f"Pwd={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def fetch_and_lock(engine_rest: str, auth, worker_id: str, topic: str, max_tasks: int, lock_ms: int):
    url = f"{engine_rest}/external-task/fetchAndLock"
    payload = {
        "workerId": worker_id,
        "maxTasks": max_tasks,
        "usePriority": True,
        "topics": [{"topicName": topic, "lockDuration": lock_ms}]
    }
    r = requests.post(url, auth=auth, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def complete_task(engine_rest: str, auth, task_id: str, worker_id: str):
    url = f"{engine_rest}/external-task/{task_id}/complete"
    payload = {"workerId": worker_id, "variables": {}}
    r = requests.post(url, auth=auth, json=payload, timeout=30)
    r.raise_for_status()


def fail_task(engine_rest: str, auth, task_id: str, worker_id: str, msg: str, details: str, retries: int = 3, retry_timeout_ms: int = 60000):
    url = f"{engine_rest}/external-task/{task_id}/failure"
    payload = {
        "workerId": worker_id,
        "errorMessage": msg[:255],
        "errorDetails": details[:4000],
        "retries": retries,
        "retryTimeout": retry_timeout_ms
    }
    r = requests.post(url, auth=auth, json=payload, timeout=30)
    r.raise_for_status()


def main():
    engine_rest = env("ENGINE_REST")               # http://camunda:8080/engine-rest (inside docker)
    cam_user = env("CAMUNDA_USER", "demo")
    cam_pass = env("CAMUNDA_PASS", "demo")
    topic = env("TOPIC_NAME", "store-reject-contract")

    worker_id = os.getenv("WORKER_ID", f"worker-reject-{uuid.uuid4()}")
    lock_ms = int(os.getenv("LOCK_DURATION_MS", "60000"))
    max_tasks = int(os.getenv("MAX_TASKS", "5"))
    poll_sleep = float(os.getenv("POLL_SLEEP_SEC", "2.0"))

    auth = HTTPBasicAuth(cam_user, cam_pass)

    print(f"[reject-worker] started. engine={engine_rest} topic={topic} workerId={worker_id}")

    while True:
        try:
            tasks = fetch_and_lock(engine_rest, auth, worker_id, topic, max_tasks, lock_ms)
            if not tasks:
                time.sleep(poll_sleep)
                continue

            for t in tasks:
                task_id = t["id"]
                vars_dict = t.get("variables", {})
                process_instance_id = t.get("processInstanceId")
                business_key = t.get("businessKey")

                contract_id = get_var(vars_dict, "contractId")
                if not contract_id:
                    contract_id = str(uuid.uuid4())

                # From reviewContract.form
                legal_comment = get_var(vars_dict, "legalcomment")
                approval_decision = get_var(vars_dict, "approvaldecision")

                # Optional snapshot
                contract_title = get_var(vars_dict, "contractTitle")

                try:
                    with sql_conn() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            """
                            UPDATE Contracts
                            SET 
                                LegalComment = ?,
                                ApprovalDecision = ?,
                                ContractStatus = 'Rejected'
                            WHERE ContractId = ?
                            """,
                            legal_comment, approval_decision, contract_id
                        )
                        conn.commit()

                        # --- VERIFICATION ---
                        # --- VERIFICATION ---
                        cur.execute("SELECT ContractTitle, ContractStatus FROM Contracts WHERE ContractId = ?", contract_id)
                        row = cur.fetchone()
                        if row:
                            print(f"[reject-worker] VERIFICATION SUCCESS: Contract '{row[0]}' status '{row[1]}' in Contracts table.")
                        else:
                            print(f"[reject-worker] VERIFICATION FAILED: Row not found after update!")
                        # --------------------

                    complete_task(engine_rest, auth, task_id, worker_id)
                    print(f"[reject-worker] stored RejectedContracts contractId={contract_id} task={task_id}")

                except Exception as e:
                    fail_task(engine_rest, auth, task_id, worker_id,
                              msg="Azure SQL insert failed (RejectedContracts)",
                              details=str(e))
                    print(f"[reject-worker] FAILED task={task_id} err={e}")

        except Exception as e:
            print(f"[reject-worker] loop error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
