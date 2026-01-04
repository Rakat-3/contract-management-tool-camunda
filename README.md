# Contract Management System (Camunda BPMN + FastAPI)

A professional, enterprise-grade Contract Management solution designed for high-efficiency procurement workflows. This system orchestrates the entire lifecycle of a contract—from initial requirements drafting to provider offer review and final legal approval—using **Camunda Platform 7** for process orchestration and **FastAPI** for a robust, API-only backend.

## 🌟 Key Features

-   **Workflow Orchestration**: End-to-end process management involving Procurement Managers, Provider Managers (via API), and Legal Counsel.
-   **API-First for Providers**: External providers interact with the system through dedicated REST API endpoints (`GET` and `PATCH`), bypassing a traditional dashboard for direct integration.
-   **Automated Variable Sync**: Real-time synchronization between API updates and Camunda process variables, ensuring stakeholders always see the latest provider offers.
-   **Unified Persistence**: A single, optimized Azure SQL `Contracts` table with dynamic status tracking (`Submitted`, `Running`, `Approved`, `Rejected`).
-   **Email Notifications**: Automated HTML-formatted email alerts delivered via **MailHog** for cross-stakeholder communication.
-   **Containerized Deployment**: Fully orchestrated via Docker Compose for easy environment setup and scalability.

## 🏗 System Architecture

The project follows a modular, containerized architecture:

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Backend API** | FastAPI | Central hub for process initiation and provider data updates. |
| **Workflow Engine** | Camunda 7 | Orchestrates the `ContractTool` BPMN process and user tasks. |
| **Database** | Azure SQL | Primary data store for all contract metadata and status. |
| **System DB** | PostgreSQL | Reliability store for Camunda's internal engine state. |
| **Workers** | Python | External task clients for automated DB storage and email alerts. |
| **Email Server** | MailHog | SMTP server for testing automated notifications in development. |

## 🛠 Prerequisites

-   **Docker** & **Docker Compose**
-   **Azure SQL** Instance (Managed or Local Simulation)

## ⚡ Quick Start

### 1. Configuration

Ensure your `docker/.env` file is populated with your specific Azure SQL credentials:

```bash
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=contract_db
AZURE_SQL_USER=your_user
AZURE_SQL_PASSWORD=your_password
```

### 2. Launch the Ecosystem

```bash
cd docker
docker compose up -d --build
```

### 3. Service Access

| Service | Access URL | Credentials |
| :--- | :--- | :--- |
| **Backend Swagger Docs** | `http://localhost:8000/docs` | N/A |
| **Camunda Tasklist** | `http://localhost:8080/camunda/app/tasklist` | `demo` / `demo` |
| **MailHog Web UI** | `http://localhost:8025` | N/A |

## 📂 Project Structure

```text
├── backend/            # FastAPI source code and API definitions
├── bpmn/               # BPMN XML definitions and Camunda Forms
│   └── forms/          # UI definitions for Camunda Tasklist
├── docker/             # Docker configuration and Python workers
│   ├── email_worker.py # Unified HTML email notification engine
│   └── worker_*.py     # Specialized DB persistence workers
```

## 🔍 Workflow Lifecycle

1.  **Drafting**: Procurement Manager creates contract requirements in Camunda Tasklist.
2.  **Notification**: A notification is automatically sent to the Provider Manager (`provider@local.com`).
3.  **Submission**: Provider retrieves and updates the contract offer via the **Provider API** (`GET` / `PATCH`).
4.  **Sync**: The backend automatically syncs the provider's data back to the Camunda process.
5.  **Review**: Procurement Manager reviews offers and forwards to Legal.
6.  **Approval**: Legal Counsel approves or declines. Approved contracts are finalized in the DB.

## 📡 Provider API Overview

### `GET /api/providers/contracts`
Retrieves a list of active contracts assigned to providers with `Submitted` or `Running` status.

### `PATCH /api/providers/contracts/{id}`
Allows providers to submit their budget, comments, and confirmation of requirements.


#### Not Organized
'''

{
  "providersBudget": 7500,
  "providersComment": "Price includes priority support and implementation.",
  "meetRequirement": "Yes"
}

PATCH http://localhost:8000/api/providers/contracts/{contract_id}


http://localhost:8000/api/providers/contracts




Procurement Manager (PM)	pm_user	pm
Legal Counsel (LC)	lc_user	lc
Contract Administrator (CA)	ca_user	ca

20604eedcefd3bafc39e31b590dda114761a57c5

'''


---
*Developed for professional contract lifecycle management.*
