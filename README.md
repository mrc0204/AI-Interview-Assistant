# AI Interview Assistant

An AI-powered voice interview assistant that conducts adaptive technical and communication interviews, converts spoken answers to text, generates contextual follow-up questions, and produces AI-driven interview feedback.

## Features

- 🎙️ Voice-based interview experience
- 🤖 Adaptive questions powered by Gemini 2.5 Flash
- 🧠 LangGraph-based conversation state
- 🗣️ AssemblyAI speech-to-text
- 🔊 Murf AI text-to-speech
- 📊 AI-generated score and feedback
- 🎯 Five-question interview flow
- 💻 Modern responsive web interface
- 🔐 API keys loaded through environment variables
- 🧵 Unique interview session IDs so concurrent browser sessions do not share interview state

## Tech Stack

**Frontend:** HTML, CSS, JavaScript, Tailwind CSS, Font Awesome

**Backend:** Python, Flask, Flask-CORS

**AI / Voice:** Gemini 2.5 Flash, LangChain, LangGraph, AssemblyAI, Murf AI

## Project Structure

```text
AI-Interview-Assistant/
├── backend/
│   └── app.py
├── frontend/
│   ├── index.html
│   └── index.js
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Local Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd AI-Interview-Assistant
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

Copy `.env.example` to `.env` and add your own API keys:

```text
GOOGLE_API_KEY=...
MURF_API_KEY=...
ASSEMBLYAI_API_KEY=...
```

**Never commit `.env` or API keys to GitHub.**

### 5. Run the application

```bash
python backend/app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Production Deployment

The Flask application serves the frontend and backend from the same service, so the browser uses same-origin API routes such as `/start-interview` and `/submit-answer`.

Recommended production start command:

```bash
gunicorn --chdir backend app:app
```

Configure the following environment variables in your hosting provider:

- `GOOGLE_API_KEY`
- `MURF_API_KEY`
- `ASSEMBLYAI_API_KEY`
- `PORT` (if required by the provider)

Health check: `GET /health` should return `{ "status": "ok" }`.

### Production note

The current implementation stores session metadata and LangGraph checkpoints in process memory. This is suitable for a portfolio/demo deployment on a single server instance. For horizontal scaling or high traffic, replace `InMemorySaver` and the in-memory session dictionary with a shared store such as Redis or a database.

## Security Notes

- API keys are read only from environment variables.
- `.env` is excluded by `.gitignore`.
- Interview state is isolated using a unique session ID per interview.
- For a public high-traffic deployment, add authentication, rate limiting, request-size limits, and a shared persistent session/checkpoint store.

## Resume Description

**AI Interview Assistant | Python, Flask, LangGraph, Gemini, AssemblyAI, Murf AI**

Built an AI-powered voice interview platform that conducts adaptive five-question interviews using Gemini and LangGraph, dynamically generating follow-up questions based on candidate responses. Integrated AssemblyAI for speech-to-text and Murf AI for text-to-speech, and implemented an automated evaluation pipeline that generates interview scores, strengths, and areas for improvement.

## Vercel Deployment

This repository is configured for Vercel's Python runtime with Flask. The Vercel entrypoint is `api/index.py`, which imports the Flask app from `backend/app.py`.

1. Import the GitHub repository into Vercel.
2. Keep the project root as the repository root.
3. Add these Environment Variables in Vercel:
   - `GOOGLE_API_KEY`
   - `MURF_API_KEY`
   - `ASSEMBLYAI_API_KEY`
4. Deploy. Vercel will install dependencies from `requirements.txt`.

The frontend and API use the same origin, so no frontend API hostname or CORS configuration is required.
