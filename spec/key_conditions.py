"""Presentation priorities only: values/parsing still come from ParameterSpec."""

KEY_CONDITIONS = frozenset({
    "kind", "variant", "charge_c_rate", "discharge_c_rate", "reference_c_rate",
    "c_rate", "pulse_c_rate", "charge_voltage_v", "discharge_cutoff_v",
    "upper_voltage_v", "lower_voltage_v", "voltage_v", "end_voltage_v",
    "cv_cutoff_c_rate", "rest_s", "rest_after_charge_s", "rest_after_discharge_s",
    "duration_s", "cycles", "repeat_count", "repeat", "start_soc", "initial_soc",
    "dod_percent", "pulse_s", "dcir_pulse_c_rates", "soc_points", "high_rate_dod_percent",
    "cycle_count", "loop_count", "condition_c_rate", "soc_control", "start_soc_percent",
    "soc_voltage_v", "high_rate_start_c", "high_rate_step_c", "high_rate_levels",
    "charge_end_voltage_v", "discharge_end_voltage_v", "soc_fractions", "dcir_pulse_s",
})
