from flask import Flask, request, jsonify, Response, send_from_directory
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent
import assemblyai as aai
import base64
import json
import os
import tempfile
import threading
import uuid
import requests

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MURF_API_KEY = os.getenv("MURF_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not GOOGLE_API_KEY or not MURF_API_KEY or not ASSEMBLYAI_API_KEY:
    raise RuntimeError(
        "Missing required environment variables: GOOGLE_API_KEY, MURF_API_KEY, ASSEMBLYAI_API_KEY"
    )

aai.settings.api_key = ASSEMBLYAI_API_KEY

# A single checkpointer/agent can safely serve multiple interview threads.
# Each request is isolated by its unique thread_id.
checkpointer = InMemorySaver()
model = init_chat_model(
    "google_genai:gemini-2.5-flash-lite",
    api_key=GOOGLE_API_KEY,
)
agent = create_agent(model=model, tools=[], checkpointer=checkpointer)

# Session metadata is kept separately from the LangGraph conversation state.
# For a horizontally scaled production deployment, replace this with Redis/DB storage.
sessions = {}
sessions_lock = threading.Lock()

INTERVIEW_PROMPT = """You are Natalie, a friendly and conversational interviewer conducting a natural {subject} interview.

IMPORTANT GUIDELINES:
1. Ask exactly 5 questions total throughout the interview
2. Keep questions SHORT and CRISP (1-2 sentences maximum)
3. ALWAYS reference what the candidate ACTUALLY said in their previous answer - do NOT make up or assume their answers
4. Show genuine interest with brief acknowledgments based on their REAL responses
5. Adapt questions based on their ACTUAL responses - go deeper if they're strong, adjust if uncertain
6. Be warm and conversational but CONCISE
7. No lengthy explanations - just ask clear, direct questions

CRITICAL: Read the conversation history carefully. Only acknowledge what the candidate truly said, not what you think they might have said.

Keep it short, conversational, and adaptive!"""

FEEDBACK_PROMPT = """Based on our complete interview conversation, provide detailed feedback as JSON only:
{{
  "subject": "<topic>",
  "candidate_score": <1-5>,
  "feedback": "<detailed strengths with specific examples from their ACTUAL answers>",
  "areas_of_improvement": "<constructive suggestions based on gaps you noticed>"
}}
Be specific - reference ACTUAL things they said during the interview."""

app = Flask(__name__, static_folder="../frontend", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max uploaded audio
def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


def stream_audio(text):
    base_url = "https://global.api.murf.ai/v1/speech/stream"
    payload = {
        "text": text,
        "voiceId": "en-US-natalie",
        "model": "FALCON",
        "multiNativeLocale": "en-US",
        "sampleRate": 24000,
        "format": "MP3",
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": MURF_API_KEY,
    }

    response = requests.post(
        base_url,
        headers=headers,
        json=payload,
        stream=True,
        timeout=60,
    )
    response.raise_for_status()

    for chunk in response.iter_content(chunk_size=4096):
        if chunk:
            yield base64.b64encode(chunk).decode("utf-8") + "\n"


def speech_to_text(audio_path):
    transcriber = aai.Transcriber()
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro", "universal-2"],
        language_detection=True,
        speaker_labels=True,
    )
    transcript = transcriber.transcribe(audio_path, config=config)
    return transcript.text.strip() if transcript.text else ""


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/start-interview")
def start_interview():
    data = request.get_json(silent=True) or {}
    subject = data.get("subject", "Python")
    allowed_subjects = {"Self Introduction", "Generative AI", "Python", "English", "HTML", "CSS"}
    if subject not in allowed_subjects:
        return jsonify({"success": False, "error": "Invalid interview subject."}), 400

    session_id = str(uuid.uuid4())

    with sessions_lock:
        sessions[session_id] = {
            "subject": subject,
            "question_count": 1,
        }

    config = {"configurable": {"thread_id": session_id}}
    formatted_prompt = INTERVIEW_PROMPT.format(subject=subject)

    response = agent.invoke(
        {
            "messages": [
                {"role": "system", "content": formatted_prompt},
                {
                    "role": "user",
                    "content": f"Start the interview with a warm greeting and ask the first question about {subject}. Keep it SHORT (1-2 sentences).",
                },
            ]
        },
        config=config,
    )
    question = response["messages"][-1].content

    return Response(
        stream_audio(question),
        mimetype="text/plain",
        headers={
            "X-Interview-Session": session_id,
            "X-Question-Number": "1",
        },
    )


@app.post("/submit-answer")
def submit_answer():
    session_id = request.headers.get("X-Interview-Session")
    session = get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Invalid or expired interview session."}), 400

    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"success": False, "error": "Audio file is required."}), 400

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
            temp_path = temp_file.name
            audio_file.save(temp_path)

        answer = speech_to_text(temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    if not answer:
        answer = "[Candidate provided a verbal response]"

    question_count = session["question_count"]
    config = {"configurable": {"thread_id": session_id}}
    agent.invoke({"messages": [{"role": "user", "content": answer}]}, config=config)

    if question_count >= 5:
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "That was the 5th question. Briefly acknowledge their ACTUAL answer and let them know the interview is complete. Keep it SHORT.",
                    }
                ]
            },
            config=config,
        )
        closing_message = response["messages"][-1].content
        return Response(
            stream_audio(closing_message),
            mimetype="text/plain",
            headers={"X-Interview-Complete": "true"},
        )

    question_count += 1
    session["question_count"] = question_count

    prompt = f"""The candidate just answered question {question_count - 1}.

Look at their ACTUAL answer above. Do NOT assume or make up what they said.

Now ask question {question_count} of 5:
1. Briefly acknowledge what they ACTUALLY said (1 sentence) - quote their exact words if needed
2. Ask your next question that builds on their REAL response (1-2 sentences)
3. If they said "I don't know" or gave a wrong answer, acknowledge that and ask something simpler
4. Keep the TOTAL response under 3 sentences

Be conversational but CONCISE. Only reference what they truly said."""

    response = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config=config,
    )
    question = response["messages"][-1].content

    return Response(
        stream_audio(question),
        mimetype="text/plain",
        headers={"X-Question-Number": str(question_count)},
    )


@app.post("/get-feedback")
def get_feedback():
    session_id = request.headers.get("X-Interview-Session")
    session = get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Invalid or expired interview session."}), 400

    config = {"configurable": {"thread_id": session_id}}
    response = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"{FEEDBACK_PROMPT}\n\nReview our complete {session['subject']} interview conversation and provide detailed feedback.",
                }
            ]
        },
        config=config,
    )
    text = response["messages"][-1].content.strip()

    if "```" in text:
        parts = text.split("```")
        text = parts[1].replace("json", "", 1).strip()

    try:
        feedback = json.loads(text)
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "The AI returned invalid feedback JSON."}), 502

    return jsonify({"success": True, "feedback": feedback})


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"success": False, "error": "Audio file is too large. Maximum size is 16 MB."}), 413


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
