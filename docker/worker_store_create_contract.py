import os
import time
import uuid
import json
import requests
import pyodbc
from requests.auth import HTTPBasicAuth


def env(name: str, default: str = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


def get_var(vars_dict: dict, name: str, default=None):
    """Camunda returns variables as {name: {value: ...}}"""
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
        "topics": [
            {
                "topicName": topic,
                "lockDuration": lock_ms
                # Fetch all variables (safe + simple)
            }
        ]
    }
    r = requests.post(url, auth=auth, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def complete_task(engine_rest: str, auth, task_id: str, worker_id: str, variables: dict):
    url = f"{engine_rest}/external-task/{task_id}/complete"
    # Camunda expects variables in { varName: { value: x } }
    payload = {"workerId": worker_id, "variables": {k: {"value": v} for k, v in variables.items()}}
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
    engine_rest = env("ENGINE_REST")               # e.g. http://camunda:8080/engine-rest
    cam_user = env("CAMUNDA_USER", "demo")
    cam_pass = env("CAMUNDA_PASS", "demo")
    topic = env("TOPIC_NAME", "store-create-contract")

    worker_id = os.getenv("WORKER_ID", f"worker-create-{uuid.uuid4()}")
    lock_ms = int(os.getenv("LOCK_DURATION_MS", "60000"))
    max_tasks = int(os.getenv("MAX_TASKS", "5"))
    poll_sleep = float(os.getenv("POLL_SLEEP_SEC", "2.0"))

    auth = HTTPBasicAuth(cam_user, cam_pass)

    print(f"[create-worker] started. engine={engine_rest} topic={topic} workerId={worker_id}")

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
                business_key = t.get("businessKey")  # may be None

                # Generate contractId once (and push back to Camunda)
                contract_id = get_var(vars_dict, "contractId")
                if not contract_id:
                    contract_id = str(uuid.uuid4())

                # From contractDraft.form (your fields)
                contract_title = get_var(vars_dict, "contractTitle")
                contract_type = get_var(vars_dict, "contractType")
                roles = get_var(vars_dict, "roles")
                skills = get_var(vars_dict, "skills")
                request_type = get_var(vars_dict, "requestType")
                budget = get_var(vars_dict, "budget")
                contract_start = get_var(vars_dict, "contractStartDate")
                contract_end = get_var(vars_dict, "contractEndDate")
                description = get_var(vars_dict, "description")

                # budget normalize
                try:
                    budget_val = float(budget) if budget is not None and budget != "" else None
                except Exception:
                    budget_val = None

                try:
                    with sql_conn() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            """
                            INSERT INTO Contracts
                            (ContractId, ProcessInstanceId, BusinessKey,
                             ContractTitle, ContractType, Roles, Skills, RequestType,
                             Budget, ContractStartDate, ContractEndDate, Description, 
                             ContractStatus, ProvidersBudget, ProvidersComment,
                             MeetRequirement, ProvidersName,
                             CreatedAt)
                            VALUES
                            (CONVERT(uniqueidentifier, ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                             'Submitted', NULL, '', 
                             NULL, NULL,
                             SYSUTCDATETIME())
                            """,
                            contract_id, process_instance_id, business_key,
                            contract_title, contract_type, roles, skills, request_type,
                            budget_val, contract_start, contract_end, description
                        )
                        conn.commit()



                    # Push contractId back so next steps can use it
                    complete_task(engine_rest, auth, task_id, worker_id, {"contractId": contract_id})
                    print(f"[create-worker] stored CreatedContracts contractId={contract_id} task={task_id}")

                except Exception as e:
                    fail_task(engine_rest, auth, task_id, worker_id,
                              msg="Azure SQL insert failed (CreatedContracts)",
                              details=str(e))
                    print(f"[create-worker] FAILED task={task_id} err={e}")

        except Exception as e:
            print(f"[create-worker] loop error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
