"""
Field policy for technical-only specs per category.
Keeps essential technical keys and maps common synonyms to canonical names.
"""

FIELD_POLICY = {
    "imprimantes_scanners": {
        "allowed": [
            "brand", "model", "technology",
            "print_speed_ppm", "print_resolution_dpi",
            "scan_speed_ipm", "scan_resolution_dpi", "optical_resolution_dpi",
            "duplex", "adf", "adf_capacity_sheets",
            "paper_sizes", "max_document_size_mm",
            "connectivity", "interfaces", "wireless",
            "color_depth_bit",
            "duty_cycle_pages_month",
            "dimensions_mm", "weight_kg",
            "power_consumption_w", "noise_db",
            "twain_driver", "ocr_supported"
        ],
        "synonyms": {
            "ppm": "print_speed_ppm",
            "scan_speed": "scan_speed_ipm",
            "ipm": "scan_speed_ipm",
            "resolution_print": "print_resolution_dpi",
            "resolution_scan": "scan_resolution_dpi",
            "optical_resolution": "optical_resolution_dpi",
            "resolution_optique": "optical_resolution_dpi",
            "wifi": "connectivity",
            "wireless": "connectivity",
            "ethernet": "connectivity",
            "usb": "interfaces",
            "size": "dimensions_mm",
            "max_document_size": "max_document_size_mm",
            "color_depth": "color_depth_bit",
            "adf_capacity": "adf_capacity_sheets",
            "adf_pages": "adf_capacity_sheets",
            "twain": "twain_driver",
            "ocr": "ocr_supported",
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
