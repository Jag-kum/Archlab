import argparse
import json
import sys

from archlab.cli.config import build_engine, load_config
from archlab.cli.sweep import format_sweep_table, run_sweep


def _print_summary(summary):
    print(f"\n{'='*50}")
    print("  ArchLab Simulation Results")
    print(f"{'='*50}")
    for key, value in summary.items():
        if key == "sla":
            print("  sla:")
            for check_name, check in value.items():
                if isinstance(check, dict):
                    status = "PASS" if check["passed"] else "FAIL"
                    print(f"    [{status}] {check_name}: {check['actual']:.4f} (limit: {check['threshold']})")
                else:
                    print(f"    all_passed: {check}")
        elif isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        elif isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="archlab",
        description="ArchLab - Distributed Systems Simulator",
    )
    subparsers = parser.add_subparsers(dest="command")

    sim_parser = subparsers.add_parser("simulate", help="Run a simulation from a YAML config")
    sim_parser.add_argument("config", help="Path to YAML configuration file")
    sim_parser.add_argument("--json", action="store_true", help="Output results as JSON")

    sweep_parser = subparsers.add_parser("sweep", help="Run a parameter sweep")
    sweep_parser.add_argument("config", help="Path to YAML configuration file")
    sweep_parser.add_argument("--param", required=True, help="Parameter to sweep (e.g. db.workers)")
    sweep_parser.add_argument("--values", required=True, help="Comma-separated values to try")
    sweep_parser.add_argument("--seeds", help="Comma-separated seeds for multi-run averaging")
    sweep_parser.add_argument("--json", action="store_true", help="Output results as JSON")

    serve_parser = subparsers.add_parser("serve", help="Start the web UI")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn
        print(f"\n  ArchLab Web UI starting at http://{args.host}:{args.port}\n")
        uvicorn.run("archlab.api.app:app", host=args.host, port=args.port, reload=False)

    elif args.command == "simulate":
        config = load_config(args.config)
        engine = build_engine(config)
        engine.run()
        summary = engine.metrics.summary()

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            _print_summary(summary)

    elif args.command == "sweep":
        config = load_config(args.config)

        raw_values = args.values.split(",")
        values = []
        for v in raw_values:
            v = v.strip()
            try:
                values.append(int(v))
            except ValueError:
                try:
                    values.append(float(v))
                except ValueError:
                    values.append(v)

        seeds = None
        if args.seeds:
            seeds = [int(s.strip()) for s in args.seeds.split(",")]

        results = run_sweep(config, args.param, values, seeds=seeds)

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(format_sweep_table(results, args.param))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
