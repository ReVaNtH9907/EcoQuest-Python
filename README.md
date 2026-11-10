# 🌿 EcoQuest

An environmental challenge platform built with Python and Flask.

## Technology Stack

| Layer    | Technology                  |
| -------- | --------------------------- |
| Backend  | Python · Flask · Jinja2     |
| Frontend | HTML5 · CSS3 · Vanilla JS   |
| Database | SQLite (dev) → Supabase (prod) |

## Project Structure

```
EcoQuest/
├── app.py              # Application factory & entry point
├── config.py           # Dev / Prod / Test configuration
├── routes/             # Flask Blueprints (one per feature)
├── models/             # Data models (DB-agnostic)
├── services/           # Business logic layer
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, images
├── instance/           # Local SQLite DB & runtime files
└── tests/              # Automated tests
```

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd EcoQuest

# 2. Create & activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env       # then edit .env with your values

# 5. Run the development server
flask run
```

The app will be available at **http://127.0.0.1:5000**.

## Roadmap

- [x] Project architecture & Flask factory
- [ ] Supabase authentication integration
- [ ] Supabase PostgreSQL database
- [ ] Supabase Storage for media
- [ ] AI-powered mission verification
- [ ] Mission management system
- [ ] XP & leaderboard system
- [ ] Learning modules
- [ ] User profiles & dashboards

## License

All rights reserved.
