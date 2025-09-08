# monitoring/performance_tracker.py
import gc
import time
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from utils.system_utils import psutil, PSUTIL_AVAILABLE
from config.constants import SettingsKey

if TYPE_CHECKING:
    from utils.settings_manager import SettingsManager

class PerformanceTracker:
    """
    Verfolgt Performance-Metriken und Memory-Verbrauch.
    Erkennt potenzielle Memory Leaks und Performance-Probleme.
    """

    def __init__(self, settings_manager: "SettingsManager"):
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.get_all_settings()
        self._start_time = time.time()
        self.prev_time = self._start_time

        self._load_settings()

        self._baseline_memory: Optional[float] = None
        self._memory_samples: List[Dict[str, Any]] = []
        self._max_memory_samples = 20
        self._last_memory_check = time.time()
        self._peak_memory = 0.0

        self._performance_stats: Dict[str, Any] = {
            'update_count': 0, 'error_count': 0, 'total_update_time': 0.0,
            'avg_update_time': 0.0, 'max_update_time': 0.0, 'min_update_time': float('inf')
        }
        self._memory_warnings: List[Dict[str, Any]] = []
        self._max_warnings = 10
        self._gc_stats = {'manual_collections': 0, 'last_gc_time': 0}

        self._initialize_baseline()
        logging.debug(f"PerformanceTracker initialisiert (Threshold: {self.memory_threshold_mb}MB)")

    def _load_settings(self):
        """Lädt alle Schwellenwerte aus dem Einstellungs-Dictionary."""
        self.settings = self.settings_manager.get_all_settings()
        self.memory_threshold_mb = self.settings.get(SettingsKey.PERF_MEM_THRESHOLD_MB.value, 50)
        self.memory_check_interval_sec = self.settings.get(SettingsKey.PERF_MEM_CHECK_INTERVAL_SEC.value, 60)
        self.memory_trend_threshold_mb = self.settings.get(SettingsKey.PERF_MEM_TREND_THRESHOLD_MB.value, 10)
        self.slow_update_threshold_sec = self.settings.get(SettingsKey.PERF_SLOW_UPDATE_THRESHOLD_SEC.value, 5)
        self.gc_threshold_updates = self.settings.get(SettingsKey.PERF_GC_THRESHOLD_UPDATES.value, 50)

    def update_settings(self, key: str, value: Any):
        if key.startswith('perf_'):
            self._load_settings()
            logging.info(f"PerformanceTracker-Einstellung aktualisiert: {key} = {value}")

    def _initialize_baseline(self):
        """Initialisiert die Baseline aus den Einstellungen oder durch Messung."""
        if not PSUTIL_AVAILABLE:
            logging.warning("psutil nicht verfügbar - Memory Monitoring deaktiviert")
            return

        # KORREKTUR: Lade gespeicherte Baseline
        saved_baseline = self.settings_manager.get_setting("perf_mem_baseline_mb", 0.0)
        if saved_baseline > 0:
            self._baseline_memory = saved_baseline
            self._peak_memory = saved_baseline
            logging.info(f"Gespeicherte Memory Baseline geladen: {self._baseline_memory:.1f}MB")
        else:
            try:
                process = psutil.Process()
                self._baseline_memory = process.memory_info().rss / (1024 * 1024)
                self._peak_memory = self._baseline_memory
                # Speichere die neu erstellte Baseline sofort
                self.settings_manager.set_setting("perf_mem_baseline_mb", self._baseline_memory)
                logging.info(f"Neue Memory Baseline erstellt und gespeichert: {self._baseline_memory:.1f}MB")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logging.error(f"Memory Baseline-Initialisierung fehlgeschlagen: {e}")
                self._baseline_memory = None
        
        if self._baseline_memory is not None:
             self._memory_samples.append({'timestamp': time.time(), 'memory_mb': self._baseline_memory})

    def reset_memory_baseline(self, new_baseline_mb: float = None) -> bool:
        """
        Setzt die Memory Baseline und speichert sie in den Einstellungen.
        """
        try:
            if new_baseline_mb is None:
                if PSUTIL_AVAILABLE:
                    process = psutil.Process()
                    new_baseline_mb = process.memory_info().rss / (1024 * 1024)
                else:
                    logging.error("psutil nicht verfügbar - kann Baseline nicht zurücksetzen")
                    return False
            
            old_baseline = self._baseline_memory
            self._baseline_memory = new_baseline_mb
            self._peak_memory = new_baseline_mb
            self._memory_samples = [{'timestamp': time.time(), 'memory_mb': new_baseline_mb}]
            self._memory_warnings.clear()
            self._last_memory_check = time.time()
            
            # KORREKTUR: Speichere die neue Baseline
            self.settings_manager.set_setting("perf_mem_baseline_mb", new_baseline_mb)
            
            logging.info(f"Memory Baseline zurückgesetzt und gespeichert: {old_baseline:.1f} -> {new_baseline_mb:.1f} MB")
            return True
            
        except Exception as e:
            logging.error(f"Fehler beim Zurücksetzen der Memory Baseline: {e}")
            return False

    def get_elapsed_time(self) -> float:
        """Gibt die Zeit seit dem letzten Aufruf zurück und aktualisiert den Zeitstempel."""
        now = time.time()
        elapsed = now - self.prev_time
        self.prev_time = now
        return elapsed

    def track_update_performance(self, update_time: float):
        stats = self._performance_stats
        stats['update_count'] += 1
        stats['total_update_time'] += update_time
        stats['avg_update_time'] = stats['total_update_time'] / stats['update_count']
        stats['max_update_time'] = max(stats['max_update_time'], update_time)
        stats['min_update_time'] = min(stats['min_update_time'], update_time)

        if update_time > self.slow_update_threshold_sec:
            logging.warning(f"Sehr langsames Update: {update_time:.2f}s")

    def check_memory_usage(self) -> Optional[float]:
        current_time = time.time()
        if (current_time - self._last_memory_check) < self.memory_check_interval_sec or not PSUTIL_AVAILABLE:
            return None
        try:
            process = psutil.Process()
            current_memory = process.memory_info().rss / (1024 * 1024)
            self._memory_samples.append({'timestamp': current_time, 'memory_mb': current_memory})
            if len(self._memory_samples) > self._max_memory_samples: self._memory_samples.pop(0)
            self._peak_memory = max(self._peak_memory, current_memory)
            if self._baseline_memory is not None: self._check_for_memory_leaks(current_memory)
            self._last_memory_check = current_time
            return current_memory
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logging.error(f"Memory Check fehlgeschlagen: {e}")
            return None

    def _check_for_memory_leaks(self, current_memory: float):
        if self._baseline_memory is None: return
        memory_increase = current_memory - self._baseline_memory
        if memory_increase > self.memory_threshold_mb:
            percent = (memory_increase / self._baseline_memory) * 100 if self._baseline_memory > 0 else 0
            self._add_memory_warning({
                'timestamp': time.time(),
                'key': 'perf_warning_mem_increase',
                'kwargs': {'increase': f'{memory_increase:.1f}', 'percent': f'{percent:.1f}'}
            })
        if len(self._memory_samples) >= 10: self._check_memory_trend()

    def _check_memory_trend(self):
        recent_avg = sum(s['memory_mb'] for s in self._memory_samples[-5:]) / 5
        older_avg = sum(s['memory_mb'] for s in self._memory_samples[-10:-5]) / 5
        trend = recent_avg - older_avg
        if trend > self.memory_trend_threshold_mb:
            self._add_memory_warning({
                'timestamp': time.time(),
                'key': 'perf_warning_mem_trend',
                'kwargs': {'trend': f'{trend:.1f}'}
            })

    def _add_memory_warning(self, warning: Dict[str, Any]):
        self._memory_warnings.append(warning)
        if len(self._memory_warnings) > self._max_warnings: self._memory_warnings.pop(0)
        # Logging for developers, does not need translation
        logging.warning(f"Memory warning triggered: {warning.get('key')}")

    def get_performance_stats(self) -> Dict[str, Any]:
        stats, runtime = self._performance_stats.copy(), time.time() - self._start_time
        updates = stats['update_count']
        stats.update({
            'runtime_seconds': runtime,
            'error_rate_percent': (stats['error_count'] / updates * 100) if updates > 0 else 0,
            'avg_update_time_ms': stats['avg_update_time'] * 1000,
            'max_update_time_ms': stats['max_update_time'] * 1000,
            'min_update_time_ms': stats['min_update_time'] * 1000 if stats['min_update_time'] != float('inf') else 0
        })
        return stats
    
    def get_performance_summary(self) -> str:
        """Gibt eine kurze Zusammenfassung der Performance für das Logging zurück."""
        stats = self.get_performance_stats()
        return (f"Avg={stats['avg_update_time_ms']:.1f}ms, "
                f"Max={stats['max_update_time_ms']:.1f}ms, "
                f"Errors={self._performance_stats['error_count']}")

    def get_memory_stats(self) -> Dict[str, Any]:
        if not PSUTIL_AVAILABLE: return {'psutil_available': False}
        current_memory = self._memory_samples[-1]['memory_mb'] if self._memory_samples else None
        increase = (current_memory - self._baseline_memory) if self._baseline_memory and current_memory else None
        return {
            'psutil_available': True, 'baseline_memory_mb': self._baseline_memory,
            'current_memory_mb': current_memory, 'peak_memory_mb': self._peak_memory,
            'memory_increase_mb': increase, 'memory_warnings_count': len(self._memory_warnings)
        }

    def get_recent_memory_warnings(self, minutes: int = 10) -> List[Dict[str, Any]]:
        if not self._memory_warnings: return []
        cutoff = time.time() - (minutes * 60)
        return [w for w in self._memory_warnings if w['timestamp'] > cutoff]

    def get_health_report(self) -> Dict[str, Any]:
        """
        Gibt einen umfassenden Gesundheitsbericht zurück.
        """
        return {
            'performance_stats': self.get_performance_stats(),
            'memory_stats': self.get_memory_stats(),
            'recent_warnings': self.get_recent_memory_warnings(),
            'is_healthy': self._assess_health(),
            'recommendations': self._get_recommendations()
        }

    def _assess_health(self) -> bool:
        """
        Bewertet die allgemeine "Gesundheit" des Systems basierend auf Metriken.
        """
        stats = self.get_performance_stats()
        if stats['error_rate_percent'] > 10: return False
        if stats['avg_update_time_ms'] > 2000: return False
        if len(self.get_recent_memory_warnings(5)) > 3: return False
        return True

    def _get_recommendations(self) -> List[str]:
        """
        Gibt Empfehlungen (als Übersetzungsschlüssel) zur Performance-Verbesserung zurück.
        """
        recommendations = []
        stats = self.get_performance_stats()
        memory_stats = self.get_memory_stats()

        if stats['error_rate_percent'] > 5:
            recommendations.append("perf_reco_high_error")
        if stats['avg_update_time_ms'] > 1000:
            recommendations.append("perf_reco_slow_updates")
        
        mem_increase_mb = memory_stats.get('memory_increase_mb')
        if mem_increase_mb is not None and mem_increase_mb > 50:
            recommendations.append("perf_reco_high_mem")
        if len(self.get_recent_memory_warnings(10)) > 0:
            recommendations.append("perf_reco_mem_warnings")
        
        if not recommendations and self._assess_health():
            recommendations.append("perf_reco_stable")
            
        return recommendations