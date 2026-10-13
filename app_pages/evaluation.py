import streamlit as st

from src.evaluation import evaluate_suite
from src.ui import csv_bytes, fmt_num

st.title("Evaluation")
st.caption("Held-out synthetic scenarios. Undefined precision, recall, or F1 stay blank in meaning: the table prints the word undefined.")
st.write(
    "ECHO's morning alert is compared with a 2-day inventory-cover baseline on the same deterministic scenarios. "
    "The detector does not see future demand or future stockouts. "
    "Precision is undefined when a detector raises no alerts. Recall is undefined when a scenario has no shortage label. "
    "Nothing here is a guarantee that ECHO beats the baseline."
)

if "eval_report" not in st.session_state:
    st.session_state.eval_report = None

if st.button("Run held-out evaluation", type="primary", icon=":material/rule:"):
    with st.spinner("Replaying held-out synthetic scenarios…"):
        try:
            st.session_state.eval_report = evaluate_suite()
            st.session_state.eval_error = None
        except Exception as exc:
            st.session_state.eval_report = None
            st.session_state.eval_error = f"{type(exc).__name__}: {exc}"

if st.session_state.get("eval_error"):
    st.caption(st.session_state.eval_error)
    st.stop()

report = st.session_state.eval_report
if report is None:
    st.caption("Press Run held-out evaluation when you want precision, recall, F1, lead time, and the operating comparison. The page stays quiet until then.")
    st.stop()

definition = report["detection_definition"]
st.caption(definition["echo_rule"])
st.caption("Baseline: " + definition["baseline_rule"])
st.caption(
    definition["leakage"]
    + f" Detection window: {definition['window_days']} days, shortened if it would run past the horizon."
)

st.subheader("Detection")
detection = report["detection"].copy()
for column in (
    "echo_precision",
    "echo_recall",
    "echo_f1",
    "baseline_precision",
    "baseline_recall",
    "baseline_f1",
    "warning_lead_time_echo_days",
    "warning_lead_time_baseline_days",
):
    detection[column] = detection[column].map(lambda value: "undefined" if value is None or (isinstance(value, float) and value != value) else round(float(value), 3))
st.dataframe(detection, width="stretch", hide_index=True)

st.subheader("Operating results")
operations = report["operations"].copy()
operations["service_level"] = operations["service_level"].map(
    lambda value: "undefined" if value is None else f"{float(value) * 100:.1f}%"
)
st.dataframe(
    operations[
        [
            "scenario",
            "policy_label",
            "unmet_demand_crates",
            "stockout_events",
            "service_level",
            "recovery_status",
            "recovery_days",
            "estimated_spoilage_crates",
            "transport_cost_units",
        ]
    ],
    width="stretch",
    hide_index=True,
)

st.subheader("Computed findings")
for note in report["findings"]:
    st.write(note)

st.download_button(
    "Download detection table",
    data=csv_bytes(report["detection"]),
    file_name="echo_detection.csv",
    mime="text/csv",
)
st.download_button(
    "Download operating table",
    data=csv_bytes(report["operations"]),
    file_name="echo_operations.csv",
    mime="text/csv",
)
st.caption("Empty metric cells in the source data are undefined, not zero. " + fmt_num(len(report["findings"]), 0) + " finding lines were generated from these tables.")
