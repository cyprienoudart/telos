"""CLI entry point for the Telos agent system.

Usage:
    telos-agent interview --project-dir ./myproject
    telos-agent generate-plan --project-dir ./myproject --transcript transcript.txt
    telos-agent generate-prds --project-dir ./myproject
    telos-agent execute --project-dir ./myproject --max-iterations 10
    telos-agent run --project-dir ./myproject --transcript transcript.txt
"""

import argparse
import json
import sys
from pathlib import Path


def cmd_interview(args: argparse.Namespace) -> None:
    """Run an interview round."""
    from telos_agent.orchestrator import TelosOrchestrator

    orchestrator = TelosOrchestrator(
        project_dir=args.project_dir,
        agent_dir=args.agent_dir,
        context_dir=args.context_dir,
    )
    runner = orchestrator.interview()

    if args.transcript:
        # New flow: process transcript and generate follow-up questions
        transcript = Path(args.transcript).read_text()
        result = runner.process_round(transcript, no_more_questions=args.no_more_questions)

        if result.ready:
            print("Interview complete — sufficient context gathered.")
        else:
            print("Follow-up questions:")
            for i, q in enumerate(result.questions, 1):
                print(f"  {i}. {q}")

        # Save context
        output_path = Path(args.project_dir) / "interview-context.txt"
        output_path.write_text(transcript)
        print(f"\nTranscript saved to {output_path}")

        # Output as JSON for programmatic use
        result_json = {"ready": result.ready, "questions": result.questions}
        json_path = Path(args.project_dir) / "interview-result.json"
        json_path.write_text(json.dumps(result_json, indent=2) + "\n")
        print(f"Result saved to {json_path}")

    elif args.questions:
        # Legacy flow: structured questions
        questions = json.loads(Path(args.questions).read_text())

        answers = runner.ask_agent(questions)

        print("\n--- Agent Answers ---")
        for q, a in answers.items():
            print(f"\nQ: {q}")
            print(f"A: {a}")

        output_path = Path(args.project_dir) / "interview-context.json"
        context = runner.get_context()
        output_path.write_text(json.dumps(context, indent=2) + "\n")
        print(f"\nTranscript saved to {output_path}")

    else:
        print("Provide --transcript (new flow) or --questions (legacy flow).", file=sys.stderr)
        sys.exit(1)


def cmd_generate_plan(args: argparse.Namespace) -> None:
    """Generate a project plan from interview transcript."""
    from telos_agent.orchestrator import TelosOrchestrator

    orchestrator = TelosOrchestrator(
        project_dir=args.project_dir,
        agent_dir=args.agent_dir,
        context_dir=args.context_dir,
    )

    transcript = Path(args.transcript).read_text()
    plan_path = orchestrator.generate_plan(transcript)
    print(f"Plan generated at {plan_path}")


def cmd_generate_prds(args: argparse.Namespace) -> None:
    """Generate PRDs from plan.md."""
    from telos_agent.orchestrator import TelosOrchestrator

    orchestrator = TelosOrchestrator(
        project_dir=args.project_dir,
        agent_dir=args.agent_dir,
        context_dir=args.context_dir,
    )

    prds_dir = orchestrator.generate_prds()
    prd_files = sorted(prds_dir.glob("*.md"))
    print(f"Generated {len(prd_files)} PRD(s) in {prds_dir}:")
    for f in prd_files:
        print(f"  - {f.name}")


def cmd_generate_prd(args: argparse.Namespace) -> None:
    """Generate a single PRD from interview context (deprecated)."""
    from telos_agent.orchestrator import TelosOrchestrator

    print("Warning: generate-prd is deprecated. Use generate-plan + generate-prds instead.", file=sys.stderr)

    orchestrator = TelosOrchestrator(
        project_dir=args.project_dir,
        agent_dir=args.agent_dir,
    )

    context_path = Path(args.context)
    context = json.loads(context_path.read_text())

    prd_path = orchestrator.generate_prd(context)
    print(f"PRD generated at {prd_path}")


def _print_iteration_history(result) -> None:
    """Print iteration history from a RalphResult."""
    if not result.iteration_results:
        return
    print(f"\n--- Iteration History ---")
    for ir in result.iteration_results:
        print(f"  [{ir.iteration}] {ir.status}: {ir.details[:120]}")
    if result.denial_streak > 0:
        print(f"  Final denial streak: {result.denial_streak}")


def cmd_execute(args: argparse.Namespace) -> None:
    """Execute the Ralph loop."""
    from telos_agent.orchestrator import TelosOrchestrator

    orchestrator = TelosOrchestrator(
        project_dir=args.project_dir,
        agent_dir=args.agent_dir,
        context_dir=args.context_dir,
        max_iterations=args.max_iterations,
        model=args.model,
        timeout=args.timeout,
    )

    result = orchestrator.execute()

    _print_iteration_history(result)

    if result.success:
        print(f"\nCompleted successfully in {result.iterations} iteration(s).")
        if result.final_verdict:
            print(f"Summary: {result.final_verdict.get('summary', 'N/A')}")
    else:
        print(f"\nFailed after {result.iterations} iteration(s).", file=sys.stderr)
        if result.error:
            print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)


def cmd_run(args: argparse.Namespace) -> None:
    """Run the full workflow."""
    from telos_agent.orchestrator import TelosOrchestrator

    orchestrator = TelosOrchestrator(
        project_dir=args.project_dir,
        agent_dir=args.agent_dir,
        max_iterations=args.max_iterations,
        model=args.model,
        context_dir=args.context_dir,
        timeout=args.timeout,
    )

    if args.transcript:
        # New flow: transcript → plan → PRDs → execute
        transcript = Path(args.transcript).read_text()
        result = orchestrator.run(transcript=transcript)
    elif args.questions:
        # Legacy flow: questions → single PRD → execute
        questions = json.loads(Path(args.questions).read_text())

        def user_callback(round_num, round_questions, agent_answers):
            print(f"\n--- Round {round_num} Agent Answers ---")
            for q, a in agent_answers.items():
                print(f"\nQ: {q}")
                print(f"A: {a}")

            print(f"\n--- Your Turn (Round {round_num}) ---")
            user_answers = {}
            for q in round_questions:
                print(f"\nQ: {q}")
                answer = input("A: ").strip()
                if answer:
                    user_answers[q] = answer
            return user_answers

        result = orchestrator.run(questions=questions, user_answers_callback=user_callback)
    else:
        print("Provide --transcript (new flow) or --questions (legacy flow).", file=sys.stderr)
        sys.exit(1)

    _print_iteration_history(result)

    if result.success:
        print(f"\nCompleted successfully in {result.iterations} iteration(s).")
    else:
        print(f"\nFailed after {result.iterations} iteration(s).", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="telos-agent",
        description="Multi-agent orchestration with interview-driven planning",
    )
    parser.add_argument(
        "--agent-dir",
        type=Path,
        default=None,
        help="Path to the agent directory (default: auto-detect from package)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # interview
    p_interview = subparsers.add_parser("interview", help="Run interview rounds")
    p_interview.add_argument("--project-dir", type=Path, required=True)
    p_interview.add_argument("--transcript", type=str, help="Path to transcript text file (new flow)")
    p_interview.add_argument("--questions", type=str, help="Path to JSON file with questions (legacy)")
    p_interview.add_argument("--no-more-questions", action="store_true", help="Signal that no more questions are needed")
    p_interview.add_argument("--context-dir", type=Path, default=None)
    p_interview.set_defaults(func=cmd_interview)

    # generate-plan
    p_plan = subparsers.add_parser("generate-plan", help="Generate project plan from interview transcript")
    p_plan.add_argument("--project-dir", type=Path, required=True)
    p_plan.add_argument("--transcript", type=str, required=True, help="Path to interview transcript text file")
    p_plan.add_argument("--context-dir", type=Path, default=None)
    p_plan.set_defaults(func=cmd_generate_plan)

    # generate-prds
    p_prds = subparsers.add_parser("generate-prds", help="Generate PRDs from plan.md")
    p_prds.add_argument("--project-dir", type=Path, required=True)
    p_prds.add_argument("--context-dir", type=Path, default=None)
    p_prds.set_defaults(func=cmd_generate_prds)

    # generate-prd (deprecated alias)
    p_prd = subparsers.add_parser("generate-prd", help="(Deprecated) Generate single PRD from interview context")
    p_prd.add_argument("--project-dir", type=Path, required=True)
    p_prd.add_argument("--context", type=str, required=True, help="Path to interview context JSON")
    p_prd.set_defaults(func=cmd_generate_prd)

    # execute
    p_exec = subparsers.add_parser("execute", help="Run the Ralph loop")
    p_exec.add_argument("--project-dir", type=Path, required=True)
    p_exec.add_argument("--context-dir", type=Path, default=None)
    p_exec.add_argument("--max-iterations", type=int, default=10)
    p_exec.add_argument("--model", type=str, default="opus")
    p_exec.add_argument("--timeout", type=int, default=900, help="Per-iteration timeout in seconds (default: 900)")
    p_exec.set_defaults(func=cmd_execute)

    # run
    p_run = subparsers.add_parser("run", help="Full workflow: interview → plan → PRDs → execute")
    p_run.add_argument("--project-dir", type=Path, required=True)
    p_run.add_argument("--transcript", type=str, help="Path to transcript text file (new flow)")
    p_run.add_argument("--questions", type=str, help="Path to JSON questions file (legacy)")
    p_run.add_argument("--max-iterations", type=int, default=10)
    p_run.add_argument("--model", type=str, default="opus")
    p_run.add_argument("--timeout", type=int, default=900, help="Per-iteration timeout in seconds (default: 900)")
    p_run.add_argument("--context-dir", type=Path, default=None)
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
