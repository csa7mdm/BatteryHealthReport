"""
EV Battery Health Analysis Module

This module processes raw vehicle diagnostic data to generate battery health reports
for dealership partners. It calculates State of Health (SoH), tracks charge cycles,
and flags potential anomalies.

Author: Backend Engineering Team
Version: 1.0.0
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from statistics import mean, stdev

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BatteryCell:
    """Represents a single battery cell with its measurements."""
    id: str
    voltage: float
    temperature: float
    internal_resistance: float


@dataclass
class ChargeEvent:
    """Represents a charge/discharge cycle event."""
    timestamp: datetime
    event_type: str  # 'charge' or 'discharge'
    start_soc: float  # State of Charge at start (%)
    end_soc: float    # State of Charge at end (%)
    energy_transferred: float  # kWh


@dataclass
class VehicleDiagnosticData:
    """Raw vehicle diagnostic data structure."""
    vehicle_id: str
    timestamp: datetime
    battery_pack_voltage: float
    total_capacity_kwh: float
    current_capacity_kwh: float
    cells: List[BatteryCell]
    charge_history: List[ChargeEvent]
    odometer_miles: int
    manufacturing_date: datetime


@dataclass
class BatteryHealthReport:
    """Battery health analysis results."""
    vehicle_id: str
    analysis_timestamp: datetime
    state_of_health_percent: float
    charge_cycle_count: int
    anomalies: List[str]
    degradation_rate_per_year: float
    estimated_remaining_capacity_kwh: float
    confidence_score: float


class BatteryHealthAnalyzer:
    """
    Analyzes EV battery health from diagnostic data.
    
    Based on industry standards and real-world EV degradation patterns.
    """
    
    # Industry-standard thresholds
    VOLTAGE_IMBALANCE_THRESHOLD = 0.05  # 50mV difference between cells
    CELL_OVERHEAT_THRESHOLD = 45.0      # 45°C
    HIGH_RESISTANCE_THRESHOLD = 5.0      # 5 milliohms
    MIN_CYCLES_FOR_ANALYSIS = 10         # Minimum cycles for reliable analysis
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_battery_health(self, diagnostic_data: VehicleDiagnosticData) -> BatteryHealthReport:
        """
        Main analysis function that processes diagnostic data and returns health report.
        
        Args:
            diagnostic_data: Raw vehicle diagnostic data
            
        Returns:
            BatteryHealthReport with calculated metrics and anomalies
        """
        self.logger.info(f"Analyzing battery health for vehicle {diagnostic_data.vehicle_id}")
        
        # Calculate State of Health
        soh_percent = self._calculate_state_of_health(diagnostic_data)
        
        # Count charge cycles
        cycle_count = self._count_charge_cycles(diagnostic_data.charge_history)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(diagnostic_data)
        
        # Calculate degradation rate
        degradation_rate = self._calculate_degradation_rate(diagnostic_data)
        
        # Calculate confidence score
        confidence = self._calculate_confidence_score(diagnostic_data)
        
        return BatteryHealthReport(
            vehicle_id=diagnostic_data.vehicle_id,
            analysis_timestamp=datetime.now(),
            state_of_health_percent=soh_percent,
            charge_cycle_count=cycle_count,
            anomalies=anomalies,
            degradation_rate_per_year=degradation_rate,
            estimated_remaining_capacity_kwh=diagnostic_data.current_capacity_kwh,
            confidence_score=confidence
        )
    
    def _calculate_state_of_health(self, data: VehicleDiagnosticData) -> float:
        """
        Calculate State of Health (SoH) as percentage of original capacity.
        
        SoH = (Current Usable Capacity / Original Capacity) * 100
        
        Industry standard: >90% = Excellent, 80-90% = Good, 70-80% = Fair, <70% = Poor
        """
        if data.total_capacity_kwh <= 0:
            self.logger.warning("Invalid total capacity, using estimated value")
            return 0.0
            
        soh = (data.current_capacity_kwh / data.total_capacity_kwh) * 100
        
        # Cap at 100% (sometimes current > total due to measurement variance)
        return min(100.0, round(soh, 1))
    
    def _count_charge_cycles(self, charge_history: List[ChargeEvent]) -> int:
        """
        Count complete charge cycles. A full cycle = 100% discharge + 100% charge.
        Partial cycles are accumulated (e.g., two 50% cycles = one full cycle).
        
        This follows industry standard cycle counting methodology.
        """
        if not charge_history:
            return 0
            
        total_cycles = 0.0
        
        # Sort events by timestamp
        sorted_events = sorted(charge_history, key=lambda x: x.timestamp)
        
        for event in sorted_events:
            if event.event_type == 'discharge':
                # Count discharge depth as fraction of cycle
                discharge_depth = (event.start_soc - event.end_soc) / 100.0
                total_cycles += discharge_depth
        
        return int(total_cycles)
    
    def _detect_anomalies(self, data: VehicleDiagnosticData) -> List[str]:
        """
        Detect battery anomalies that could indicate degradation or safety issues.
        
        Checks for:
        - Cell voltage imbalance
        - Overheating cells  
        - High internal resistance
        - Rapid degradation patterns
        """
        anomalies = []
        
        if not data.cells:
            anomalies.append("No cell data available for analysis")
            return anomalies
        
        # Check voltage imbalance
        voltages = [cell.voltage for cell in data.cells]
        if len(voltages) > 1:
            voltage_range = max(voltages) - min(voltages)
            if voltage_range > self.VOLTAGE_IMBALANCE_THRESHOLD:
                anomalies.append(f"Cell voltage imbalance detected: {voltage_range:.3f}V range")
        
        # Check for overheating
        overheated_cells = [cell for cell in data.cells 
                          if cell.temperature > self.CELL_OVERHEAT_THRESHOLD]
        if overheated_cells:
            max_temp = max(cell.temperature for cell in overheated_cells)
            anomalies.append(f"Cell overheating detected: {max_temp:.1f}°C (threshold: {self.CELL_OVERHEAT_THRESHOLD}°C)")
        
        # Check internal resistance
        high_resistance_cells = [cell for cell in data.cells 
                               if cell.internal_resistance > self.HIGH_RESISTANCE_THRESHOLD]
        if high_resistance_cells:
            max_resistance = max(cell.internal_resistance for cell in high_resistance_cells)
            anomalies.append(f"High internal resistance detected: {max_resistance:.2f}mΩ")
        
        # Check degradation rate
        degradation_rate = self._calculate_degradation_rate(data)
        if degradation_rate > 8.0:  # More than 8% per year is concerning
            anomalies.append(f"Accelerated degradation detected: {degradation_rate:.1f}% per year")
        
        return anomalies
    
    def _calculate_degradation_rate(self, data: VehicleDiagnosticData) -> float:
        """
        Estimate annual degradation rate based on vehicle age and current SoH.
        
        Typical EV batteries degrade 2-8% per year depending on usage patterns.
        """
        vehicle_age_years = (datetime.now() - data.manufacturing_date).days / 365.25
        
        if vehicle_age_years < 0.1:  # Less than ~36 days
            return 0.0
        
        current_soh = self._calculate_state_of_health(data)
        capacity_lost = 100.0 - current_soh
        
        return capacity_lost / vehicle_age_years
    
    def _calculate_confidence_score(self, data: VehicleDiagnosticData) -> float:
        """
        Calculate confidence score (0-100) for the analysis based on data quality.
        
        Factors:
        - Number of charge cycles (more = better)
        - Cell data completeness
        - Vehicle age (too new = less reliable)
        - Data consistency
        """
        confidence = 100.0
        
        # Reduce confidence if insufficient cycle data
        cycle_count = self._count_charge_cycles(data.charge_history)
        if cycle_count < self.MIN_CYCLES_FOR_ANALYSIS:
            confidence -= 30.0
        
        # Reduce confidence if missing cell data
        if not data.cells:
            confidence -= 40.0
        elif len(data.cells) < 4:  # Minimal cell monitoring
            confidence -= 20.0
        
        # Reduce confidence for very new vehicles
        vehicle_age_years = (datetime.now() - data.manufacturing_date).days / 365.25
        if vehicle_age_years < 0.5:
            confidence -= 25.0
        
        return max(0.0, min(100.0, confidence))


def create_mock_diagnostic_data() -> VehicleDiagnosticData:
    """
    Create realistic mock diagnostic data for testing.
    Based on typical Tesla Model 3 specifications.
    """
    # Mock battery cells (simplified - real Tesla has ~4400 cells)
    cells = [
        BatteryCell(id="cell_001", voltage=3.92, temperature=32.5, internal_resistance=2.1),
        BatteryCell(id="cell_002", voltage=3.91, temperature=33.1, internal_resistance=2.3),
        BatteryCell(id="cell_003", voltage=3.93, temperature=32.8, internal_resistance=2.0),
        BatteryCell(id="cell_004", voltage=3.89, temperature=34.2, internal_resistance=2.4),  # Slightly degraded
        BatteryCell(id="cell_005", voltage=3.92, temperature=32.9, internal_resistance=2.2),
        BatteryCell(id="cell_006", voltage=3.90, temperature=33.5, internal_resistance=2.1),
    ]
    
    # Mock charge history (3 years of data)
    base_date = datetime.now() - timedelta(days=1095)  # 3 years ago
    charge_history = []
    
    # Simulate ~250 cycles over 3 years (realistic for daily driver)
    for i in range(250):
        charge_date = base_date + timedelta(days=i * 4 + (i % 7))  # Every 4-7 days
        
        # Discharge event
        charge_history.append(ChargeEvent(
            timestamp=charge_date,
            event_type='discharge',
            start_soc=85.0 + (i % 15),  # Varies charge level
            end_soc=15.0 + (i % 10),
            energy_transferred=45.2 - (i * 0.02)  # Gradual capacity loss
        ))
        
        # Charge event (next day)
        charge_history.append(ChargeEvent(
            timestamp=charge_date + timedelta(hours=18),
            event_type='charge',
            start_soc=15.0 + (i % 10),
            end_soc=85.0 + (i % 15),
            energy_transferred=45.2 - (i * 0.02)
        ))
    
    return VehicleDiagnosticData(
        vehicle_id="TSLA_5YJ3E1EA8KF123456",
        timestamp=datetime.now(),
        battery_pack_voltage=350.4,
        total_capacity_kwh=75.0,  # Original Tesla Model 3 Long Range
        current_capacity_kwh=53.25,  # 71% SoH (matches the scenario)
        cells=cells,
        charge_history=charge_history,
        odometer_miles=87500,
        manufacturing_date=datetime.now() - timedelta(days=1095)  # 3 years old
    )


def main():
    """Example usage of the battery health analyzer."""
    
    # Create analyzer
    analyzer = BatteryHealthAnalyzer()
    
    # Generate mock data
    diagnostic_data = create_mock_diagnostic_data()
    
    # Analyze battery health
    report = analyzer.analyze_battery_health(diagnostic_data)
    
    # Print results
    print("=" * 60)
    print("EV BATTERY HEALTH REPORT")
    print("=" * 60)
    print(f"Vehicle ID: {report.vehicle_id}")
    print(f"Analysis Date: {report.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print(f"State of Health: {report.state_of_health_percent}%")
    print(f"Charge Cycles: {report.charge_cycle_count}")
    print(f"Degradation Rate: {report.degradation_rate_per_year:.1f}% per year")
    print(f"Confidence Score: {report.confidence_score:.1f}%")
    print()
    
    if report.anomalies:
        print("⚠️ ANOMALIES DETECTED:")
        for anomaly in report.anomalies:
            print(f"  • {anomaly}")
    else:
        print("✅ No anomalies detected")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
