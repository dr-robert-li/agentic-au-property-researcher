# Contributing to Australian Property Research

Thank you for your interest in contributing to the Australian Property Research project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)

## Code of Conduct

This project adheres to a code of conduct that all contributors are expected to follow:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Assume good intentions
- Respect differing viewpoints and experiences

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/agentic-re-researcher.git
   cd agentic-re-researcher
   ```
3. **Set up development environment** (see below)
4. **Create a branch** for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- At least one API key for testing:
  - Perplexity API key (for Perplexity provider integration testing)
  - Anthropic API key (for Claude provider integration testing)

### Environment Setup

1. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt  # If available
   # Or install individually:
   pip install pytest mypy pylint black isort
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add at least one API key:
   # PERPLEXITY_API_KEY=your-key-here
   # ANTHROPIC_API_KEY=your-key-here
   ```

## How to Contribute

### Reporting Bugs

Before creating a bug report:
- Check if the bug has already been reported in Issues
- Verify the bug exists in the latest version
- Collect relevant information (OS, Python version, error messages)

When creating a bug report, include:
- Clear, descriptive title
- Steps to reproduce the issue
- Expected vs actual behavior
- Error messages and stack traces
- Environment details (OS, Python version)
- Screenshots if applicable

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub Issues. When creating an enhancement suggestion:
- Use a clear, descriptive title
- Provide detailed description of the proposed feature
- Explain why this enhancement would be useful
- Include examples of how it would work
- Note any potential drawbacks or alternatives considered

### Code Contributions

Areas where contributions are especially welcome:

1. **New Features**:
   - PDF/Excel export functionality
   - Data caching layer
   - Additional chart types
   - New region definitions
   - Additional AI provider integrations

2. **Improvements**:
   - Performance optimizations
   - Error handling enhancements
   - Documentation improvements
   - Test coverage expansion
   - Code refactoring

3. **Bug Fixes**:
   - Fix reported issues
   - Handle edge cases
   - Improve error messages

## Coding Standards

### Python Style Guide

This project follows [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications:

- **Line length**: 100 characters maximum (not 79)
- **Quotes**: Double quotes for strings (not single)
- **Imports**: Organized using isort
- **Formatting**: Use Black for automatic formatting

### Code Formatting

Before committing, format your code:

```bash
# Format with Black
black src/ tests/

# Sort imports
isort src/ tests/

# Check formatting without modifying
black --check src/ tests/
```

### Type Hints

- Use type hints for all function signatures
- Use Pydantic models for data validation
- Run mypy for type checking:
  ```bash
  mypy src/
  ```

### Documentation

- Add docstrings to all public functions, classes, and modules
- Use Google-style docstrings:
  ```python
  def function_name(param1: str, param2: int) -> bool:
      """
      Brief description of function.

      Args:
          param1: Description of param1
          param2: Description of param2

      Returns:
          Description of return value

      Raises:
          ValueError: Description of when this is raised
      """
      pass
  ```

## Testing Guidelines

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_perplexity.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files as `test_*.py`
- Name test functions as `test_*`
- Use descriptive test names that explain what is being tested
- Include both positive and negative test cases
- Mock external API calls when appropriate

Example test structure:

```python
def test_suburb_discovery_filters_by_price():
    """Test that suburb discovery correctly filters by max price."""
    user_input = UserInput(
        max_median_price=500000,
        dwelling_type="house",
        regions=["Test Region"]
    )
    # Test implementation
    assert result is not None
```

### Test Categories

1. **Unit Tests**: Test individual functions and classes
2. **Integration Tests**: Test component interactions
3. **API Tests**: Test Perplexity API integration (use sparingly, requires API key)
4. **Validation Tests**: Test data model validation

## Commit Messages

Write clear, descriptive commit messages:

### Format

```
<type>: <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```
feat: Add PDF export functionality

Implement PDF report generation using ReportLab.
Includes suburb reports and overview export.

Closes #42
```

```
fix: Handle missing demographic data in templates

Add null checks for household_types to prevent
template rendering errors when data is unavailable.

Fixes #56
```

## Pull Request Process

1. **Update your branch** with the latest main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-feature-branch
   git rebase main
   ```

2. **Run tests and checks**:
   ```bash
   pytest tests/
   mypy src/
   black --check src/
   pylint src/
   ```

3. **Update documentation** if needed:
   - Update README.md for new features
   - Update CHANGELOG.md
   - Add/update docstrings

4. **Create Pull Request**:
   - Use a clear, descriptive title
   - Reference related issues
   - Describe changes in detail
   - Include screenshots for UI changes
   - List any breaking changes

5. **PR Review Process**:
   - Address review feedback
   - Keep PR scope focused
   - Respond to comments promptly
   - Update PR based on feedback

6. **Merge Requirements**:
   - All tests passing
   - Code review approval
   - No merge conflicts
   - Documentation updated
   - CHANGELOG.md updated

## Project Structure

```
agentic-re-researcher/
├── src/
│   ├── config/              # Configuration and settings
│   │   ├── settings.py      # Environment and app settings
│   │   └── regions_data.py  # Region definitions
│   ├── models/              # Pydantic data models
│   │   ├── inputs.py        # User input models
│   │   ├── suburb_metrics.py # Suburb data models
│   │   └── run_result.py    # Result models
│   ├── research/            # Research and API integration
│   │   ├── perplexity_client.py  # Perplexity provider client
│   │   ├── anthropic_client.py   # Anthropic Claude provider client
│   │   ├── suburb_discovery.py
│   │   ├── suburb_research.py
│   │   └── ranking.py
│   ├── reporting/           # Report generation
│   │   ├── charts.py        # Chart generation
│   │   └── html_renderer.py # HTML rendering
│   ├── ui/                  # User interfaces
│   │   ├── web/
│   │   │   ├── server.py    # FastAPI web server
│   │   │   ├── templates/   # Jinja2 templates
│   │   │   └── static/      # CSS, JS, images
│   │   └── cli/
│   │       └── interactive.py # Interactive CLI with prompt_toolkit
│   └── app.py              # Main application orchestrator
├── tests/                   # Test suite
├── runs/                    # Output directory (gitignored)
├── .env.example            # Environment template
├── .gitignore
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── CLAUDE.md               # Project specification
```

## Development Workflow

1. **Choose an issue** to work on (or create one)
2. **Create a branch** from main
3. **Make changes** following coding standards
4. **Write/update tests** for your changes
5. **Test locally** to ensure everything works
6. **Commit changes** with clear messages
7. **Push to your fork**
8. **Create Pull Request** with description
9. **Address review feedback**
10. **Merge** once approved

## Questions?

If you have questions about contributing:

- Check existing Issues and Pull Requests
- Create a new Issue with your question
- Reach out to maintainers

Thank you for contributing to Australian Property Research!
