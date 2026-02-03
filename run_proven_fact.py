#!/usr/bin/env python3
"""
Command-line interface for the Proven Fact-Based Algorithm
Supports both interactive mode and command-line arguments

LICENSE:
BY-NC (Personal use allowed. Commercial use prohibited. Attribution required.)
Copyright (c) 2026 [Cheongwon Choi]

Version: 1.4.0-ABSOLUTE-FINAL
Date: 2026-02-03

Changes from v1.1.0:
  BUG-A : 심판 주기 설명 텍스트를 v1.1.0 실제 주기(5n/5n-3, 7n/7n-3/7n-5)로 수정
  SUGGEST-04 : tiktoken 설치 안내 추가
"""

import argparse
from datetime import datetime
import sys
import os
import json
from proven_fact_system import ProvenFactSystem


# ---------------------------------------------------------------------------
# Predefined simulation templates with fixed constants
# ---------------------------------------------------------------------------
SIMULATION_TEMPLATES = {
    "earth_rotation": {
        "proven_fact": "The Earth rotates on its axis once every 24 hours, causing day and night cycles.",
        "topic": "Earth's Rotation and the Day-Night Cycle",
        "fixed_constants": {
            "Earth_rotation_period_hours": 24,
            "Earth_circumference_km": 40075,
            "Earth_diameter_km": 12742,
            "degrees_per_hour": 15,
            "rotation_speed_at_equator_km_per_hour": 1670
        },
        "evidence_stages": [
            [
                "The Sun appears to rise in the east and set in the west daily",
                "Stars appear to move across the night sky in circular patterns",
                "Shadows change length and direction throughout the day"
            ],
            [
                "Ancient Greek astronomers measured stellar positions",
                "Sundials have been used for thousands of years to track time",
                "Different locations experience noon at different times"
            ],
            [
                "Foucault pendulum demonstrates Earth's rotation (1851)",
                "Satellites in geostationary orbit remain fixed above one point",
                "Coriolis effect influences weather patterns and ocean currents",
                "High-precision atomic clocks confirm 24-hour rotation period"
            ],
            [
                "Photos from space show Earth rotating",
                "GPS satellites account for Earth's rotation in positioning calculations",
                "International Space Station completes orbit while Earth rotates beneath"
            ]
        ]
    },
    "earth_sphericity": {
        "proven_fact": "The Earth is a sphere (oblate spheroid) with a circumference of approximately 40,075 km at the equator.",
        "topic": "The Spherical Shape of Earth",
        "fixed_constants": {
            "Earth_circumference_km": 40075,
            "Earth_diameter_km": 12742,
            "Greek_stadium_meters": 185,
            "Chinese_li_meters": 500,
            "Korean_li_meters": 400,
            "km_to_miles": 0.621371
        },
        "evidence_stages": [
            [
                "Ships disappear over the horizon hull-first, mast-last",
                "The shadow of Earth on the Moon during lunar eclipses is always circular",
                "Different stars are visible from different latitudes"
            ],
            [
                "Eratosthenes measured Earth's circumference (~250 BCE) using shadows at different locations",
                "Travelers going south see southern stars rise higher in the sky",
                "Altitude of Polaris changes with latitude"
            ],
            [
                "Ferdinand Magellan's crew completed first circumnavigation (1519-1522)",
                "Time zones exist because different longitudes face the sun at different times",
                "Gravity measurements show consistent spherical distribution"
            ],
            [
                "Satellite photos from space show Earth as a sphere",
                "GPS system requires spherical Earth model for accurate positioning",
                "Astronauts have directly observed Earth's curvature from space"
            ]
        ]
    },
    "vaccines": {
        "proven_fact": "Vaccines have saved millions of lives by training the immune system to recognize and fight specific pathogens.",
        "topic": "How Vaccines Work and Their Historical Impact",
        "fixed_constants": {
            "smallpox_deaths_20th_century": 300000000,
            "polio_reduction_percentage": 99,
            "measles_prevaccine_cases_per_year": 3500000,
            "vaccine_efficacy_percentage": 95
        },
        "evidence_stages": [
            [
                "Edward Jenner's cowpox experiment (1796) protected against smallpox",
                "Smallpox killed 300 million people in the 20th century alone",
                "Observable: Vaccinated individuals showed resistance to disease outbreaks"
            ],
            [
                "Louis Pasteur developed rabies vaccine (1885) based on weakened virus principle",
                "Polio incidence dropped 99% after vaccine introduction (1955)",
                "Measles cases decreased from 3-4 million/year to near elimination in vaccinated populations"
            ],
            [
                "Clinical trials demonstrate 90-95% efficacy for most modern vaccines",
                "Herd immunity threshold calculations match epidemiological models",
                "Antibody titers measurably increase post-vaccination",
                "Historical data: Diseases eliminated in regions with high vaccination rates"
            ],
            [
                "mRNA vaccine technology (COVID-19) demonstrated rapid development capability",
                "Genetic sequencing confirms vaccine-induced antibodies match target pathogens",
                "Global vaccination campaigns eradicated smallpox (1980) and nearly eliminated polio",
                "Real-time surveillance data shows correlation between vaccination rates and disease reduction"
            ]
        ]
    },
    "evolution": {
        "proven_fact": "Species evolve through natural selection acting on genetic variation over time.",
        "topic": "The Theory of Evolution by Natural Selection",
        "fixed_constants": {
            "Earth_age_billions_years": 4.54,
            "first_life_billions_years_ago": 3.5,
            "human_chimp_common_ancestor_millions_years": 6,
            "DNA_similarity_human_chimp_percentage": 98.8
        },
        "evidence_stages": [
            [
                "Fossil record shows progression from simple to complex life forms",
                "Anatomical similarities across different species (homologous structures)",
                "Selective breeding demonstrates heritable trait modification"
            ],
            [
                "Darwin's finches show beak adaptation to different food sources",
                "Geographic distribution of species matches continental drift patterns",
                "Vestigial structures (whale hip bones, human appendix) indicate ancestry"
            ],
            [
                "Radiometric dating confirms fossil ages and evolutionary timeline",
                "Observed speciation events in laboratory and nature",
                "Antibiotic resistance demonstrates evolution in real-time"
            ],
            [
                "DNA sequencing reveals precise genetic relationships between species",
                "Human and chimpanzee DNA is 98.8% identical",
                "Molecular clock analysis confirms evolutionary timeline",
                "Direct observation of genetic mutations and selection pressures"
            ]
        ]
    }
}


# ---------------------------------------------------------------------------
# Interactive Mode
# ---------------------------------------------------------------------------
def interactive_mode():
    """
    Interactive mode with sequential question process:
    Step 1  : Choose proven fact (topic)
    Step 2  : Enter number of discussion sessions
    Step 2.5: Choose number of referees (2 or 3)
    Step 3  : Choose display mode
    """
    print("\n" + "=" * 70)
    print("  PROVEN FACT-BASED ALGORITHM v1.4.0 – Interactive Setup")
    print("=" * 70 + "\n")

    # ---- tiktoken 안내 (SUGGEST-04) ----
    try:
        import tiktoken  # noqa: F401
        print("✅ tiktoken installed – accurate token counting enabled.\n")
    except ImportError:
        print("⚠️  tiktoken not installed. Token estimates will use fallback (÷4).")
        print("    Run: pip install tiktoken   for accurate token counting.\n")

    # ============================================================
    # STEP 1 : 주제 선택
    # ============================================================
    print("=" * 70)
    print("STEP 1: Choose the proven fact to demonstrate")
    print("=" * 70)
    print("\nAvailable topics (proven facts):")
    for i, (key, template) in enumerate(SIMULATION_TEMPLATES.items(), 1):
        print(f"\n  {i}. {template['topic']}")
        print(f"     Fact: {template['proven_fact'][:80]}…")

    print(f"\n  {len(SIMULATION_TEMPLATES) + 1}. Custom (provide your own JSON config file)")

    while True:
        choice = input(f"\nEnter your choice (1-{len(SIMULATION_TEMPLATES)+1}): ").strip()
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(SIMULATION_TEMPLATES):
                template_name = list(SIMULATION_TEMPLATES.keys())[choice_num - 1]
                config = SIMULATION_TEMPLATES[template_name]
                output_default = f"{template_name}_results.json"
                print(f"\n✓ Selected: {template_name}")
                print(f"  Topic: {config['topic']}")
                break
            elif choice_num == len(SIMULATION_TEMPLATES) + 1:
                config_path = input("  Enter path to your JSON config file: ").strip()
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    output_default = config_path.replace('.json', '_results.json')
                    print(f"✓ Loaded custom config from {config_path}")
                    break
                except Exception as e:
                    print(f"✗ Error loading config: {e}")
            else:
                print("  Invalid choice. Please try again.")
        except ValueError:
            print("  Please enter a number.")

    # ============================================================
    # STEP 2 : 세션 수
    # ============================================================
    print("\n" + "=" * 70)
    print("STEP 2: Number of discussion sessions")
    print("=" * 70)
    print("\n  Each session involves:")
    print("    • Student challenges with skeptical questions (min 4)")
    print("    • 4 professors respond with evidence")
    print("    • 2-3 referees verify for hallucinations")
    print("\n  Recommended: 12 sessions (divides evenly into 4 evidence stages)")
    print("  Minimum: 8 | Maximum: 50")

    while True:
        sessions_input = input("\n  Enter number of sessions (default: 12): ").strip()
        if not sessions_input:
            total_sessions = 12
            break
        try:
            total_sessions = int(sessions_input)
            if 8 <= total_sessions <= 50:
                break
            else:
                print("  Please enter a number between 8 and 50.")
        except ValueError:
            print("  Please enter a valid number.")

    num_stages = len(config.get('evidence_stages', []))
    sessions_per_stage = total_sessions // num_stages
    remainder = total_sessions % num_stages

    print(f"\n✓ {total_sessions} sessions → {num_stages} evidence stages:")
    current = 0
    for i in range(num_stages):
        stage_size = sessions_per_stage + (1 if i < remainder else 0)
        print(f"     Stage {i+1}: Sessions {current+1}–{current+stage_size} ({stage_size} sessions)")
        current += stage_size

    # ============================================================
    # STEP 2.5 : 심판 수 (BUG-A 수정 – 올바른 주기 표시)
    # ============================================================
    print("\n" + "=" * 70)
    print("STEP 2.5: Number of referees (2 or 3)")
    print("=" * 70)
    print("\n  Referees verify factual accuracy and detect hallucinations.")
    print("  • 2 referees: Reset schedule 5n / 5n-3  (sessions 5,10,15… / 2,7,12…)")
    print("  • 3 referees: Reset schedule 7n / 7n-3 / 7n-5  (7,14… / 4,11… / 2,9…)")
    print("  • Zero simultaneous resets guaranteed.")
    print("\n  Recommended: 2 referees for most cases")

    while True:
        ref_input = input("\n  Enter number of referees (2 or 3, default: 2): ").strip()
        if not ref_input:
            num_referees = 2
            break
        try:
            num_referees = int(ref_input)
            if num_referees in [2, 3]:
                break
            else:
                print("  Please enter 2 or 3.")
        except ValueError:
            print("  Please enter a valid number.")

    print(f"\n✓ Using {num_referees} referees with non-overlapping reset schedules")

    # ============================================================
    # STEP 3 : 표시 모드
    # ============================================================
    print("\n" + "=" * 70)
    print("STEP 3: Choose display mode")
    print("=" * 70)
    print("\n  1. Full display  – Show all questions, responses, and verifications")
    print("  2. Briefing only – Show session summaries and final results only")
    print("\n  Recommended: Briefing only (cleaner output)")

    while True:
        mode_choice = input("\n  Enter display mode (1 or 2, default: 2): ").strip()
        if not mode_choice:
            verbose = False
            break
        try:
            mode_num = int(mode_choice)
            if mode_num == 1:
                verbose = True
                break
            elif mode_num == 2:
                verbose = False
                break
            else:
                print("  Please enter 1 or 2.")
        except ValueError:
            print("  Please enter a valid number.")

    print(f"\n✓ Display mode: {'Full' if verbose else 'Briefing only'}")

    # ============================================================
    # API 선택
    # ============================================================
    print("\n" + "=" * 70)
    print("API Provider Selection")
    print("=" * 70)
    print("\n  1. Anthropic (Claude) – Recommended")
    print("  2. OpenAI (GPT-4)")

    while True:
        api_choice = input("\n  Choose API provider (1 or 2, default: 1): ").strip()
        if not api_choice:
            api_provider = "anthropic"
            break
        try:
            api_num = int(api_choice)
            if api_num == 1:
                api_provider = "anthropic"
                break
            elif api_num == 2:
                api_provider = "openai"
                break
            else:
                print("  Please enter 1 or 2.")
        except ValueError:
            print("  Please enter a valid number.")

    # Output file
    output_file = input(f"\n  Output filename (default: {output_default}): ").strip()
    if not output_file:
        output_file = output_default

    # ============================================================
    # 확인 및 실행
    # ============================================================
    print("\n" + "=" * 70)
    print("  CONFIGURATION SUMMARY")
    print("=" * 70)
    print(f"  Topic      : {config['topic']}")
    print(f"  Sessions   : {total_sessions} (across {num_stages} evidence stages)")
    print(f"  Referees   : {num_referees}")
    print(f"  Display    : {'Full' if verbose else 'Briefing only'}")
    print(f"  API        : {api_provider.title()}")
    print(f"  Output     : {output_file}")
    print("=" * 70)

    confirm = input("\n  Proceed with simulation? (y/n): ").strip().lower()
    if confirm != 'y':
        print("  Simulation cancelled.")
        return

    print("\n" + "=" * 70)
    print("  INITIALIZING SIMULATION…")
    print("=" * 70 + "\n")

    # 출력 디렉토리 자동 생성
    # GROK-M1: output_file=None 완벽 처리
    if output_file is None:
        from datetime import datetime
        output_file = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        print(f"  📝 Auto-generated output file: {output_file}")
    
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"  📁 Created directory: {output_dir}")

    try:
        system = ProvenFactSystem(
            api_provider=api_provider,
            num_referees=num_referees
        )
        results = system.run_learning_simulation(
            proven_fact=config['proven_fact'],
            topic=config['topic'],
            evidence_stages=config['evidence_stages'],
            fixed_constants=config.get('fixed_constants', {}),
            total_sessions=total_sessions,
            output_file=output_file,
            verbose=verbose
        )

        print("\n" + "=" * 70)
        print("  ✅ SIMULATION COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"\n  Results       : {output_file}")
        print(f"  SFT data      : {output_file.replace('.json', '.jsonl')}")
        print(f"  Hallucinations: {results['hallucination_summary']['total']} "
              f"(rate {results['hallucination_summary']['rate']:.2%})")
        print(f"  Training examples: {len(results['sft_data'])}")

    except Exception as e:
        print(f"\n  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Command-line Mode
# ---------------------------------------------------------------------------
def command_line_mode(args):
    # ── 1. 설정 소스 결정 ──────────────────────────────────────────────
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"  ❌ Config file not found: {args.config}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"  ❌ Invalid JSON in config file: {e}")
            sys.exit(1)
        output_file = args.output or args.config.replace('.json', '_results.json')

    elif args.template:
        if args.template not in SIMULATION_TEMPLATES:
            print(f"  Error: Unknown template '{args.template}'")
            print(f"  Available: {', '.join(SIMULATION_TEMPLATES.keys())}")
            sys.exit(1)
        config = SIMULATION_TEMPLATES[args.template]
        output_file = args.output or f"{args.template}_results.json"

    else:
        print("  Error: Must specify either --config or --template")
        print("  Use --help for usage information.")
        sys.exit(1)

    # ── 2. 출력 디렉토리 자동 생성 ─────────────────────────────────────
    # GROK-M1: output_file=None 완벽 처리
    if output_file is None:
        from datetime import datetime
        output_file = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        print(f"  📝 Auto-generated output file: {output_file}")
    
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"  📁 Created directory: {output_dir}")

    # ── 3. 시뮬레이션 실행 ─────────────────────────────────────────────
    system = ProvenFactSystem(
        api_provider=args.api,
        num_referees=args.referees
    )
    results = system.run_learning_simulation(
        proven_fact=config['proven_fact'],
        topic=config['topic'],
        evidence_stages=config['evidence_stages'],
        fixed_constants=config.get('fixed_constants', {}),
        total_sessions=args.sessions,
        output_file=output_file,
        verbose=args.verbose
    )
    print(f"\n✅ Results saved to {output_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Proven Fact-Based Algorithm v1.4.0-ABSOLUTE-FINAL – Generate high-quality reasoning data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended for first-time users)
  python run_proven_fact.py

  # Command-line with template
  python run_proven_fact.py --template earth_sphericity --sessions 12 --referees 2

  # Custom config file
  python run_proven_fact.py --config my_topic.json --sessions 15 --referees 3 --verbose
        """
    )
    parser.add_argument('--config', type=str,
                        help='Path to custom JSON config file')
    parser.add_argument('--template', type=str,
                        choices=list(SIMULATION_TEMPLATES.keys()),
                        help='Use predefined template')
    parser.add_argument('--sessions', type=int, default=12,
                        help='Number of discussion sessions (default: 12)')
    parser.add_argument('--referees', type=int, choices=[2, 3], default=2,
                        help='Number of referees (2 or 3, default: 2)')
    parser.add_argument('--api', type=str,
                        choices=['anthropic', 'openai'], default='anthropic',
                        help='API provider (default: anthropic)')
    parser.add_argument('--output', type=str,
                        help='Output filename (default: auto-generated)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show full output (default: briefing only)')

    args = parser.parse_args()

    if len(sys.argv) == 1:
        interactive_mode()
    else:
        command_line_mode(args)


if __name__ == "__main__":
    main()
