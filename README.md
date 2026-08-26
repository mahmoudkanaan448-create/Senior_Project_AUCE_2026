# 🛡️ AI-Based Network Intrusion Detection and Prevention System

> **Senior Project – Computer Science | AUCE | 2026–2027**

An intelligent cybersecurity platform designed to **monitor network traffic, detect suspicious behavior and cyberattacks using Artificial Intelligence, analyze threats in real time, and automatically respond to malicious activity**.

The system combines **Machine Learning, Network Security, Threat Intelligence, Real-Time Monitoring, and Automated Prevention** within a unified security dashboard.

---

## 📌 Project Overview

Modern computer networks generate large amounts of traffic every second, making traditional manual monitoring difficult and inefficient.

This project introduces an **AI-Based Network Intrusion Detection and Prevention System (IDS/IPS)** capable of analyzing network activity and identifying potentially malicious behavior.

The system is designed to provide security analysts and administrators with:

* Real-time network monitoring
* AI-based attack detection
* Anomaly detection
* Known attack detection
* Automated threat response
* Attack visualization
* Threat intelligence
* Security alerts
* AI model analysis
* Historical attack tracking

The goal is to provide a centralized and intelligent platform capable of supporting faster and more effective cybersecurity decisions.

---

# 🚀 Key Features

### 🤖 AI-Based Threat Detection

The system uses Machine Learning models to analyze network traffic and identify potentially malicious behavior.

Supported AI approaches include:

* Random Forest
* XGBoost
* Isolation Forest
* LSTM / Deep Learning
* Anomaly Detection

The system can compare different models to evaluate their detection performance.

---

### 🔍 Real-Time Network Monitoring

Network activity can be monitored through the dashboard to provide visibility into:

* Network flows
* Source IP addresses
* Destination IP addresses
* Protocols
* Ports
* Traffic behavior
* Detected attacks
* Threat severity
* Detection timestamps

---

### 🚨 Intrusion Detection System — IDS

The IDS component analyzes traffic and identifies suspicious or malicious network behavior.

Detected threats can be classified according to their:

* Attack type
* Risk level
* Confidence score
* Source
* Destination
* Detection time
* AI prediction

---

### 🛑 Intrusion Prevention System — IPS

The prevention component is designed to respond to detected threats.

Depending on configuration, the system can support:

* Automatic IP blocking
* Manual IP blocking
* Threat isolation
* Security response actions
* Block history
* Allowlist management

---

### 🧠 Anomaly Detection

The system can identify traffic patterns that differ from normal network behavior.

This makes it possible to detect potentially unknown or previously unseen attacks in addition to known attack patterns.

---

### 🌐 Threat Intelligence

Threat Intelligence capabilities help enrich suspicious network activity with additional security information.

The platform can analyze indicators such as:

* Suspicious IP addresses
* Reputation information
* External threat intelligence
* Risk scores
* Known malicious indicators

---

### 🗺️ IP Geolocation

Suspicious IP addresses can be associated with geographical information to provide additional context about detected threats.

Information may include:

* Country
* Region
* City
* Location
* IP information

---

### 📊 Security Dashboard

The dashboard provides centralized visibility into the security status of the monitored environment.

It can display:

* Total detected threats
* Network activity
* Recent attacks
* Threat severity
* Blocked IP addresses
* Attack statistics
* AI detection results
* Model performance
* System status

---

### ⏱️ Attack Timeline

Detected security events are organized chronologically, allowing users to review:

* When an attack occurred
* Source of the attack
* Destination
* Attack category
* Severity
* Detection result
* Response performed by the system

---

### 📈 AI Model Platform

The system includes functionality for evaluating and comparing AI models used for intrusion detection.

Model evaluation may include:

* Accuracy
* Precision
* Recall
* F1-Score
* ROC Curve
* Confusion Matrix
* Precision–Recall Curve

This helps determine which model performs best for different cybersecurity scenarios.

---

### 🔔 Security Alerts

The platform is designed to provide security notifications when important threats are detected.

Possible integrations include:

* Email alerts
* Telegram alerts
* Slack notifications
* SIEM integrations

---

### 🗃️ Attack History & Database

Detected events can be stored in a database for later investigation.

Stored information can include:

* Attack type
* Source IP
* Destination IP
* Protocol
* Severity
* Prediction
* Timestamp
* Blocking status

This provides a historical security record for analysis and reporting.

---

### 🔐 Authentication & Access Control

The system includes authentication mechanisms to help protect access to the cybersecurity dashboard and administrative functionality.

---

### 🧑‍💻 Security Analyst Interface

The platform is designed to simplify security monitoring by presenting technical network information through an organized graphical interface.

This allows administrators to quickly understand:

* What happened
* Where the threat originated
* How serious the threat is
* What action was taken

---

# 🏗️ System Architecture

The project follows a modular architecture connecting network monitoring, artificial intelligence, backend services, data storage, threat intelligence, and the user dashboard.

Typical processing flow:

```text
Network Traffic
      │
      ▼
Traffic Capture
      │
      ▼
Feature Extraction
      │
      ▼
Data Preprocessing
      │
      ▼
AI / ML Detection Engine
      │
      ├── Random Forest
      ├── XGBoost
      ├── Isolation Forest
      └── LSTM
      │
      ▼
Threat Classification
      │
      ├── Normal Traffic
      └── Suspicious / Malicious Traffic
      │
      ▼
Threat Intelligence & Risk Analysis
      │
      ▼
IDS / IPS Response
      │
      ├── Alert
      ├── Log
      └── Block
      │
      ▼
Database
      │
      ▼
Security Dashboard
```

---

# 🤖 Machine Learning Pipeline

The AI detection pipeline follows several stages:

```text
Dataset
   ↓
Data Cleaning
   ↓
Preprocessing
   ↓
Feature Engineering
   ↓
Train / Test Split
   ↓
Model Training
   ↓
Model Evaluation
   ↓
Model Deployment
   ↓
Real-Time Prediction
```

Multiple Machine Learning models can be evaluated to select the most appropriate model for network intrusion detection.

---

# 🧰 Technologies

## Backend

* Python
* FastAPI
* REST API

## Artificial Intelligence

* Machine Learning
* Deep Learning
* Random Forest
* XGBoost
* Isolation Forest
* LSTM
* Scikit-learn

## Data Processing

* Pandas
* NumPy

## Network Security

* Network Traffic Analysis
* Intrusion Detection
* Intrusion Prevention
* Packet / Flow Analysis
* Threat Intelligence

## Database

* SQLite
* Database-based attack history

## Development

* Visual Studio Code
* Git
* GitHub

---

# 📁 Project Structure

```text
Senior_Project_AUCE_2026/
│
├── AI_Network_Analyzer/
│   │
│   ├── ai/
│   ├── backend/
│   ├── database/
│   ├── detection/
│   ├── models/
│   ├── monitoring/
│   ├── prevention/
│   ├── threat_intelligence/
│   ├── frontend/
│   ├── tests/
│   │
│   ├── .env.example
│   ├── requirements.txt
│   └── ...
│
├── .gitignore
└── README.md
```

> The exact folder structure may evolve as development continues.

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/mahmoudkanaan448-create/Senior_Project_AUCE_2026.git
```

Then enter the project directory:

```bash
cd Senior_Project_AUCE_2026
```

---

## 2. Create a Virtual Environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r AI_Network_Analyzer/requirements.txt
```

---

# 🔑 Environment Configuration

The real `.env` file is **not included in this repository** for security reasons.

An example configuration file is provided:

```text
.env.example
```

Create your local `.env` file from the example:

```bash
copy AI_Network_Analyzer\.env.example AI_Network_Analyzer\.env
```

Then configure the services you want to use.

Example:

```env
VIRUSTOTAL_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SLACK_WEBHOOK_URL=
SPLUNK_HEC_TOKEN=
SMTP_PASSWORD=
ELASTIC_PASSWORD=
JIRA_TOKEN=
```

> ⚠️ Never commit API keys, passwords, tokens, or other secrets to GitHub.

---

# 🔐 Security

Sensitive information is intentionally excluded from the repository.

The `.gitignore` configuration prevents files such as the following from being committed:

```text
.env
.env.*
*.key
*.pem
venv/
.venv/
__pycache__/
node_modules/
```

Only `.env.example` is provided to document the required environment variables.

---

# 🖥️ Screenshots

## Main Dashboard

<img width="1600" height="900" alt="01_home" src="https://github.com/user-attachments/assets/46de9d0e-231a-4c54-9314-0da79fcdd863" />


## Real-Time Monitoring

<img width="1600" height="900" alt="02_live_monitoring" src="https://github.com/user-attachments/assets/abcc1daa-75f4-4875-ac18-a2794cae6bd3" />


## AI Detection

<img width="1600" height="900" alt="03_ai_detection" src="https://github.com/user-attachments/assets/9e6eeb03-28ea-45cd-9678-82f4d455efbd" />



## AI Model Platform

<img width="1600" height="900" alt="08_ai_models" src="https://github.com/user-attachments/assets/11ccc4cc-08e6-4667-bc9e-1a6e96903f56" />


## Threat Intelligence

<img width="1600" height="900" alt="05_threat_intelligence" src="https://github.com/user-attachments/assets/863b7044-cbee-43dc-b716-e143bb733026" />


# 📊 Model Evaluation

The system is designed to evaluate different Machine Learning models using cybersecurity-relevant performance metrics.

Typical evaluation metrics include:

| Metric                 | Purpose                               |
| ---------------------- | ------------------------------------- |
| Accuracy               | Overall prediction correctness        |
| Precision              | Accuracy of detected attacks          |
| Recall                 | Ability to detect actual attacks      |
| F1-Score               | Balance between Precision and Recall  |
| ROC-AUC                | Classification performance            |
| Confusion Matrix       | Detailed classification analysis      |
| Precision–Recall Curve | Performance on imbalanced attack data |

---

# 🎯 Project Objectives

The main objectives of this project are to:

1. Detect malicious network activity using Artificial Intelligence.
2. Identify known and unknown network anomalies.
3. Monitor network traffic in real time.
4. Automate selected intrusion prevention actions.
5. Integrate Threat Intelligence into attack analysis.
6. Provide understandable security information through a centralized dashboard.
7. Compare multiple Machine Learning models.
8. Maintain historical records of detected security events.
9. Improve the speed of cybersecurity threat identification and response.

---

# 💡 Why This Project?

Traditional Intrusion Detection Systems often rely heavily on predefined signatures and rules.

Modern cyberattacks can change rapidly, making intelligent detection increasingly important.

This project explores how **Artificial Intelligence and Machine Learning can complement traditional cybersecurity techniques** by learning patterns from network traffic and helping identify suspicious behavior.

The combination of:

**AI + IDS + IPS + Threat Intelligence + Real-Time Monitoring + Automated Response**

creates a more comprehensive cybersecurity platform.

---

# 🌍 Potential Applications

The system can be adapted for environments such as:

* Companies
* Universities
* Government networks
* Data centers
* Security Operation Centers (SOC)
* Small and medium businesses
* Research environments
* Cybersecurity laboratories

---

# 🚧 Project Status

**Active Development**

The platform is continuously being developed, tested, and improved as part of the Senior Computer Science Project.

Future improvements may include:

* Advanced Deep Learning models
* Improved attack prediction
* Additional Threat Intelligence sources
* Enhanced Explainable AI
* Cloud deployment
* Distributed network monitoring
* SIEM integrations
* Advanced security automation
* Extended real-world network testing

---

# ⚠️ Disclaimer

This project is intended for:

* Educational purposes
* Academic research
* Defensive cybersecurity
* Authorized security testing

It should only be used on networks and systems where the user has explicit authorization.

---

# 👨‍💻 Author

**Mahmoud Talal Kanaan**

Computer Science
Faculty of Science
American University of Culture and Education — AUCE
Beirut Campus

**Senior Project — 2026–2027**

---

# ⭐ Support

If you find this project interesting, consider giving the repository a ⭐ on GitHub.

Contributions, feedback, and suggestions related to defensive cybersecurity and Machine Learning are welcome.
