-- =========================================
-- Contract Tool - Azure SQL Tables
-- =========================================
-- Unified Contracts Table
IF OBJECT_ID('dbo.Contracts', 'U') IS NOT NULL DROP TABLE dbo.Contracts;
GO -- Drop old tables if they exist (cleanup)
  IF OBJECT_ID('dbo.CreatedContracts', 'U') IS NOT NULL DROP TABLE dbo.CreatedContracts;
IF OBJECT_ID('dbo.ApprovedContracts', 'U') IS NOT NULL DROP TABLE dbo.ApprovedContracts;
IF OBJECT_ID('dbo.RejectedContracts', 'U') IS NOT NULL DROP TABLE dbo.RejectedContracts;
GO CREATE TABLE dbo.Contracts (
    Id INT IDENTITY(1, 1) PRIMARY KEY,
    ContractId UNIQUEIDENTIFIER NOT NULL,
    ProcessInstanceId NVARCHAR(64) NULL,
    BusinessKey NVARCHAR(255) NULL,
    -- Common Data
    ContractTitle NVARCHAR(255) NULL,
    ContractType NVARCHAR(255) NULL,
    Roles NVARCHAR(MAX) NULL,
    Skills NVARCHAR(MAX) NULL,
    RequestType NVARCHAR(255) NULL,
    Budget FLOAT NULL,
    ContractStartDate NVARCHAR(50) NULL,
    ContractEndDate NVARCHAR(50) NULL,
    Description NVARCHAR(MAX) NULL,
    -- Provider Fields
    ProvidersBudget INT NULL,
    ProvidersComment NVARCHAR(MAX) DEFAULT '',
    ProvidersName NVARCHAR(255) NULL,
    -- Provider Fields
    ProvidersBudget INT NULL,
    ProvidersComment NVARCHAR(MAX) DEFAULT '',
    ProvidersName NVARCHAR(255) NULL,
    -- Approval Fields
    SignedDate NVARCHAR(50) NULL,
    ApprovedAt DATETIME2 NULL,
    -- Rejection Fields
    LegalComment NVARCHAR(MAX) NULL,
    ApprovalDecision NVARCHAR(50) NULL,
    -- Meta
    ContractStatus NVARCHAR(50) DEFAULT 'Running',
    -- Submitted, Approved, Rejected
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    -- New Fields (Store Contract)
    EmployeeName NVARCHAR(255) NULL,
    OfficeAddress NVARCHAR(255) NULL,
    FinalPrice FLOAT NULL,
    -- New Fields (Provider Offer)
    MeetRequirement NVARCHAR(50) NULL
  );
CREATE UNIQUE INDEX UX_Contracts_ContractId ON dbo.Contracts(ContractId);
GO