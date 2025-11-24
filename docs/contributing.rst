Contributing
============

We welcome contributions to IssueDB! This guide will help you get started.

Getting Started
---------------

Prerequisites
~~~~~~~~~~~~~

- Python 3.8 or higher
- Git
- pip

Development Setup
~~~~~~~~~~~~~~~~~

1. **Clone the repository:**

   .. code-block:: bash

      git clone https://github.com/yourusername/issuedb.git
      cd issuedb

2. **Create a virtual environment:**

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate

3. **Install in development mode:**

   .. code-block:: bash

      pip install -e ".[dev]"

4. **Verify installation:**

   .. code-block:: bash

      issuedb-cli --help
      pytest

Development Workflow
--------------------

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=issuedb --cov-report=html

   # Run specific test file
   pytest tests/test_repository.py

   # Run specific test
   pytest tests/test_repository.py::test_create_issue

Code Quality
~~~~~~~~~~~~

We use several tools to maintain code quality:

**Ruff (linting and formatting):**

.. code-block:: bash

   # Check for issues
   ruff check .

   # Auto-fix issues
   ruff check --fix .

   # Format code
   ruff format .

**Mypy (type checking):**

.. code-block:: bash

   mypy issuedb/

**Run all checks:**

.. code-block:: bash

   ruff check . && ruff format --check . && mypy issuedb/ && pytest

Building Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   cd docs
   pip install -r requirements.txt
   sphinx-build -b html . _build

   # View locally
   python -m http.server -d _build 8000
   # Open http://localhost:8000

Code Style
----------

General Guidelines
~~~~~~~~~~~~~~~~~~

- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Write docstrings for public functions and classes
- Keep functions focused and small
- Prefer clarity over cleverness

Type Hints
~~~~~~~~~~

All functions should have type hints:

.. code-block:: python

   from typing import Optional, List

   def get_issue(issue_id: int) -> Optional[Issue]:
       """Get an issue by ID.

       Args:
           issue_id: The issue ID to retrieve

       Returns:
           Issue object if found, None otherwise
       """
       pass

Docstrings
~~~~~~~~~~

Use Google-style docstrings:

.. code-block:: python

   def create_issue(title: str, priority: str = "medium") -> Issue:
       """Create a new issue.

       Args:
           title: The issue title (required)
           priority: Priority level (default: medium)

       Returns:
           The created Issue object with ID populated

       Raises:
           ValueError: If title is empty
       """
       pass

Testing
-------

Test Structure
~~~~~~~~~~~~~~

Tests are located in the ``tests/`` directory:

.. code-block:: text

   tests/
   ├── __init__.py
   ├── conftest.py        # Shared fixtures
   ├── test_cli.py        # CLI tests
   ├── test_comments.py   # Comment functionality tests
   ├── test_models.py     # Model tests
   └── test_repository.py # Repository tests

Writing Tests
~~~~~~~~~~~~~

.. code-block:: python

   import pytest
   from issuedb.repository import IssueRepository
   from issuedb.models import Issue

   @pytest.fixture
   def repo():
       """Create a fresh in-memory repository for each test."""
       return IssueRepository(":memory:")

   def test_create_issue(repo):
       """Test creating a basic issue."""
       issue = repo.create_issue(Issue(title="Test issue"))

       assert issue.id is not None
       assert issue.title == "Test issue"
       assert issue.status.value == "open"

   def test_create_issue_without_title(repo):
       """Test that creating issue without title raises error."""
       with pytest.raises(ValueError, match="Title is required"):
           repo.create_issue(Issue(title=""))

Test Coverage
~~~~~~~~~~~~~

We aim for high test coverage. Check coverage with:

.. code-block:: bash

   pytest --cov=issuedb --cov-report=term-missing

   # Generate HTML report
   pytest --cov=issuedb --cov-report=html
   open htmlcov/index.html

Pull Request Process
--------------------

1. **Fork the repository** on GitHub

2. **Create a feature branch:**

   .. code-block:: bash

      git checkout -b feature/your-feature-name

3. **Make your changes:**

   - Write code
   - Add tests
   - Update documentation

4. **Run quality checks:**

   .. code-block:: bash

      ruff check . && mypy issuedb/ && pytest

5. **Commit your changes:**

   .. code-block:: bash

      git add .
      git commit -m "Add feature: description of changes"

6. **Push to your fork:**

   .. code-block:: bash

      git push origin feature/your-feature-name

7. **Create a Pull Request** on GitHub

Pull Request Guidelines
~~~~~~~~~~~~~~~~~~~~~~~

- Provide a clear description of the changes
- Reference any related issues
- Include tests for new functionality
- Update documentation as needed
- Keep changes focused and atomic

Commit Messages
~~~~~~~~~~~~~~~

Follow conventional commit format:

.. code-block:: text

   type: short description

   Longer description if needed.

   Fixes #123

Types:

- ``feat``: New feature
- ``fix``: Bug fix
- ``docs``: Documentation only
- ``test``: Adding tests
- ``refactor``: Code refactoring
- ``chore``: Maintenance tasks

Examples:

.. code-block:: text

   feat: add bulk close command

   fix: handle empty title validation

   docs: update CLI reference with new commands

   test: add tests for comment deletion

Issue Guidelines
----------------

Reporting Bugs
~~~~~~~~~~~~~~

When reporting bugs, please include:

1. **Python version:** ``python --version``
2. **IssueDB version:** ``pip show issuedb``
3. **Operating system**
4. **Steps to reproduce**
5. **Expected behavior**
6. **Actual behavior**
7. **Error messages** (if any)

Feature Requests
~~~~~~~~~~~~~~~~

For feature requests:

1. Check existing issues first
2. Describe the use case
3. Explain why it would be useful
4. Provide examples if possible

Release Process
---------------

(For maintainers)

1. Update version in ``pyproject.toml``
2. Update ``CHANGELOG.md``
3. Create git tag:

   .. code-block:: bash

      git tag -a v2.2.0 -m "Version 2.2.0"
      git push origin v2.2.0

4. Build and publish:

   .. code-block:: bash

      python -m build
      twine upload dist/*

License
-------

By contributing to IssueDB, you agree that your contributions will be licensed under the MIT License.

Questions?
----------

- Open an issue for questions
- Check existing documentation
- Review closed issues for similar problems

Thank you for contributing to IssueDB!
