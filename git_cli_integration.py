"""
Integration code for git commands in CLI.

This file contains:
1. Argument parser additions to add to main()
2. Command handlers to add to main()
"""

# === ARGUMENT PARSERS (add before 'args = parser.parse_args()') ===

ARGUMENT_PARSERS = """
    # Git link command
    link_parser = subparsers.add_parser("link", help="Link an issue to a git commit or branch")
    link_parser.add_argument("issue_id", type=int, help="Issue ID")
    link_group = link_parser.add_mutually_exclusive_group(required=True)
    link_group.add_argument("-c", "--commit", help="Commit hash to link")
    link_group.add_argument("-b", "--branch", help="Branch name to link")

    # Git unlink command
    unlink_parser = subparsers.add_parser(
        "unlink", help="Remove git link(s) from an issue"
    )
    unlink_parser.add_argument("issue_id", type=int, help="Issue ID")
    unlink_group = unlink_parser.add_mutually_exclusive_group(required=True)
    unlink_group.add_argument("-c", "--commit", help="Commit hash to unlink")
    unlink_group.add_argument("-b", "--branch", help="Branch name to unlink")

    # Git links command
    links_parser = subparsers.add_parser("links", help="Show all git links for an issue")
    links_parser.add_argument("issue_id", type=int, help="Issue ID")

    # Git linked command
    linked_parser = subparsers.add_parser(
        "linked", help="Show issues linked to a commit or branch"
    )
    linked_group = linked_parser.add_mutually_exclusive_group(required=True)
    linked_group.add_argument("-c", "--commit", help="Commit hash")
    linked_group.add_argument("-b", "--branch", help="Branch name")

    # Git scan command
    git_scan_parser = subparsers.add_parser(
        "git-scan",
        help="Scan recent git commits for issue references and link them",
    )
    git_scan_parser.add_argument(
        "-n",
        "--num-commits",
        type=int,
        default=10,
        help="Number of recent commits to scan (default: 10)",
    )
    git_scan_parser.add_argument(
        "--auto-close",
        action="store_true",
        help="Auto-close issues with 'fixes #N' or 'closes #N' patterns",
    )

    # Git status command
    git_status_parser = subparsers.add_parser(
        "git-status", help="Show git repository status"
    )
"""

# === COMMAND HANDLERS (add before the 'except Exception' at the end of main()) ===

COMMAND_HANDLERS = """
        elif args.command == "link":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            if args.commit:
                result = git_cli.link_commit(args.issue_id, args.commit, as_json=args.json)
            else:
                result = git_cli.link_branch(args.issue_id, args.branch, as_json=args.json)
            print(result)

        elif args.command == "unlink":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.unlink(
                args.issue_id,
                commit_hash=args.commit,
                branch_name=args.branch,
                as_json=args.json,
            )
            print(result)

        elif args.command == "links":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.list_links(args.issue_id, as_json=args.json)
            print(result)

        elif args.command == "linked":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.find_linked_issues(
                commit_hash=args.commit,
                branch_name=args.branch,
                as_json=args.json,
            )
            print(result)

        elif args.command == "git-scan":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.git_scan(
                num_commits=args.num_commits,
                auto_close=args.auto_close,
                as_json=args.json,
            )
            print(result)

        elif args.command == "git-status":
            from issuedb.git_cli import GitCLI

            git_cli = GitCLI(args.db)
            result = git_cli.git_status(as_json=args.json)
            print(result)
"""

if __name__ == "__main__":
    print("This file contains integration code for git commands.")
    print("\n1. ARGUMENT_PARSERS - add before 'args = parser.parse_args()'")
    print("\n2. COMMAND_HANDLERS - add before 'except Exception' in main()")
