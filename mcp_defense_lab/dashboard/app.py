"""Streamlit research dashboard for MCP Defense Lab.

Reads results directly from SQLite. Visualizes attack success rates, benign task
completion, false positives, latency breakdowns, defense comparisons, adaptive
fuzzing degradation, and granular per-case telemetry.
"""

from __future__ import annotations

import json
from typing import Any
import pandas as pd
import streamlit as st

from mcp_defense_lab.core.llm_provider import ScriptedBehaviorMode, ScriptedFakeModelProvider
from mcp_defense_lab.db.repository import repo
from mcp_defense_lab.defenses import DEFENSE_REGISTRY, get_defense
from mcp_defense_lab.evaluation.benchmark import BenchmarkRunner
from mcp_defense_lab.evaluation.datasets import generate_synthetic_benchmark

st.set_page_config(
    page_title="MCP Defense Lab — Research Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom header styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .kpi-badge-synthetic {
        background-color: #EFF6FF;
        color: #1D4ED8;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .kpi-badge-real {
        background-color: #ECFDF5;
        color: #047857;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">🛡️ MCP Defense Lab</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Measuring Model Context Protocol (MCP) Defenses with a Real Agent in the Loop</div>',
    unsafe_allow_html=True,
)

# Sidebar: Experiment Selection & Quick Actions
st.sidebar.title("Navigation & Control")

experiments = repo.list_experiments()
experiment_ids = [e["id"] for e in experiments]

selected_exp_id = None
if experiment_ids:
    selected_exp_id = st.sidebar.selectbox(
        "Select Experiment Run:",
        options=experiment_ids,
        format_func=lambda x: f"{x} — {next(e['title'] for e in experiments if e['id'] == x)}",
    )
else:
    st.sidebar.warning("No experiments found in database.")

st.sidebar.markdown("---")
st.sidebar.subheader("🚀 Quick Benchmark Runner")
runner_defense = st.sidebar.selectbox("Defense:", options=list(DEFENSE_REGISTRY.keys()), index=4)
runner_cases_count = st.sidebar.slider("Sample Size:", min_value=10, max_value=40, value=40, step=10)

if st.sidebar.button("Run Benchmark Suite Now"):
    with st.spinner(f"Running benchmark for '{runner_defense}'..."):
        defense_instance = get_defense(runner_defense)
        provider = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.NAIVE_COMPLIANT)
        cases = generate_synthetic_benchmark()[:runner_cases_count]

        import uuid
        new_exp_id = f"exp_{uuid.uuid4().hex[:8]}"
        runner = BenchmarkRunner(provider=provider, defense=defense_instance)
        telemetry, report = runner.run_suite(cases, experiment_id=new_exp_id)

        repo.save_experiment(
            experiment_id=new_exp_id,
            title=f"Manual Run: {runner_defense}",
            defense_name=runner_defense,
            model_provider=provider.model_type,
            model_name=provider.model_name,
            config={"sample_count": runner_cases_count, "defense": runner_defense},
            telemetry_records=telemetry,
            report=report,
        )
        st.sidebar.success(f"Experiment {new_exp_id} completed!")
        st.rerun()

# Main Dashboard Tabs
tabs = st.tabs([
    "📊 Executive Summary",
    "🛡️ Defense Comparison",
    "⏱️ Latency Analysis",
    "🌪️ Adaptive Fuzzing",
    "🔍 Granular Case Inspector",
    "💾 Data Export",
])

# ==============================================================================
# TAB 1: EXECUTIVE SUMMARY
# ==============================================================================
with tabs[0]:
    if not selected_exp_id:
        st.info("Please run an experiment using the sidebar or CLI to populate benchmark data.")
    else:
        exp_data = repo.get_experiment_details(selected_exp_id)
        if exp_data and exp_data.get("report"):
            rep = exp_data["report"]
            cfg = exp_data.get("config", {})

            # Provenance badge
            mtype = exp_data.get("model_provider", "synthetic_offline")
            if mtype == "ollama_local":
                st.markdown('<span class="kpi-badge-real">⚡ MODEL: OLLAMA LOCAL INFERENCE</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="kpi-badge-synthetic">🔬 EVALUATION: SYNTHETIC FIXTURE (DETERMINISTIC OFFLINE)</span>', unsafe_allow_html=True)

            st.markdown(f"### {exp_data['title']}")
            st.caption(f"Experiment ID: `{selected_exp_id}` | Defense: **{exp_data['defense_name']}** | Model: **{exp_data['model_name']}** | Cases: **{exp_data['total_cases']}**")

            # KPI Metric Columns
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                asr = rep["attack_success_rate"]
                st.metric(
                    label="Attack Success Rate (ASR)",
                    value=f"{asr['point_estimate']:.1%}",
                    help=f"Fraction of valid attacks succeeded. 95% Wilson CI: [{asr['ci_lower']:.1%} – {asr['ci_upper']:.1%}] (n={asr['sample_size']})",
                )
                st.caption(f"CI: [{asr['ci_lower']:.1%} – {asr['ci_upper']:.1%}]")

            with c2:
                tcr = rep["benign_completion_rate"]
                st.metric(
                    label="Benign Completion (TCR)",
                    value=f"{tcr['point_estimate']:.1%}",
                    help=f"Fraction of benign tasks completed without false block. 95% CI: [{tcr['ci_lower']:.1%} – {tcr['ci_upper']:.1%}]",
                )
                st.caption(f"CI: [{tcr['ci_lower']:.1%} – {tcr['ci_upper']:.1%}]")

            with c3:
                fpr = rep["false_positive_rate"]
                st.metric(
                    label="False Positive Rate (FPR)",
                    value=f"{fpr['point_estimate']:.1%}",
                    help=f"Fraction of benign tasks erroneously blocked by defense. 95% CI: [{fpr['ci_lower']:.1%} – {fpr['ci_upper']:.1%}]",
                )
                st.caption(f"CI: [{fpr['ci_lower']:.1%} – {fpr['ci_upper']:.1%}]")

            with c4:
                dbr = rep["defense_block_rate"]
                st.metric(
                    label="Defense Block Rate",
                    value=f"{dbr['point_estimate']:.1%}",
                    help=f"Total fraction of all proposals blocked by defense.",
                )
                st.caption(f"{dbr['numerator']}/{dbr['sample_size']} blocked")

            with c5:
                st.metric(
                    label="Median Total Latency",
                    value=f"{rep['median_total_latency_ms']:.1f} ms",
                    help=f"P95 Total Latency: {rep['p95_total_latency_ms']:.1f} ms",
                )
                st.caption(f"P95: {rep['p95_total_latency_ms']:.1f} ms")

            st.markdown("---")

            # Risk Category Breakdown
            st.subheader("Vulnerability Breakdown by Risk Category")
            risk_breakdown = rep.get("risk_breakdown", {})
            if risk_breakdown:
                risk_rows = []
                for cat, val in risk_breakdown.items():
                    risk_rows.append({
                        "Security Risk Category": cat,
                        "Sample Size": val["sample_size"],
                        "Attacks Succeeded": val["attacks_succeeded"],
                        "Attack Success Rate": f"{val['asr']:.1%}",
                        "95% CI Lower": f"{val['ci_lower']:.1%}",
                        "95% CI Upper": f"{val['ci_upper']:.1%}",
                    })
                st.dataframe(pd.DataFrame(risk_rows), use_container_width=True)

# ==============================================================================
# TAB 2: DEFENSE COMPARISON MATRIX
# ==============================================================================
with tabs[1]:
    st.subheader("Comparative Defense Performance Matrix")
    if not experiments:
        st.info("Run benchmarks on multiple defenses to populate the comparison table.")
    else:
        comp_data = []
        for e in experiments:
            comp_data.append({
                "Experiment ID": e["id"],
                "Defense": e["defense_name"],
                "Model Provider": e["model_provider"],
                "Total Cases": e["total_cases"],
                "ASR": f"{e['asr']:.1%}" if e['asr'] is not None else "N/A",
                "TCR (Benign)": f"{e['tcr']:.1%}" if e['tcr'] is not None else "N/A",
                "FPR": f"{e['fpr']:.1%}" if e['fpr'] is not None else "N/A",
                "Defense Block Rate": f"{e['dbr']:.1%}" if e['dbr'] is not None else "N/A",
                "Median Latency (ms)": f"{e['median_latency_ms']:.1f}" if e['median_latency_ms'] is not None else "N/A",
                "P95 Latency (ms)": f"{e['p95_latency_ms']:.1f}" if e['p95_latency_ms'] is not None else "N/A",
            })
        df_comp = pd.DataFrame(comp_data)
        st.dataframe(df_comp, use_container_width=True)

        # Comparative Bar Chart
        if len(experiments) > 1:
            st.subheader("Attack Success vs. Benign Task Completion Trade-off")
            plot_df = pd.DataFrame([
                {
                    "Defense": e["defense_name"],
                    "Attack Success Rate (%)": (e["asr"] or 0.0) * 100,
                    "Benign Completion Rate (%)": (e["tcr"] or 0.0) * 100,
                }
                for e in experiments
            ]).set_index("Defense")
            st.bar_chart(plot_df)

# ==============================================================================
# TAB 3: LATENCY ANALYSIS
# ==============================================================================
with tabs[2]:
    st.subheader("Latency Overhead Breakdown")
    if selected_exp_id and exp_data and exp_data.get("report"):
        rep = exp_data["report"]
        lat_c1, lat_c2, lat_c3 = st.columns(3)
        with lat_c1:
            st.metric("Model Inference Median", f"{rep['median_model_latency_ms']:.1f} ms")
            st.caption(f"Model P95: {rep['p95_model_latency_ms']:.1f} ms")
        with lat_c2:
            st.metric("Defense Inspection Median", f"{rep['median_defense_latency_ms']:.1f} ms")
            st.caption(f"Defense P95: {rep['p95_defense_latency_ms']:.1f} ms")
        with lat_c3:
            st.metric("Total End-to-End Median", f"{rep['median_total_latency_ms']:.1f} ms")
            st.caption(f"Total P95: {rep['p95_total_latency_ms']:.1f} ms")

        st.markdown("---")
        cases_df = pd.DataFrame(exp_data.get("cases", []))
        if not cases_df.empty and "proposal_latency_ms" in cases_df.columns:
            st.subheader("Per-Case Latency Comparison (Model Proposal vs. Defense Decision)")
            sub_lat = cases_df[["case_id", "proposal_latency_ms", "defense_latency_ms"]].rename(
                columns={"proposal_latency_ms": "Model Proposal (ms)", "defense_latency_ms": "Defense Check (ms)"}
            ).set_index("case_id")
            st.bar_chart(sub_lat)

# ==============================================================================
# TAB 4: ADAPTIVE FUZZING & EVASION RESILIENCE
# ==============================================================================
with tabs[3]:
    st.subheader("Adaptive Fuzzing Evasion Analysis")
    fuzz_runs = repo.list_fuzz_runs()

    # Form to trigger a new fuzz run
    with st.expander("🌪️ Run New Adaptive Fuzzing Evaluation", expanded=False):
        with st.form("fuzz_form"):
            fuzz_defense = st.selectbox("Defense to Fuzz:", options=list(DEFENSE_REGISTRY.keys()))
            fuzz_mutations = st.slider("Max Mutations per Case:", min_value=1, max_value=4, value=2)
            fuzz_samples = st.slider("Samples to Fuzz:", min_value=10, max_value=40, value=20)
            fuzz_seed = st.number_input("Deterministic Seed:", value=42, step=1)
            fuzz_submit = st.form_submit_button("Launch Fuzzing")

        if fuzz_submit:
            with st.spinner(f"Fuzzing defense '{fuzz_defense}' with {fuzz_mutations} mutations..."):
                from mcp_defense_lab.fuzzing.fuzzer import AdaptiveFuzzer
                from mcp_defense_lab.fuzzing.mutators import (
                    ArgumentPathObfuscator,
                    BenignContextWrapperMutator,
                    SynonymMutator,
                    UnicodeZeroWidthMutator,
                )
                import uuid

                fuzz_inst = get_defense(fuzz_defense)
                f_prov = ScriptedFakeModelProvider(mode=ScriptedBehaviorMode.NAIVE_COMPLIANT)
                f_cases = generate_synthetic_benchmark()[:fuzz_samples]

                fuzzer_eng = AdaptiveFuzzer(
                    mutators=[
                        SynonymMutator(),
                        UnicodeZeroWidthMutator(),
                        BenignContextWrapperMutator(),
                        ArgumentPathObfuscator(),
                    ],
                    seed=int(fuzz_seed),
                    max_mutations_per_case=int(fuzz_mutations),
                )
                f_res = fuzzer_eng.run_fuzz_evaluation(
                    defense=fuzz_inst,
                    provider=f_prov,
                    baseline_cases=f_cases,
                    fuzz_run_id=f"fuzz_{uuid.uuid4().hex[:8]}",
                )
                repo.save_fuzz_run(f_res)
                st.success("Adaptive fuzz run finished!")
                st.rerun()

    if not fuzz_runs:
        st.info("No fuzz runs recorded yet. Launch a fuzz run above.")
    else:
        st.subheader("Recorded Adaptive Fuzz Runs")
        fuzz_table = []
        for fr in fuzz_runs:
            fuzz_table.append({
                "Run ID": fr["id"],
                "Defense": fr["defense_name"],
                "Mutations": fr["mutations_count"],
                "Delta ASR": f"{fr['delta_asr']:+.1%}",
                "Delta TCR": f"{fr['delta_tcr']:+.1%}",
                "Delta FPR": f"{fr['delta_fpr']:+.1%}",
                "Summary": fr["summary"],
                "Timestamp": fr["created_at"],
            })
        st.dataframe(pd.DataFrame(fuzz_table), use_container_width=True)

# ==============================================================================
# TAB 5: GRANULAR CASE INSPECTOR
# ==============================================================================
with tabs[4]:
    st.subheader("Per-Case Decision & Audit Trail Inspector")
    if selected_exp_id and exp_data:
        case_records = exp_data.get("cases", [])
        if not case_records:
            st.info("No case records available for this experiment.")
        else:
            filter_type = st.radio("Filter Case Type:", options=["All", "Attack Cases Only", "Benign Cases Only"], horizontal=True)
            filtered = case_records
            if filter_type == "Attack Cases Only":
                filtered = [c for c in case_records if c["is_attack"] == 1]
            elif filter_type == "Benign Cases Only":
                filtered = [c for c in case_records if c["is_attack"] == 0]

            display_records = []
            for c in filtered:
                display_records.append({
                    "Case ID": c["case_id"],
                    "Title": c["title"],
                    "Type": "ATTACK" if c["is_attack"] == 1 else "BENIGN",
                    "Paradigm": c["paradigm"],
                    "Risk": c["risk_category"],
                    "Proposed Tool": c["proposal_tool"],
                    "Decision": c["defense_decision"].upper(),
                    "Reason Code": c["defense_reason_code"],
                    "Executed": "YES" if c["executed"] == 1 else "NO",
                    "Attack Succeeded": "YES" if c["attack_succeeded"] == 1 else "NO",
                    "Benign Completed": "YES" if c["benign_completed"] == 1 else "NO",
                })
            st.dataframe(pd.DataFrame(display_records), use_container_width=True)

            # Detailed Drill-down
            st.markdown("---")
            st.subheader("Detailed Case Audit Log")
            selected_case_id = st.selectbox("Inspect Individual Case:", options=[c["case_id"] for c in filtered])
            selected_c = next((c for c in filtered if c["case_id"] == selected_case_id), None)
            if selected_c:
                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("**User Request:**")
                    st.code(selected_c["user_prompt"], language="text")
                    st.markdown("**Proposed Tool & Arguments:**")
                    st.code(f"{selected_c['proposal_tool']}({selected_c['proposal_args_json']})", language="json")

                with dc2:
                    st.markdown(f"**Defense Decision:** `{selected_c['defense_decision'].upper()}`")
                    st.markdown(f"**Reason Code:** `{selected_c['defense_reason_code']}`")
                    st.markdown(f"**Explanation:** {selected_c['defense_explanation']}")
                    st.markdown(f"**Executed in Sandbox:** `{bool(selected_c['executed'])}`")
                    st.markdown(f"**Attack Succeeded:** `{bool(selected_c['attack_succeeded'])}`")
                    st.markdown(f"**Benign Task Completed:** `{bool(selected_c['benign_completed'])}`")

# ==============================================================================
# TAB 6: DATA EXPORT
# ==============================================================================
with tabs[5]:
    st.subheader("One-Click Research Data Exports")
    if selected_exp_id and exp_data:
        st.write(f"Export telemetry and metrics for experiment `{selected_exp_id}` ({exp_data['title']}).")

        ec1, ec2 = st.columns(2)
        with ec1:
            csv_data = pd.DataFrame(exp_data.get("cases", [])).to_csv(index=False)
            st.download_button(
                label="📥 Download Granular Cases CSV",
                data=csv_data,
                file_name=f"{selected_exp_id}_cases.csv",
                mime="text/csv",
            )
        with ec2:
            json_data = json.dumps(exp_data, indent=2)
            st.download_button(
                label="📥 Download Full Experiment JSON",
                data=json_data,
                file_name=f"{selected_exp_id}_full.json",
                mime="application/json",
            )
    else:
        st.info("Select an experiment to export data.")
