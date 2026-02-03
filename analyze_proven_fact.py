"""
Analysis and Visualization for Proven Fact-Based Algorithm Results
Generates tables and plots for examining data quality and system performance

LICENSE:
BY-NC (Personal use allowed. Commercial use prohibited. Attribution required.)
Copyright (c) 2026 [Cheongwon Choi]

Version: 1.4.0-ABSOLUTE-FINAL
Date: 2026-02-03

Changes from v1.1.0:
  BUG-C : generate_referee_analysis() – v1.1.0 실제 주기로 수정 (5n/5n-3, 7n/7n-3/7n-5)
  NEW   : redundancy 분석 섹션 추가
  NEW   : confirmed_logic 통계 표시
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import argparse

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False

try:
    import matplotlib
    matplotlib.use('Agg')          # headless safe
    import matplotlib.pyplot as plt
    import seaborn as sns          # noqa: F401
    _MATPLOTLIB = True
except ImportError:
    _MATPLOTLIB = False


# ---------------------------------------------------------------------------
# Core Analyzer
# ---------------------------------------------------------------------------
class ProvenFactAnalyzer:
    """Analyze and visualize proven fact simulation results."""

    def __init__(self, results_file: str):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  ❌ Failed to parse JSON in '{results_file}': {e}")
            print(f"      The file may be corrupted or incomplete.")
            raise SystemExit(1)
        except FileNotFoundError:
            print(f"  ❌ Results file not found: {results_file}")
            raise SystemExit(1)

        self.metadata = self.data.get('metadata', {})
        self.all_records = self.data.get('all_records', [])
        self.hallucinations = self.data.get('hallucinations', [])
        self.hallucination_summary = self.data.get('hallucination_summary', {})
        self.final_audit = self.data.get('final_audit', {})
        self.confirmed_logic = self.data.get('confirmed_logic', [])

    # ------------------------------------------------------------------
    def generate_session_table(self) -> List[Dict]:
        """Generate session-by-session performance data."""
        # 세션별로 기록 그룹화
        sessions: Dict[int, list] = {}
        for record in self.all_records:
            sessions.setdefault(record['session'], []).append(record)

        # 세션별 hallucination 카운트 (session 필드 기반)
        hall_per_session: Dict[int, int] = {}
        for h in self.hallucinations:
            s = h.get('session', -1)
            hall_per_session[s] = hall_per_session.get(s, 0) + 1

        table = []
        for sn in sorted(sessions.keys()):
            records = sessions[sn]
            total_tokens = sum(r.get('estimated_tokens', 0) for r in records)
            hall_count = hall_per_session.get(sn, 0)

            # redundancy 체크
            redundant = sum(1 for r in records
                            if r.get('redundancy_assessment', {}).get('status') == 'redundant')

            table.append({
                'Session': sn,
                'Exchanges': len(records),
                'Est. Tokens': total_tokens,
                'Hallucinations': hall_count,
                'Redundant': redundant,
                'Status': '✓ Clean' if hall_count == 0 else f'⚠ {hall_count} issues'
            })
        return table

    # ------------------------------------------------------------------
    def generate_summary_statistics(self) -> Dict:
        total_sessions = self.metadata.get('total_sessions', 0)
        total_exchanges = len(self.all_records)

        # redundancy 통계
        redundant_count = sum(
            1 for r in self.all_records
            if r.get('redundancy_assessment', {}).get('status') == 'redundant'
        )
        redundancy_rate = redundant_count / max(1, total_exchanges)

        return {
            'Topic': self.metadata.get('topic', 'N/A'),
            'Version': self.metadata.get('version', 'N/A'),
            'Total Sessions': total_sessions,
            'Total Exchanges': total_exchanges,
            'Number of Referees': self.metadata.get('num_referees', 2),
            'Total Hallucinations': self.hallucination_summary.get('total', 0),
            'Hallucination Rate': f"{self.hallucination_summary.get('rate', 0):.2%}",
            'Critical Issues': self.hallucination_summary.get('by_severity', {}).get('critical', 0),
            'High Issues': self.hallucination_summary.get('by_severity', {}).get('high', 0),
            'Medium Issues': self.hallucination_summary.get('by_severity', {}).get('medium', 0),
            'Low Issues': self.hallucination_summary.get('by_severity', {}).get('low', 0),
            'Confirmed Logic Nodes': len(self.confirmed_logic),
            'Redundant Exchanges': f"{redundant_count} ({redundancy_rate:.1%})",
            'API Provider': self.metadata.get('api_provider', 'N/A'),
            'Timestamp': self.metadata.get('timestamp', 'N/A'),
        }

    # ------------------------------------------------------------------
    def analyze_hallucinations_by_severity(self) -> List[Dict]:
        sev = self.hallucination_summary.get('by_severity', {})
        return [
            {'Severity': 'Critical', 'Count': sev.get('critical', 0)},
            {'Severity': 'High',     'Count': sev.get('high', 0)},
            {'Severity': 'Medium',   'Count': sev.get('medium', 0)},
            {'Severity': 'Low',      'Count': sev.get('low', 0)},
        ]

    # ------------------------------------------------------------------
    # BUG-C 수정 : v1.1.0 실제 주기 반영
    def generate_referee_analysis(self) -> Dict:
        num_referees = self.metadata.get('num_referees', 2)
        total_sessions = self.metadata.get('total_sessions', 0)

        if num_referees == 2:
            # 5n : 리셋 횟수 = total_sessions // 5
            # 5n-3 : 리셋 횟수 = (total_sessions + 3) // 5  (근사)
            reset_counts = [
                total_sessions // 5,
                (total_sessions + 3) // 5
            ]
            schedule_labels = ["5n (5,10,15…)", "5n-3 (2,7,12…)"]
        else:  # 3 referees
            reset_counts = [
                total_sessions // 7,
                (total_sessions + 3) // 7,
                (total_sessions + 5) // 7
            ]
            schedule_labels = ["7n (7,14,21…)", "7n-3 (4,11,18…)", "7n-5 (2,9,16…)"]

        # hallucination type별 분류
        type_counts: Dict[str, int] = {}
        for h in self.hallucinations:
            t = h.get('type', 'unknown')
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            'Number of Referees': num_referees,
            'Reset Schedules': schedule_labels,
            'Estimated Resets per Referee': reset_counts,
            'Total Hallucinations Detected': self.hallucination_summary.get('total', 0),
            'Hallucination Types': type_counts,
            'Confirmed Logic Nodes': len(self.confirmed_logic),
        }

    # ------------------------------------------------------------------
    # NEW : Redundancy 분석
    def analyze_redundancy(self) -> Dict:
        total = len(self.all_records)
        redundant = sum(
            1 for r in self.all_records
            if r.get('redundancy_assessment', {}).get('status') == 'redundant'
        )
        progressive = total - redundant
        # 토큰 절약 추정 (redundant 교환당 평균 2000 토큰)
        avg_tokens = 2000
        token_savings = redundant * avg_tokens
        # 비용 추정 ($0.00001 / token – 대략)
        cost_savings = token_savings * 0.00001

        return {
            'Total Exchanges': total,
            'Progressive (유효)': progressive,
            'Redundant (중복)': redundant,
            'Redundancy Rate': f"{redundant / max(1, total):.1%}",
            'Estimated Token Savings': token_savings,
            'Estimated Cost Savings': f"${cost_savings:.3f}",
        }

    # ------------------------------------------------------------------
    # Plots
    def plot_severity_distribution(self, output_file: str = None):
        if not _MATPLOTLIB:
            print("  ⚠️  matplotlib not installed – skipping plot.")
            return

        data = self.analyze_hallucinations_by_severity()
        labels = [d['Severity'] for d in data]
        counts = [d['Count'] for d in data]

        colors = {'Critical': '#d62728', 'High': '#ff7f0e',
                  'Medium': '#ffbb78', 'Low': '#aec7e8'}

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(labels, counts,
                      color=[colors[l] for l in labels], alpha=0.8)
        ax.set_xlabel('Severity Level', fontsize=12)
        ax.set_ylabel('Count', fontsize=12)
        ax.set_title('Hallucination Distribution by Severity', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                    str(count), ha='center', va='bottom', fontsize=10)

        plt.tight_layout()
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"  📊 Plot saved: {output_file}")
        else:
            plt.show()
        plt.close()

    # ------------------------------------------------------------------
    def plot_hallucinations_per_session(self, output_file: str = None):
        if not _MATPLOTLIB:
            print("  ⚠️  matplotlib not installed – skipping plot.")
            return

        total_sessions = self.metadata.get('total_sessions', 0)
        if total_sessions == 0:
            print("  ⚠️  total_sessions is 0 – skipping hallucinations-per-session plot.")
            return

        # session 필드로 직접 카운팅
        hall_per_session = [0] * (total_sessions + 1)
        for h in self.hallucinations:
            s = h.get('session', 0)
            if 1 <= s <= total_sessions:
                hall_per_session[s] += 1

        sessions = list(range(1, total_sessions + 1))
        counts = hall_per_session[1:]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(sessions, counts, color='coral', alpha=0.7)
        ax.set_xlabel('Session Number', fontsize=12)
        ax.set_ylabel('Hallucinations Detected', fontsize=12)
        ax.set_title('Hallucination Count per Session', fontsize=14, fontweight='bold')
        ax.set_xticks(sessions)
        ax.grid(axis='y', alpha=0.3)
        plt.tight_layout()

        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"  📊 Plot saved: {output_file}")
        else:
            plt.show()
        plt.close()

    # ------------------------------------------------------------------
    # LaTeX
    def generate_latex_table(self, rows: List[Dict], caption: str = "", label: str = "") -> str:
        if not rows:
            return ""
        columns = list(rows[0].keys())
        latex = "\\begin{table}[h]\n\\centering\n"
        if caption:
            latex += f"\\caption{{{caption}}}\n"
        if label:
            latex += f"\\label{{{label}}}\n"
        latex += "\\begin{tabular}{" + "l" * len(columns) + "}\n\\hline\n"
        latex += " & ".join(columns) + " \\\\\n\\hline\n"
        for row in rows:
            latex += " & ".join(str(row.get(c, '')) for c in columns) + " \\\\\n"
        latex += "\\hline\n\\end{tabular}\n\\end{table}\n"
        return latex

    # ------------------------------------------------------------------
    # Full Report
    def generate_full_report(self, output_dir: str = "."):
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        print("\n" + "=" * 70)
        print("  PROVEN FACT SIMULATION ANALYSIS REPORT  v1.4.0-ABSOLUTE-FINAL")
        print("=" * 70 + "\n")

        # ---- Summary ----
        print("SUMMARY STATISTICS")
        print("-" * 70)
        summary = self.generate_summary_statistics()
        for key, value in summary.items():
            print(f"  {key:.<44} {value}")

        # ---- Session table ----
        print("\n\nSESSION-BY-SESSION PERFORMANCE")
        print("-" * 70)
        session_table = self.generate_session_table()
        if _PANDAS:
            print(pd.DataFrame(session_table).to_string(index=False))
        else:
            # fallback: plain text
            if session_table:
                headers = list(session_table[0].keys())
                print("  " + "  ".join(f"{h:>14}" for h in headers))
                for row in session_table:
                    print("  " + "  ".join(f"{str(row[h]):>14}" for h in headers))

        # ---- Severity ----
        print("\n\nHALLUCINATION SEVERITY DISTRIBUTION")
        print("-" * 70)
        severity_data = self.analyze_hallucinations_by_severity()
        for item in severity_data:
            bar = "█" * item['Count']
            print(f"  {item['Severity']:10} {item['Count']:3}  {bar}")

        # ---- Referee analysis (BUG-C 수정) ----
        print("\n\nREFEREE SYSTEM ANALYSIS")
        print("-" * 70)
        ref_analysis = self.generate_referee_analysis()
        for key, value in ref_analysis.items():
            print(f"  {key:.<44} {value}")

        # ---- Redundancy (NEW) ----
        print("\n\nREDUNDANCY ANALYSIS")
        print("-" * 70)
        redundancy = self.analyze_redundancy()
        for key, value in redundancy.items():
            print(f"  {key:.<44} {value}")

        # ---- Confirmed Logic (NEW) ----
        print("\n\nCONFIRMED LOGIC NODES")
        print("-" * 70)
        if self.confirmed_logic:
            for i, node in enumerate(self.confirmed_logic, 1):
                print(f"  {i}. [Session {node.get('session', '?')}] "
                      f"{node.get('conclusion', 'N/A')[:80]}")
        else:
            print("  (none)")

        # ---- Plots ----
        print("\n\nGENERATING VISUALIZATIONS…")
        print("-" * 70)
        self.plot_severity_distribution(
            output_file=str(output_path / "severity_distribution.png")
        )
        self.plot_hallucinations_per_session(
            output_file=str(output_path / "hallucinations_per_session.png")
        )

        # ---- LaTeX ----
        print("\n\nLATEX TABLE GENERATION")
        print("-" * 70)
        latex_output = output_path / "tables.tex"
        with open(latex_output, 'w', encoding='utf-8') as f:
            f.write("% Session Performance Table\n")
            f.write(self.generate_latex_table(
                session_table,
                caption="Session-by-Session Performance",
                label="tab:sessions"
            ))
            f.write("\n\n% Severity Distribution Table\n")
            f.write(self.generate_latex_table(
                severity_data,
                caption="Hallucination Severity Distribution",
                label="tab:severity"
            ))
            f.write("\n\n% Redundancy Analysis Table\n")
            f.write(self.generate_latex_table(
                [redundancy],
                caption="Redundancy Analysis",
                label="tab:redundancy"
            ))
        print(f"  📄 LaTeX tables saved: {latex_output}")

        # ---- JSON summary ----
        summary_file = output_path / "analysis_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary_statistics': summary,
                'referee_analysis': ref_analysis,
                'redundancy_analysis': redundancy,
                'session_table': session_table,
                'severity_distribution': severity_data,
                'confirmed_logic_count': len(self.confirmed_logic),
            }, f, indent=2, ensure_ascii=False)
        print(f"  📄 Summary JSON saved: {summary_file}")

        print("\n" + "=" * 70)
        print("  ✅ ANALYSIS COMPLETE")
        print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Analyze Proven Fact-Based Algorithm Results v1.4.0-ABSOLUTE-FINAL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_proven_fact.py results.json
  python analyze_proven_fact.py results.json --output analysis_output
  python analyze_proven_fact.py results.json --summary-only
        """
    )
    parser.add_argument('results_file', type=str,
                        help='Path to simulation results JSON file')
    parser.add_argument('--output', type=str, default='.',
                        help='Output directory (default: current directory)')
    parser.add_argument('--summary-only', action='store_true',
                        help='Print summary only – no files generated')

    args = parser.parse_args()

    if not Path(args.results_file).exists():
        print(f"  ❌ File not found: {args.results_file}")
        return 1

    try:
        analyzer = ProvenFactAnalyzer(args.results_file)

        if args.summary_only:
            print("\n" + "=" * 70)
            print("  SUMMARY STATISTICS")
            print("=" * 70 + "\n")
            for key, value in analyzer.generate_summary_statistics().items():
                print(f"  {key:.<44} {value}")
            print()
        else:
            analyzer.generate_full_report(output_dir=args.output)

        return 0

    except Exception as e:
        print(f"\n  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
