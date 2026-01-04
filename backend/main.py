from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db import get_connection, get_azure_connection
import sys
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Backend is running!"}
    
@app.get("/test-db")
def test_db():
    try:
        conn = get_connection()
        conn.close()
        return {"status": "ok", "message": "Database connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/stats")
def get_stats():
    """
    Returns counts for Submitted, Approved, and Rejected contracts from Azure SQL.
    """
    try:
        conn = get_azure_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT ContractStatus, COUNT(*) FROM Contracts GROUP BY ContractStatus")
        rows = cursor.fetchall()
        
        stats = {"submitted": 0, "approved": 0, "rejected": 0}
        
        for status, count in rows:
            s = status.lower() if status else ""
            if s == "submitted" or s == "running":
                stats["submitted"] += count
            elif s == "approved":
                stats["approved"] += count
            elif s == "rejected":
                stats["rejected"] += count
        
        conn.close()
        
        return stats
    except Exception as e:
        print(f"Error in /stats: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/contracts/{status}")
def get_contracts(status: str):
    """
    Returns list of contracts based on status: 'submitted', 'approved', 'rejected'.
    """
    status = status.lower()
    allowed = ["submitted", "approved", "rejected"]
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status. Must be submitted, approved, or rejected.")
    
    try:
        conn = get_azure_connection()
        cursor = conn.cursor()
        
        # Map frontend status to DB status
        # 'submitted' could match 'Submitted' or 'Running'
        # 'approved' matches 'Approved'
        # 'rejected' matches 'Rejected'
        
        if status == "submitted":
            query = "SELECT * FROM Contracts WHERE ContractStatus IN ('Submitted', 'Running') ORDER BY CreatedAt DESC"
        elif status == "approved":
             query = "SELECT * FROM Contracts WHERE ContractStatus = 'Approved' ORDER BY ApprovedAt DESC"
        else: # rejected
             query = "SELECT * FROM Contracts WHERE ContractStatus = 'Rejected' ORDER BY RejectedAt DESC"
            
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Convert rows to list of dicts
        columns = [column[0] for column in cursor.description]
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
            
        conn.close()
        return results
        
    except Exception as e:
        print(f"Error in /contracts/{status}: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

        
import requests

CAMUNDA_URL = "http://camunda:8080/engine-rest" # Use docker service name if running in docker

class ProviderUpdate(BaseModel):
    providersBudget: Optional[int] = None
    providersComment: Optional[str] = None
    meetRequirement: Optional[str] = None
    providersName: Optional[str] = None

@app.get("/api/providers/contracts")
def get_provider_contracts():
    """
    Returns contracts for providers that are in 'Submitted' or 'Running' status.
    """
    try:
        conn = get_azure_connection()
        cursor = conn.cursor()
        
        # Select specific fields requested, filtering for 'Submitted' or 'Running' contracts
        query = """
            SELECT ContractId, ContractTitle, ContractType, Roles, Skills, RequestType, 
                   Budget, ContractStartDate, ContractEndDate, Description,
                   ContractStatus, ProvidersBudget, ProvidersComment, MeetRequirement, ProvidersName
            FROM Contracts
            WHERE ContractStatus IN ('Submitted', 'Running')
            ORDER BY CreatedAt DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        columns = [column[0] for column in cursor.description]
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
            
        conn.close()
        return results
    except Exception as e:
        print(f"Error in /api/providers/contracts: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/providers/contracts/{contract_id}")
def update_provider_contract(contract_id: str, update: ProviderUpdate):
    """
    Updates providersBudget, providersComment and meetRequirement for a contract.
    This endpoint is used by providers to submit their offers.
    It also attempts to sync the data back to Camunda process variables if an active instance is found.
    """
    try:
        conn = get_azure_connection()
        cursor = conn.cursor()
        
        # Check if contract exists
        cursor.execute("SELECT ContractId, ContractStatus FROM Contracts WHERE ContractId = ?", contract_id)
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
            
        # Update fields in DB
        query = """
            UPDATE Contracts
            SET ContractStatus = 'Running', ProvidersBudget = ?, ProvidersComment = ?, MeetRequirement = ?, ProvidersName = ?
            WHERE ContractId = ?
        """
        cursor.execute(query, update.providersBudget, update.providersComment, update.meetRequirement, update.providersName, contract_id)
        conn.commit()
        conn.close()

        # Camunda Sync: Try to find and update process variables
        try:
            print(f"[Camunda Sync] Looking for instance with contractId={contract_id}...")
            # Use /variable-instance to find the process instance ID
            # This is more reliable as it searches throughout the process lifecycle
            instances_res = requests.get(f"{CAMUNDA_URL}/variable-instance?variableName=contractId&variableValue={contract_id}")
            variables = instances_res.json()
            
            if variables:
                instance_id = variables[0]["processInstanceId"]
                print(f"[Camunda Sync] Found instance {instance_id}. Updating variables...")
                
                # 2. Update variables (handle None/null safely)
                modifications = {}
                if update.providersName is not None:
                    modifications["providersName"] = {"value": update.providersName, "type": "String"}
                if update.providersBudget is not None:
                    modifications["providersBudget"] = {"value": int(update.providersBudget), "type": "Integer"}
                if update.providersComment is not None:
                    modifications["providersComment"] = {"value": update.providersComment, "type": "String"}
                if update.meetRequirement is not None:
                    modifications["meetRequirement"] = {"value": update.meetRequirement, "type": "String"}

                if modifications:
                    var_payload = {"modifications": modifications}
                    print(f"[Camunda Sync] Sending payload: {var_payload}")
                    resp = requests.post(f"{CAMUNDA_URL}/process-instance/{instance_id}/variables", json=var_payload)
                    print(f"[Camunda Sync] Status Code: {resp.status_code}")
                    if resp.status_code >= 400:
                        print(f"[Camunda Sync] Response Body: {resp.text}")
                    else:
                        print(f"[Camunda Sync] Successfully pushed variables to {instance_id}")
            else:
                print(f"[Camunda Sync] No process instance found with contractId={contract_id}")
        except Exception as camunda_err:
            print(f"Warning: Failed to sync with Camunda: {camunda_err}", file=sys.stderr)

        return {
            "status": "success",
            "message": "Contract updated and synced successfully",
            "contractId": contract_id,
            "updatedFields": {
                "providersBudget": update.providersBudget,
                "providersComment": update.providersComment,
                "meetRequirement": update.meetRequirement,
                "providersName": update.providersName
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in PATCH /api/providers/contracts: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start-process")
def start_process(data: dict):
    """
    Starts the Camunda process and passes initial variables.
    """
    # Note: contractId is NOT generated here, it's generated by the store-create-contract-worker
    payload = {
        "variables": {
            "contractTitle": {"value": data.get("contractTitle"), "type": "String"},
            "requestedBy": {"value": data.get("requestedBy"), "type": "String"},
        }
    }
    
    try:
        print(f"Starting process in Camunda: {data.get('contractTitle')}")
        res = requests.post(
            f"{CAMUNDA_URL}/process-definition/key/contractTool/start",
            json=payload,
            timeout=10
        )
        res.raise_for_status()
        return {"camunda_response": res.json()}
    except Exception as e:
        print(f"Failed to start Camunda process: {e}", file=sys.stderr)
        return {"error": str(e)}
