"""Main entry point: parse args and dispatch to CLI methods."""

from __future__ import annotations

import argparse
import json
import os
import sys

from issuedb.cli._parser import build_parser


def _missing_subcommand(parser: argparse.ArgumentParser, command: str, choices: str) -> None:
    """Report a missing subcommand as a usage error (stderr, exit code 2)."""
    print(
        f"{parser.prog} {command}: error: a subcommand is required ({choices})",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(2)


def main() -> None:
    """Main entry point for the CLI."""
    parser = build_parser()

    args = parser.parse_args()

    # Handle --prompt flag
    if args.prompt:
        from pathlib import Path

        # Get the prompt file path
        package_dir = Path(__file__).parent.parent
        prompt_file = package_dir / "data" / "agents" / "PROMPT.txt"

        if prompt_file.exists():
            print(prompt_file.read_text(), file=sys.stdout, flush=True)
        else:
            print(f"Error: Prompt file not found at {prompt_file}", file=sys.stderr, flush=True)
            sys.exit(1)
        sys.exit(0)

    # Handle --ollama flag
    if args.ollama:
        from pathlib import Path

        from issuedb.ollama_client import handle_ollama_request

        # Join the list of words into a single request string
        user_request = " ".join(args.ollama)

        if not user_request.strip():
            print("Error: No request provided for --ollama", file=sys.stderr)
            sys.exit(1)

        # Get the prompt file path
        package_dir = Path(__file__).parent.parent
        prompt_file = package_dir / "data" / "agents" / "PROMPT.txt"

        if not prompt_file.exists():
            print(f"Error: Prompt file not found at {prompt_file}", file=sys.stderr)
            sys.exit(1)

        prompt_text = prompt_file.read_text()

        # Handle Ollama request
        exit_code = handle_ollama_request(
            user_request=user_request,
            prompt_text=prompt_text,
            host=args.ollama_host,
            port=args.ollama_port,
            model=args.ollama_model,
            dry_run=args.ollama_dry_run,
        )
        sys.exit(exit_code)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Auth commands SHORT-CIRCUIT HERE, before CLI(args.db) below. That
    # constructor creates .issue.db in the current directory when it is
    # absent, which is right for `create` and wrong for `signin`: signing in
    # is a statement about this machine, not about whatever directory the user
    # happens to be standing in. Dispatching these after it would leave a
    # mystery database behind in a home directory or a repo the user never
    # meant to track.
    if args.command in ("signin", "signout", "whoami"):
        from issuedb.sync import _auth_commands

        if args.command == "signin":
            sys.exit(_auth_commands.signin(token=args.token, server=args.server))
        if args.command == "signout":
            sys.exit(
                _auth_commands.signout(server=args.server, all_servers=args.all_servers)
            )
        sys.exit(_auth_commands.whoami(server=args.server))

    try:
        from issuedb.cli import CLI

        cli = CLI(args.db)

        if args.command == "create":
            result = cli.create_issue(
                title=args.title,
                description=args.description,
                priority=args.priority,
                status=args.status,
                due_date=args.due_date,
                as_json=args.json,
                tags=args.tags,
                check_duplicates=args.check_duplicates,
                force=args.force,
                template=args.template,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "templates":
            print(cli.list_templates(as_json=args.json), file=sys.stdout, flush=True)

        elif args.command == "list":
            result = cli.list_issues(
                status=args.status,
                priority=args.priority,
                limit=args.limit,
                due_date=args.due_date,
                tag=args.tag,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "get":
            result = cli.get_issue(args.id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "update":
            updates = {}
            if args.title:
                updates["title"] = args.title
            # description/due_date use "is not None" so an explicit empty string
            # (e.g. -d "" / --due-date "") clears the field instead of being ignored.
            if args.description is not None:
                updates["description"] = args.description
            if args.priority:
                updates["priority"] = args.priority
            if args.status:
                updates["status"] = args.status
            if args.due_date is not None:
                updates["due_date"] = args.due_date

            if not updates:
                print("Error: No updates specified", file=sys.stderr, flush=True)
                sys.exit(1)

            result = cli.update_issue(args.id, as_json=args.json, **updates)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "memory":
            if not args.memory_command:
                _missing_subcommand(parser, "memory", "add/list/update/delete")

            if args.memory_command == "add":
                result = cli.memory_add(args.key, args.value, args.category, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.memory_command == "list":
                result = cli.memory_list(args.category, args.search, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.memory_command == "update":
                result = cli.memory_update(args.key, args.value, args.category, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.memory_command == "delete":
                print(cli.memory_delete(args.key, args.json), file=sys.stdout, flush=True)

        elif args.command == "lesson":
            if not args.lesson_command:
                _missing_subcommand(parser, "lesson", "add/list")

            if args.lesson_command == "add":
                result = cli.lesson_add(args.lesson, args.issue_id, args.category, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.lesson_command == "list":
                result = cli.lesson_list(args.issue_id, args.category, args.json)
                print(result, file=sys.stdout, flush=True)

        elif args.command == "tag":
            if not args.tag_command:
                _missing_subcommand(parser, "tag", "list/add/remove")

            if args.tag_command == "list":
                print(cli.tag_list(args.json), file=sys.stdout, flush=True)
            elif args.tag_command == "add":
                result = cli.tag_issue(args.issue_id, args.tags, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.tag_command == "remove":
                result = cli.untag_issue(args.issue_id, args.tags, args.json)
                print(result, file=sys.stdout, flush=True)

        elif args.command == "link":
            if not args.link_command:
                _missing_subcommand(parser, "link", "add/remove")

            if args.link_command == "add":
                result = cli.link_issues(args.source, args.target, args.type, args.json)
                print(result, file=sys.stdout, flush=True)
            elif args.link_command == "remove":
                result = cli.unlink_issues(args.source, args.target, args.type, args.json)
                print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-update":
            if not args.status and not args.priority:
                msg = "Error: No updates specified (use -s or --priority)"
                print(msg, file=sys.stderr, flush=True)
                sys.exit(1)

            if not args.filter_status and not args.filter_priority and not args.all:
                msg = (
                    "Error: refusing to update ALL issues without a filter. "
                    "Use --filter-status/--filter-priority, or pass --all to confirm."
                )
                print(msg, file=sys.stderr, flush=True)
                sys.exit(1)

            result = cli.bulk_update_issues(
                new_status=args.status,
                new_priority=args.priority,
                filter_status=args.filter_status,
                filter_priority=args.filter_priority,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "delete":
            result = cli.delete_issue(args.id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "get-next":
            result = cli.get_next_issue(status=args.status, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "get-last":
            result = cli.get_last_fetched(limit=args.number, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "search":
            result = cli.search_issues(
                keyword=args.keyword,
                limit=args.limit,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "clear":
            result = cli.clear_all(confirm=args.confirm, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "audit":
            result = cli.get_audit_logs(issue_id=args.issue, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "info":
            result = cli.get_info(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "summary":
            result = cli.get_summary(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "report":
            result = cli.get_report(group_by=args.group_by, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-create":
            # Get JSON input from file, data arg, or stdin
            json_input = None
            if args.data:
                json_input = args.data
            elif args.file:
                with open(args.file) as f:
                    json_input = f.read()
            else:
                # Read from stdin
                json_input = sys.stdin.read()

            result = cli.bulk_create(json_input, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-update-json":
            # Get JSON input from file, data arg, or stdin
            json_input = None
            if args.data:
                json_input = args.data
            elif args.file:
                with open(args.file) as f:
                    json_input = f.read()
            else:
                # Read from stdin
                json_input = sys.stdin.read()

            result = cli.bulk_update_json(json_input, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-close":
            # Get JSON input from file, data arg, or stdin
            json_input = None
            if args.data:
                json_input = args.data
            elif args.file:
                with open(args.file) as f:
                    json_input = f.read()
            else:
                # Read from stdin
                json_input = sys.stdin.read()

            result = cli.bulk_close(json_input, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "comment":
            result = cli.add_comment(args.issue_id, args.text, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "list-comments":
            result = cli.list_comments(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "delete-comment":
            result = cli.delete_comment(args.comment_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "context":
            result = cli.get_issue_context(
                args.issue_id,
                as_json=args.json,
                compact=args.compact,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "block":
            result = cli.block_issue(
                issue_id=args.issue_id,
                blocker_id=args.blocker_id,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "unblock":
            result = cli.unblock_issue(
                issue_id=args.issue_id,
                blocker_id=args.blocker_id,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "deps":
            result = cli.show_dependencies(
                issue_id=args.issue_id,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "blocked":
            result = cli.list_blocked_issues(
                status=args.status,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "workspace":
            result = cli.workspace_status(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "start":
            result = cli.start_issue_workspace(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "stop":
            result = cli.stop_issue_workspace(close=args.close, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "active":
            result = cli.get_active_issue_workspace(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "timer-start":
            result = cli.timer_start(args.issue_id, note=args.note, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "timer-stop":
            result = cli.timer_stop(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "timer-status":
            result = cli.timer_status(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "estimate":
            result = cli.set_estimate(args.issue_id, args.hours, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "time-log":
            result = cli.time_log(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "time-report":
            result = cli.time_report(
                period=args.period, issue_id=args.issue_id, as_json=args.json
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "attach":
            result = cli.attach_code_reference(
                args.issue_id, args.file_spec, note=args.note, as_json=args.json
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "detach":
            result = cli.detach_code_reference(
                args.issue_id,
                file_path=args.file_path,
                reference_id=args.reference_id,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "refs":
            result = cli.list_code_references(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "affected":
            result = cli.list_affected_issues(args.file_path, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-close-pattern":
            if not args.title_pattern and not args.desc_pattern:
                print(
                    "Error: provide --title and/or --desc pattern", file=sys.stderr, flush=True
                )
                sys.exit(1)
            result = cli.bulk_close_pattern(
                title_pattern=args.title_pattern,
                desc_pattern=args.desc_pattern,
                use_regex=args.use_regex,
                dry_run=args.dry_run,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-update-pattern":
            if not args.title_pattern and not args.desc_pattern:
                print(
                    "Error: provide --title and/or --desc pattern", file=sys.stderr, flush=True
                )
                sys.exit(1)
            if not args.new_status and not args.new_priority:
                print(
                    "Error: provide -s/--status and/or --priority to set",
                    file=sys.stderr,
                    flush=True,
                )
                sys.exit(1)
            result = cli.bulk_update_pattern(
                title_pattern=args.title_pattern,
                desc_pattern=args.desc_pattern,
                use_regex=args.use_regex,
                new_status=args.new_status,
                new_priority=args.new_priority,
                dry_run=args.dry_run,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "bulk-delete-pattern":
            if not args.title_pattern and not args.desc_pattern:
                print(
                    "Error: provide --title and/or --desc pattern", file=sys.stderr, flush=True
                )
                sys.exit(1)
            result = cli.bulk_delete_pattern(
                title_pattern=args.title_pattern,
                desc_pattern=args.desc_pattern,
                use_regex=args.use_regex,
                confirm=args.confirm,
                dry_run=args.dry_run,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "find-similar":
            result = cli.find_similar_issues(
                args.query, threshold=args.threshold, limit=args.limit, as_json=args.json
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command in ("dedupe", "find-duplicates"):
            result = cli.find_duplicates(threshold=args.threshold, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "git-link":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            if args.commit:
                result = git_cli.link_commit(args.issue_id, args.commit, as_json=args.json)
            else:
                result = git_cli.link_branch(args.issue_id, args.branch, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "git-unlink":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.unlink(
                args.issue_id,
                commit_hash=args.commit,
                branch_name=args.branch,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "git-links":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.list_links(args.issue_id, as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "git-linked":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.find_linked_issues(
                commit_hash=args.commit,
                branch_name=args.branch,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "git-scan":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.git_scan(
                num_commits=args.num_commits,
                auto_close=args.auto_close,
                as_json=args.json,
            )
            print(result, file=sys.stdout, flush=True)

        elif args.command == "git-status":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.git_status(as_json=args.json)
            print(result, file=sys.stdout, flush=True)

        elif args.command == "web":
            from issuedb.web import run_server

            run_server(host=args.host, port=args.port, debug=args.debug, db_path=args.db)

    except BrokenPipeError:
        # The reader (e.g. `issuedb-cli list | head`) closed the pipe. Point
        # stdout at devnull so the interpreter's final flush doesn't raise
        # again, and exit with the conventional SIGPIPE code.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(141)
    except Exception as e:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(e)}), file=sys.stderr, flush=True)
        else:
            print(f"Error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
