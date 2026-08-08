# AI Meeting & Task Assistant

AI Meeting & Task Assistant is an end-to-end AI automation application that turns meeting recordings into transcripts, concise summaries, explicit decisions, structured action items, and open questions.

The application combines a Next.js dashboard, a FastAPI processing API, local audio storage, AI transcription and analysis providers, and PostgreSQL persistence. Its main AI pipeline can run completely on a local machine without paid AI APIs by using faster-whisper and Ollama.

## How It Works

```mermaid
flowchart TD
    A["User uploads MP3, WAV, or M4A audio"] --> B["Next.js dashboard"]
    B --> C["FastAPI"]
    C --> D["Local audio storage"]
    D --> E["faster-whisper"]
    E --> F["Transcript"]
    F --> G["Ollama local LLM"]
    G --> H["Pydantic structured output validation"]
    H --> I["PostgreSQL"]
    I --> J["Dashboard results and meeting history"]
```

From the dashboard, the user provides a meeting title and recording. The frontend creates the meeting, uploads the audio, and calls the end-to-end processing endpoint. FastAPI transcribes the recording, asks the configured Ollama model for schema-constrained analysis, validates the result, and persists the meeting data for later retrieval.

## Features

- Meeting creation and persisted status lifecycle: `created`, `uploaded`, `processing`, `completed`, and `failed`
- MP3, WAV, and M4A audio upload
- Safe server-generated UUID filenames and a 50 MiB upload limit
- Local faster-whisper transcription
- Optional OpenAI Speech-to-Text provider
- Local Ollama meeting analysis with a configurable model
- Pydantic-derived JSON schema and validated structured AI output
- Summary, explicit decision, and open-question extraction
- Action-item extraction with task, assignee, deadline, and priority
- End-to-end `POST /process` workflow
- PostgreSQL persistence for meeting metadata, transcripts, analyses, and action items
- Recent meeting history and individual meeting retrieval
- Next.js dashboard with drag-and-drop upload
- Responsive loading and user-friendly error states
- Readable action-item cards and a collapsible transcript
- Swagger/OpenAPI documentation
- Alembic database migrations
- Automated backend tests with isolated external AI dependencies

The default and recommended local analysis model is `llama3.2:3b`. A different Ollama model can be selected through `OLLAMA_ANALYSIS_MODEL` without coupling the API route to a model name.

## Tech Stack

### Backend

- Python 3.12+
- FastAPI and Uvicorn
- Pydantic and pydantic-settings
- SQLAlchemy 2.x with async sessions
- asyncpg
- Alembic
- httpx

### AI

- faster-whisper for local speech-to-text
- Ollama for local LLM inference
- Configurable Ollama analysis model (`llama3.2:3b` by default)
- OpenAI Speech-to-Text as an optional transcription provider

### Database

- PostgreSQL

### Frontend

- Next.js with App Router
- TypeScript
- Tailwind CSS

### Testing

- pytest
- FastAPI dependency overrides
- Temporary isolated test database sessions
- httpx `MockTransport`

## AI Provider Architecture

Transcription uses a provider-based design. The HTTP route depends on `TranscriptionService`, while the service delegates work to the configured provider:

```text
FastAPI route
    └── TranscriptionService
            ├── local faster-whisper provider
            └── OpenAI transcription provider
```

The provider is selected with `TRANSCRIPTION_PROVIDER`. Local faster-whisper is the recommended default for development because it avoids external API credentials and usage costs. The API contract and meeting-processing workflow remain independent of the selected provider.

## Structured Meeting Analysis

The analysis model does not return arbitrary prose. The Ollama request includes a JSON schema generated from the Pydantic `MeetingAnalysis` model, disables streaming and reasoning output, and uses deterministic generation settings. The response is parsed and validated before it can be returned or persisted.

Representative output:

```json
{
  "summary": "The team confirmed the release plan and assigned the remaining integration work.",
  "decisions": ["Release the product on Monday"],
  "action_items": [
    {
      "task": "Finish the API integration",
      "assignee": "Dmytro",
      "deadline": "Friday",
      "priority": "medium"
    }
  ],
  "open_questions": []
}
```

Schema validation makes the LLM response safer to consume in automation workflows: downstream code receives predictable fields and types, while malformed or incomplete provider responses are rejected with a safe API error.

## Project Structure

```text
ai-meeting-assistant/
├── app/
│   ├── api/             # FastAPI routes and HTTP orchestration
│   ├── core/            # Environment-based application configuration
│   ├── db/              # Async SQLAlchemy setup and persistence models
│   ├── models/          # Pydantic request and response schemas
│   ├── repositories/    # Meeting-specific persistence operations
│   └── services/        # Audio, transcription, analysis, and processing logic
├── alembic/             # Versioned PostgreSQL migrations
├── frontend/            # Next.js dashboard and typed API client
├── tests/               # Isolated API, provider, workflow, and persistence tests
├── storage/             # Runtime local audio files; excluded from Git
├── alembic.ini          # Alembic configuration
├── pyproject.toml       # Python dependencies and test configuration
└── README.md
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `POST` | `/api/v1/meetings` | Create and persist a meeting |
| `GET` | `/api/v1/meetings` | List recent meetings with pagination |
| `GET` | `/api/v1/meetings/{meeting_id}` | Retrieve stored meeting details |
| `POST` | `/api/v1/meetings/{meeting_id}/audio` | Validate and store meeting audio |
| `POST` | `/api/v1/meetings/{meeting_id}/transcribe` | Transcribe previously uploaded audio |
| `POST` | `/api/v1/meetings/{meeting_id}/analyze` | Analyze a supplied transcript |
| `POST` | `/api/v1/meetings/{meeting_id}/process` | Run transcription, analysis, and persistence |

After starting the backend, interactive Swagger documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Local Development

### Prerequisites

- Python 3.12 or newer
- Node.js and npm
- PostgreSQL
- Ollama

### Backend setup

Create a virtual environment and install the application with development dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create the PostgreSQL database with your preferred administration tool or the PostgreSQL CLI:

```bash
createdb ai_meeting_assistant
```

Copy the environment template and adjust the connection credentials for your PostgreSQL installation:

```bash
cp .env.example .env
```

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_meeting_assistant
```

Apply the database migration:

```bash
alembic upgrade head
```

Start Ollama in a separate terminal:

```bash
ollama serve
```

Then install the configured default analysis model:

```bash
ollama pull llama3.2:3b
```

Start FastAPI:

```bash
uvicorn app.main:app --reload
```

The backend is available at `http://127.0.0.1:8000`.

### Frontend setup

In a separate terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment Variables

Backend variables are configured in the root `.env` file:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL connection URL |
| `TRANSCRIPTION_PROVIDER` | `local` or `openai` transcription provider |
| `LOCAL_WHISPER_MODEL` | faster-whisper model size or identifier |
| `LOCAL_WHISPER_DEVICE` | Local inference device, such as `cpu` |
| `LOCAL_WHISPER_COMPUTE_TYPE` | faster-whisper compute type, such as `int8` |
| `OPENAI_API_KEY` | Optional OpenAI credential; leave empty in local mode |
| `OPENAI_TRANSCRIPTION_MODEL` | OpenAI transcription model name |
| `OLLAMA_BASE_URL` | Ollama server URL |
| `OLLAMA_ANALYSIS_MODEL` | Ollama model used for structured analysis |

The frontend reads:

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of the FastAPI backend |

The committed `.env.example` files contain development placeholders only. The backend `.env` and frontend `.env.local` files are excluded from Git. Never commit real API keys or database credentials.

## Testing

Run the backend suite from the repository root:

```bash
pytest
```

The suite covers API validation, chunked audio storage, provider isolation, structured Ollama responses, end-to-end meeting processing, failure handling, and database persistence. Tests use dependency overrides, temporary test storage, an isolated test database, and mocked providers; they do not require a downloaded Whisper model, an OpenAI API call, or a live Ollama server.

Verify the frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Local AI and Privacy

With `TRANSCRIPTION_PROVIDER=local` and a local Ollama server, audio transcription and LLM analysis run on the same machine as the application. This reduces the need to send meeting content to third-party AI services, but the actual privacy characteristics still depend on the machine, network, configuration, and operational environment.

Uploaded audio is currently stored under `storage/audio/` on the local filesystem. Meeting metadata, transcripts, structured analyses, and action items are stored in PostgreSQL.

## Current Limitations

- Audio storage is limited to the local filesystem.
- Meeting processing is synchronous and can keep an HTTP request open for the duration of transcription and analysis.
- Authentication, users, and access controls are not implemented.
- There is no background job queue.
- Speaker diarization is not implemented.
- RAG and semantic search are not implemented.
- Cloud deployment configuration is not included.
- Local LLM output quality and hardware requirements depend on the selected model.

## Roadmap

The following items are planned ideas and are **not implemented**:

- pgvector and embedding generation
- Semantic search over meeting history
- RAG chat across meetings
- LangGraph workflow orchestration
- Google Calendar integration
- Jira integration
- Telegram or Slack notifications
- Background processing
- Docker development environment
- Authentication and user accounts
- Cloud object storage
- Cloud deployment

## What This Project Demonstrates

- End-to-end AI automation and full-stack integration
- Local inference and optional external AI providers
- LLM prompt and schema design with validated structured output
- Provider abstractions that decouple API routes from AI implementations
- REST API design and async PostgreSQL persistence
- Database schema evolution with Alembic
- Testing external AI dependencies without real API calls
