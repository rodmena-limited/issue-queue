Installation
============

This guide covers how to install IssueDB for different use cases.

Prerequisites
-------------

- Python 3.8 or higher
- pip package manager

Installing from PyPI
--------------------

The easiest way to install IssueDB is using pip:

.. code-block:: bash

   pip install issuedb

That's it! IssueDB has zero external dependencies - it uses only the Python standard library.

Installing from Source
----------------------

If you want to install from the source code:

.. code-block:: bash

   git clone https://github.com/rodmena-limited/issue-queue.git
   cd issue-queue
   pip install .

Development Installation
------------------------

For development purposes, you can install in editable mode with development dependencies:

.. code-block:: bash

   git clone https://github.com/rodmena-limited/issue-queue.git
   cd issue-queue
   pip install -e ".[dev]"

This installs:

- ``pytest`` for running tests
- ``mypy`` for type checking
- ``ruff`` for linting

Verification
------------

To verify that IssueDB is installed correctly:

.. code-block:: bash

   issuedb-cli --help

You should see the help output with all available commands:

.. code-block:: text

   usage: issuedb-cli [-h] [--db DB] [--json] [--prompt] [--ollama OLLAMA]
                      {create,list,get,update,...} ...

   Command-line issue tracking system for software development projects

If this runs without error, IssueDB is properly installed.

Database Location
-----------------

By default, IssueDB creates a database file named ``issuedb.sqlite`` in your current working directory. This means:

- Each project directory can have its own issue database
- Your issues live where your code lives
- You can easily backup issues by backing up the directory

To use a custom database location:

.. code-block:: bash

   issuedb-cli --db /path/to/custom.db create -t "My issue"

Shell Completion
----------------

IssueDB uses standard argparse, so you can set up shell completion using tools like ``argcomplete``:

.. code-block:: bash

   # Install argcomplete
   pip install argcomplete

   # Add to your shell profile
   eval "$(register-python-argcomplete issuedb-cli)"

Upgrading
---------

To upgrade to the latest version:

.. code-block:: bash

   pip install --upgrade issuedb

Uninstalling
------------

To remove IssueDB:

.. code-block:: bash

   pip uninstall issuedb

Note that this does not remove your database files - they remain in your project directories.
