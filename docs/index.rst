IssueDB Documentation
=====================

Welcome to the official documentation for **IssueDB**, a command-line issue tracking system for software development projects. IssueDB provides simple, concrete issue management directly from your terminal with a per-directory database model.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   cli_reference
   comments
   bulk_operations
   audit_logging

.. toctree::
   :maxdepth: 2
   :caption: Integration

   llm_agents
   json_output
   automation

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/models
   api/repository
   api/cli
   api/database

.. toctree::
   :maxdepth: 1
   :caption: Community

   contributing
   changelog


About IssueDB
-------------

IssueDB is a lightweight, zero-dependency issue tracking system that runs entirely from your command line. Each project directory gets its own SQLite database, so your issues live where your code lives.

Key Features
~~~~~~~~~~~~

- **Per-Directory Databases**: Each directory has its own ``issuedb.sqlite`` database
- **Simple Issue Management**: Create, update, delete, and list issues
- **Comments System**: Add notes and resolution comments to issues
- **Bulk Operations**: Create, update, or close multiple issues from JSON
- **Priority Levels**: Categorize issues as low, medium, high, or critical
- **Status Tracking**: Track issues through open, in-progress, and closed states
- **FIFO Queue Management**: Get the next issue to work on based on priority and creation date
- **Full-text Search**: Search issues by keyword in title and description
- **Summary & Reports**: Aggregate statistics and detailed breakdowns
- **Audit Logging**: Complete immutable history of all changes
- **JSON Output**: Machine-readable output for scripting and automation
- **LLM Agent Integration**: Built-in prompt for programmatic usage by AI agents
- **Natural Language Interface**: Ollama integration for conversational issue management
- **Zero Dependencies**: Uses only Python standard library

Why IssueDB?
~~~~~~~~~~~~

IssueDB is designed for developers who want:

1. **Simplicity**: No servers, no configuration files, no accounts
2. **Speed**: Everything runs locally on SQLite
3. **Portability**: Just a single database file per project
4. **Automation**: Full JSON output and LLM agent support
5. **Auditability**: Complete history of all changes

Perfect for:

- Solo developers managing personal projects
- Small teams that don't need enterprise issue tracking
- LLM agents that need programmatic issue management
- CI/CD pipelines that need to create/track issues
- Anyone who prefers the command line


Quick Example
~~~~~~~~~~~~~

.. code-block:: bash

   # Create an issue
   issuedb-cli create -t "Fix login bug" --priority high

   # List open issues
   issuedb-cli list -s open

   # Get the next issue to work on
   issuedb-cli get-next

   # Add a comment and close
   issuedb-cli comment 1 -t "Fixed by updating auth config"
   issuedb-cli update 1 -s closed


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
