"""Tests for issue templates functionality."""

import tempfile

import pytest

from issuedb.models import Issue, IssueTemplate, Priority, Status
from issuedb.repository import IssueRepository


class TestIssueTemplates:
    """Test issue template functionality."""

    @pytest.fixture
    def repo(self):
        """Create a repository with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            repo = IssueRepository(f.name)
            yield repo

    def test_builtin_templates_created(self, repo):
        """Test that built-in templates are created on database initialization."""
        templates = repo.list_templates()

        # Should have 3 built-in templates
        assert len(templates) >= 3

        template_names = [t.name for t in templates]
        assert "bug" in template_names
        assert "feature" in template_names
        assert "task" in template_names

    def test_get_builtin_bug_template(self, repo):
        """Test getting the built-in bug template."""
        template = repo.get_template("bug")

        assert template is not None
        assert template.name == "bug"
        assert template.title_prefix == "[BUG]"
        assert template.default_priority == "high"
        assert template.default_status == "open"
        assert "description" in template.required_fields
        assert "description" in template.field_prompts

    def test_get_builtin_feature_template(self, repo):
        """Test getting the built-in feature template."""
        template = repo.get_template("feature")

        assert template is not None
        assert template.name == "feature"
        assert template.title_prefix == "[FEATURE]"
        assert template.default_priority == "medium"
        assert template.default_status == "open"
        assert "description" in template.required_fields

    def test_get_builtin_task_template(self, repo):
        """Test getting the built-in task template."""
        template = repo.get_template("task")

        assert template is not None
        assert template.name == "task"
        assert template.title_prefix == "[TASK]"
        assert template.default_priority == "low"
        assert template.default_status == "open"
        assert len(template.required_fields) == 0  # No required fields

    def test_create_custom_template(self, repo):
        """Test creating a custom template."""
        template = repo.create_template(
            name="custom",
            title_prefix="[CUSTOM]",
            default_priority="medium",
            default_status="open",
            required_fields=["description", "priority"],
            field_prompts={
                "description": "Provide details",
                "priority": "Set priority level",
            },
        )

        assert template.id is not None
        assert template.name == "custom"
        assert template.title_prefix == "[CUSTOM]"
        assert template.default_priority == "medium"
        assert "description" in template.required_fields
        assert "priority" in template.required_fields

    def test_create_template_duplicate_name(self, repo):
        """Test that creating a template with duplicate name fails."""
        repo.create_template(name="duplicate")

        with pytest.raises(ValueError, match="already exists"):
            repo.create_template(name="duplicate")

    def test_create_template_empty_name(self, repo):
        """Test that creating a template with empty name fails."""
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.create_template(name="")

        with pytest.raises(ValueError, match="cannot be empty"):
            repo.create_template(name="   ")

    def test_create_template_invalid_priority(self, repo):
        """Test that creating a template with invalid priority fails."""
        with pytest.raises(ValueError, match="Invalid priority"):
            repo.create_template(
                name="test",
                default_priority="invalid",
            )

    def test_create_template_invalid_status(self, repo):
        """Test that creating a template with invalid status fails."""
        with pytest.raises(ValueError, match="Invalid status"):
            repo.create_template(
                name="test",
                default_status="invalid",
            )

    def test_create_template_invalid_required_field(self, repo):
        """Test that creating a template with invalid required field fails."""
        with pytest.raises(ValueError, match="Invalid field names"):
            repo.create_template(
                name="test",
                required_fields=["invalid_field"],
            )

    def test_list_templates(self, repo):
        """Test listing templates."""
        # Create custom templates
        repo.create_template(name="custom1")
        repo.create_template(name="custom2")

        templates = repo.list_templates()

        # Should have built-in + custom templates
        assert len(templates) >= 5  # 3 built-in + 2 custom

        # Should be sorted by name
        template_names = [t.name for t in templates]
        assert template_names == sorted(template_names)

    def test_get_template_not_found(self, repo):
        """Test getting a non-existent template returns None."""
        template = repo.get_template("nonexistent")
        assert template is None

    def test_delete_template(self, repo):
        """Test deleting a template."""
        repo.create_template(name="to_delete")

        # Verify it exists
        assert repo.get_template("to_delete") is not None

        # Delete it
        deleted = repo.delete_template("to_delete")
        assert deleted is True

        # Verify it's gone
        assert repo.get_template("to_delete") is None

    def test_delete_template_not_found(self, repo):
        """Test deleting a non-existent template returns False."""
        deleted = repo.delete_template("nonexistent")
        assert deleted is False

    def test_validate_against_template_success(self, repo):
        """Test validation passes with all required fields."""
        template = repo.get_template("bug")

        issue_data = {
            "title": "Bug title",
            "description": "Bug description",
            "priority": "high",
        }

        errors = repo.validate_against_template(template, issue_data)
        assert len(errors) == 0

    def test_validate_against_template_missing_required(self, repo):
        """Test validation fails with missing required fields."""
        template = repo.get_template("bug")

        issue_data = {
            "title": "Bug title",
            # Missing description
        }

        errors = repo.validate_against_template(template, issue_data)
        assert len(errors) > 0
        assert any("description" in error.lower() for error in errors)

    def test_validate_against_template_custom_prompt(self, repo):
        """Test validation shows custom field prompts."""
        template = repo.create_template(
            name="test",
            required_fields=["description"],
            field_prompts={"description": "Please provide detailed description"},
        )

        issue_data = {"title": "Test"}

        errors = repo.validate_against_template(template, issue_data)
        assert len(errors) == 1
        assert "Please provide detailed description" in errors[0]

    def test_template_to_dict(self, repo):
        """Test converting template to dictionary."""
        template = repo.get_template("bug")
        template_dict = template.to_dict()

        assert template_dict["name"] == "bug"
        assert template_dict["title_prefix"] == "[BUG]"
        assert template_dict["default_priority"] == "high"
        assert isinstance(template_dict["required_fields"], list)
        assert isinstance(template_dict["field_prompts"], dict)

    def test_template_from_dict(self, repo):
        """Test creating template from dictionary."""
        template_data = {
            "name": "from_dict",
            "title_prefix": "[TEST]",
            "default_priority": "low",
            "default_status": "open",
            "required_fields": ["description"],
            "field_prompts": {"description": "Test prompt"},
        }

        template = IssueTemplate.from_dict(template_data)

        assert template.name == "from_dict"
        assert template.title_prefix == "[TEST]"
        assert template.default_priority == "low"
        assert "description" in template.required_fields

    def test_create_issue_with_template_title_prefix(self, repo):
        """Test creating issue applies template title prefix."""
        template = repo.get_template("bug")

        # Create issue
        issue = Issue(
            title="Memory leak",
            description="Application crashes",
            priority=Priority.HIGH,
        )

        # Apply title prefix from template
        if template.title_prefix:
            issue.title = f"{template.title_prefix} {issue.title}"

        created = repo.create_issue(issue)

        assert created.title == "[BUG] Memory leak"

    def test_create_issue_with_template_defaults(self, repo):
        """Test creating issue applies template defaults."""
        template = repo.get_template("feature")

        # Create issue with template defaults
        issue = Issue(
            title="New feature request",
            description="Add export functionality",
        )

        # Apply defaults from template
        if template.default_priority:
            issue.priority = Priority.from_string(template.default_priority)
        if template.default_status:
            issue.status = Status.from_string(template.default_status)

        created = repo.create_issue(issue)

        assert created.priority == Priority.MEDIUM  # Default from feature template
        assert created.status == Status.OPEN

    def test_template_validation_empty_field(self, repo):
        """Test validation treats empty string as missing."""
        template = repo.get_template("bug")

        issue_data = {
            "title": "Bug",
            "description": "",  # Empty string
        }

        errors = repo.validate_against_template(template, issue_data)
        assert len(errors) > 0

    def test_template_no_required_fields(self, repo):
        """Test template with no required fields."""
        template = repo.get_template("task")

        issue_data = {"title": "Simple task"}

        errors = repo.validate_against_template(template, issue_data)
        assert len(errors) == 0

    def test_template_multiple_required_fields_missing(self, repo):
        """Test validation with multiple missing required fields."""
        template = repo.create_template(
            name="strict",
            required_fields=["description", "priority", "status"],
        )

        issue_data = {"title": "Test"}

        errors = repo.validate_against_template(template, issue_data)
        assert len(errors) == 3  # All three fields missing

    def test_template_persistence(self, repo):
        """Test that templates persist across repository instances."""
        # Create a template
        repo.create_template(
            name="persist_test",
            title_prefix="[PERSIST]",
        )

        # Get the database path
        db_path = repo.db.db_path

        # Create new repository instance with same database
        repo2 = IssueRepository(str(db_path))

        # Template should still exist
        template = repo2.get_template("persist_test")
        assert template is not None
        assert template.name == "persist_test"
        assert template.title_prefix == "[PERSIST]"
