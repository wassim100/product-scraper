"""
Field policy for technical-only specs per category.
Keeps essential technical keys and maps common synonyms to canonical names.
"""

FIELD_POLICY = {
    "imprimantes_scanners": {
        "allowed": [
            "brand", "model", "technology", "print_speed_ppm", "print_resolution_dpi",
            "scan_resolution_dpi", "duplex", "adf", "paper_sizes", "connectivity",
            "interfaces", "duty_cycle_pages_month", "dimensions_mm", "weight_kg",
            "power_consumption_w", "noise_db"
        ],
        "synonyms": {
            "ppm": "print_speed_ppm",
            "resolution_print": "print_resolution_dpi",
            "resolution_scan": "scan_resolution_dpi",
            "wifi": "connectivity",
            "ethernet": "connectivity",
            "usb": "interfaces",
            "size": "dimensions_mm",
            "weight": "weight_kg",
        },
    },
    "serveurs": {
        "allowed": [
            "brand", "model", "cpu_model", "cpu_sockets", "cpu_cores_total", "ram_installed_gb",
            "ram_max_gb", "ram_type", "ram_speed_mhz", "storage_bays", "storage_form_factors",
            "raid_controller", "nic_ports", "pcie_slots", "psu_watts", "form_factor",
            "dimensions_mm", "weight_kg"
        ],
        "synonyms": {
            "cpu": "cpu_model",
            "sockets": "cpu_sockets",
            "cores": "cpu_cores_total",
            "memory": "ram_installed_gb",
            "memory_max": "ram_max_gb",
            "psu": "psu_watts",
            "lan": "nic_ports",
            "pcie": "pcie_slots",
            "size": "dimensions_mm",
            "weight": "weight_kg",
        },
    },
    "stockage": {
        "allowed": [
            "brand", "model", "type", "controller", "drive_bays", "max_capacity_tb",
            "raid_levels", "interfaces", "protocols", "cache_gb", "throughput_mb_s",
            "expansion_units", "dimensions_mm", "weight_kg", "psu_watts", "form_factor",
            "nic_ports"
        ],
        "synonyms": {
            "capacity_max": "max_capacity_tb",
            "cache": "cache_gb",
            "lan": "nic_ports",
            "size": "dimensions_mm",
            "weight": "weight_kg",
        },
    },
}
