# io_calculator.py
"""
I/O Calculator für Festplatten- und Netzwerk-Performance.
Berechnet Datenraten basierend auf psutil-Metriken.
"""

import logging
from typing import Dict, Tuple

from utils.system_utils import psutil, PSUTIL_AVAILABLE

# Konstanten zur Umrechnung
BYTES_TO_MB = 1024 * 1024
BITS_IN_BYTE = 8
BITS_TO_MBIT = 10**6

class IOCalculator:
    """
    Berechnet Festplatten- und Netzwerk-I/O Raten mit Fehlerbehandlung
    und Validierung unrealistischer Werte.
    """

    def __init__(self, settings: dict):
        self.settings = settings
        self.prev_disk_io: Dict = {}
        self.prev_net_io: Dict = {}
        
        # Limits für unrealistische Werte (in GB/s und Gbit/s)
        self.max_disk_io_gbps = 10
        self.max_network_gbps = 100
        
        if PSUTIL_AVAILABLE:
            self._initialize_baseline()
        logging.debug("IOCalculator initialisiert")

    def _initialize_baseline(self):
        """Initialisiert Baseline-Werte für I/O-Berechnungen."""
        try:
            self.prev_disk_io = psutil.disk_io_counters(perdisk=True) or {}
            self.prev_net_io = psutil.net_io_counters(pernic=True) or {}
            logging.debug("I/O Baseline initialisiert")
        except Exception as e:
            logging.error(f"I/O Baseline-Initialisierung fehlgeschlagen: {e}")
            self.prev_disk_io, self.prev_net_io = {}, {}

    def update_settings(self, key: str, value):
        """Aktualisiert eine einzelne Einstellung."""
        self.settings[key] = value
        logging.debug(f"IOCalculator Einstellung aktualisiert: {key} = {value}")

    def calculate_disk_io(self, elapsed_time: float) -> Dict[str, float]:
        """Berechnet Festplatten-I/O Raten in MB/s."""
        if not PSUTIL_AVAILABLE:
            return self._get_zero_disk_io()

        try:
            current_disk_io = psutil.disk_io_counters(perdisk=True)
            if not current_disk_io:
                return self._get_zero_disk_io()

            selected_disk = self.settings.get("selected_disk_io_device")
            if not selected_disk or selected_disk not in current_disk_io:
                if selected_disk:
                    logging.warning(f"Ausgewählte Festplatte '{selected_disk}' nicht verfügbar")
                self.prev_disk_io = current_disk_io
                return self._get_zero_disk_io()

            if selected_disk not in self.prev_disk_io:
                self.prev_disk_io = current_disk_io
                return self._get_zero_disk_io()

            current_stats = current_disk_io[selected_disk]
            prev_stats = self.prev_disk_io[selected_disk]
            read_bytes = max(0, current_stats.read_bytes - prev_stats.read_bytes)
            write_bytes = max(0, current_stats.write_bytes - prev_stats.write_bytes)

            read_mbps = (read_bytes / elapsed_time) / BYTES_TO_MB
            write_mbps = (write_bytes / elapsed_time) / BYTES_TO_MB

            max_mbps = self.max_disk_io_gbps * 1024
            if read_mbps > max_mbps or write_mbps > max_mbps:
                logging.warning(f"Unrealistische Disk I/O Werte: R={read_mbps:.1f}, W={write_mbps:.1f} MB/s")
                return self._get_zero_disk_io()

            self.prev_disk_io = current_disk_io
            return {'disk_read_mbps': read_mbps, 'disk_write_mbps': write_mbps}
        except Exception as e:
            logging.error(f"Disk I/O Berechnung fehlgeschlagen: {e}")
            return self._get_zero_disk_io()

    def calculate_network_io(self, elapsed_time: float) -> Dict[str, float]:
        """Berechnet Netzwerk-I/O Raten in MBit/s."""
        if not PSUTIL_AVAILABLE:
            return self._get_zero_network_io()
            
        try:
            current_net_io = psutil.net_io_counters(pernic=True)
            if not current_net_io:
                return self._get_zero_network_io()

            selected_nic = self.settings.get("selected_network_interface", "all")
            if selected_nic == "all":
                up_mbps, down_mbps = self._calculate_total_network_io(current_net_io, elapsed_time)
            else:
                up_mbps, down_mbps = self._calculate_single_nic_io(current_net_io, selected_nic, elapsed_time)

            max_mbps = self.max_network_gbps * 1000
            if up_mbps > max_mbps or down_mbps > max_mbps:
                logging.warning(f"Unrealistische Netzwerk-Werte: U={up_mbps:.1f}, D={down_mbps:.1f} Mbit/s")
                return self._get_zero_network_io()

            self.prev_net_io = current_net_io
            return {'net_up_mbps': up_mbps, 'net_down_mbps': down_mbps}
        except Exception as e:
            logging.error(f"Netzwerk I/O Berechnung fehlgeschlagen: {e}")
            return self._get_zero_network_io()

    def _calculate_total_network_io(self, current_net_io: dict, elapsed_time: float) -> Tuple[float, float]:
        """Berechnet die Gesamt-Netzwerk-I/O über alle Interfaces."""
        total_sent, total_recv = 0, 0
        for nic, stats in current_net_io.items():
            if nic in self.prev_net_io:
                prev_stats = self.prev_net_io[nic]
                total_sent += max(0, stats.bytes_sent - prev_stats.bytes_sent)
                total_recv += max(0, stats.bytes_recv - prev_stats.bytes_recv)

        up_mbps = (total_sent * BITS_IN_BYTE) / elapsed_time / BITS_TO_MBIT
        down_mbps = (total_recv * BITS_IN_BYTE) / elapsed_time / BITS_TO_MBIT
        return up_mbps, down_mbps

    def _calculate_single_nic_io(self, current_net_io: dict, nic: str, elapsed_time: float) -> Tuple[float, float]:
        """Berechnet I/O für ein einzelnes Netzwerk-Interface."""
        if nic not in current_net_io or nic not in self.prev_net_io:
            if nic not in current_net_io:
                logging.warning(f"Netzwerk-Interface '{nic}' nicht verfügbar")
            return 0.0, 0.0

        stats, prev_stats = current_net_io[nic], self.prev_net_io[nic]
        sent_bytes = max(0, stats.bytes_sent - prev_stats.bytes_sent)
        recv_bytes = max(0, stats.bytes_recv - prev_stats.bytes_recv)

        up_mbps = (sent_bytes * BITS_IN_BYTE) / elapsed_time / BITS_TO_MBIT
        down_mbps = (recv_bytes * BITS_IN_BYTE) / elapsed_time / BITS_TO_MBIT
        return up_mbps, down_mbps

    def calculate_all(self, elapsed_time: float) -> Dict[str, float]:
        """Berechnet alle I/O Metriken."""
        data = {}
        data.update(self.calculate_disk_io(elapsed_time))
        data.update(self.calculate_network_io(elapsed_time))
        return data

    def _get_zero_disk_io(self) -> Dict[str, float]:
        return {'disk_read_mbps': 0.0, 'disk_write_mbps': 0.0}

    def _get_zero_network_io(self) -> Dict[str, float]:
        return {'net_up_mbps': 0.0, 'net_down_mbps': 0.0}