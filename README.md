# Property Management Suite

Property Management Suite is a full-featured desktop application developed to streamline rental property operations through automation, structured data management, and financial record keeping.

The system integrates tenant onboarding, utility billing, financial ledger accounting, document management, security deposit reconciliation, and archival workflows into a unified offline-first platform. Designed with a normalized SQLite database architecture and modular Python codebase, the project emphasizes data integrity, auditability, and long-term maintainability.

### Technical Highlights

* Relational database design using SQLite with foreign key constraints
* Multi-module software architecture for scalability and maintainability
* Financial ledger system supporting historical transaction auditing
* Dynamic utility billing with versioned rate tracking
* Automated move-out reconciliation and archival workflows
* Binary document and image storage support
* Offline-first desktop deployment with local data persistence
* Custom GUI built for real-world property management operations

### Skills Demonstrated

* Software Engineering
* Database Design & Normalization
* Object-Oriented Programming
* Data Modeling
* Financial Systems Development
* Desktop Application Development
* File Management & Data Archiving
* User Interface Design
* System Architecture

This project was developed to explore the design and implementation of enterprise-style management software while solving practical challenges faced by landlords, hostel operators, and property managers.

### Tech Stack Used
* Python 3.x
* CustomTkinter
* SQLite3
* Tkinter
* Object-Oriented Programming
* File System Management
* Desktop Application Development

### Architecture
GUI Layer (CustomTkinter)  
        │  
        ▼  
Business Logic Layer  
        │  
        ▼  
Database Manager  
        │  
        ▼  
SQLite Database  
        │  
        ├── Tenants  
        ├── Financial Ledger  
        ├── Utility Logs  
        └── Rate Matrix  
