# Contributing to Dx38 Pro Web Console

Thank you for your interest in contributing to the **Dx38 Pro Web Console** project!

## Getting Started

### 1. Fork & Clone
1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/ev-dx38-serialweb.git
   cd ev-dx38-serialweb
   ```

### 2. Set Up Environment
Create and activate a virtual environment:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## Development Workflow

### Running the Application
- **Main Console**:
  ```bash
  python app.py
  ```
  Runs at `http://127.0.0.1:5000/`. On Windows, it attempts to connect to `COM2` by default. If no hardware is attached, it falls back to Demo mode automatically.

- **Staging Console**:
  ```bash
  python -m staging
  ```
  Runs the parallel staging app at `http://127.0.0.1:5001/` in safe offline mode.

### Running Tests
Before submitting a pull request, run the test suite:

```bash
# Unit tests
python -m unittest tests.test_staging_app

# Syntax check
python -m py_compile app.py staging/app.py staging/services.py staging/routes.py staging/config.py staging/serial.py staging/state.py
```

## Pull Request Guidelines

1. Create a feature branch: `git checkout -b feature/your-feature-name`.
2. Keep commits atomic and write descriptive commit messages.
3. Ensure all tests and syntax checks pass.
4. Open a pull request against the `main` branch using the provided PR template.

## Code of Conduct

Please be respectful, constructive, and helpful when interacting with other contributors and maintainers.
