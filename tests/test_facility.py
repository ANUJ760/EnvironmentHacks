"""Unit tests for ProcessingFacility and mass/energy conservation at facility level."""

import unittest
from ecotwin.categories import WasteCategory
from ecotwin.exceptions import CapacityExceededError, PhysicsViolationError
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.stream import WasteStream
from ecotwin.units import EnergyUnit, Mass, SpecificEnergy


class TestProcessingFacility(unittest.TestCase):
    def test_profile_mass_conservation_check(self):
        # Valid profile summing to 1.0
        valid_profile = CategoryProcessingProfile(
            material_recovery_rate=0.70,
            landfill_residue_rate=0.20,
            process_loss_rate=0.10,
        )
        self.assertEqual(valid_profile.material_recovery_rate, 0.70)

        # Invalid profile summing to 0.85
        with self.assertRaises(PhysicsViolationError):
            CategoryProcessingProfile(
                material_recovery_rate=0.50,
                landfill_residue_rate=0.35,
                process_loss_rate=0.00,
            )

        # Invalid negative rate
        with self.assertRaises(PhysicsViolationError):
            CategoryProcessingProfile(
                material_recovery_rate=1.20,
                landfill_residue_rate=-0.20,
            )

    def test_facility_normal_processing(self):
        facility = ProcessingFacility(
            name="Composting_Plant",
            capacity=Mass.tonnes(100.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.45,
                landfill_residue_rate=0.15,
                process_loss_rate=0.40,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(200.0),
                energy_efficiency=0.50,
            ),
        )

        stream = WasteStream.single_category(Mass.tonnes(80.0), WasteCategory.ORGANIC)
        result = facility.process(stream, energy_output_unit=EnergyUnit.KWH)

        self.assertEqual(result.facility_name, "Composting_Plant")
        self.assertEqual(result.input_mass.to_tonnes().value, 80.0)
        self.assertEqual(result.material_recovered_mass.to_tonnes().value, 36.0) # 80 * 0.45
        self.assertEqual(result.landfill_residue_mass.to_tonnes().value, 12.0)   # 80 * 0.15
        self.assertEqual(result.process_loss_mass.to_tonnes().value, 32.0)       # 80 * 0.40

        # Mass balance check
        sum_out = (
            result.material_recovered_mass.to_tonnes().value
            + result.landfill_residue_mass.to_tonnes().value
            + result.process_loss_mass.to_tonnes().value
        )
        self.assertAlmostEqual(sum_out, 80.0)

        # Energy: 80 tonnes * 200 kWh/tonne * 0.50 = 8000 kWh
        self.assertEqual(result.energy_recovered.value, 8000.0)
        self.assertEqual(result.energy_recovered.unit, EnergyUnit.KWH)

    def test_facility_capacity_exceeded_raises_error(self):
        facility = ProcessingFacility(
            name="Small_MRF",
            capacity=Mass.tonnes(50.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.80,
                landfill_residue_rate=0.20,
            ),
        )

        overload_stream = WasteStream.single_category(Mass.tonnes(55.0), WasteCategory.RECYCLABLE)
        with self.assertRaises(CapacityExceededError):
            facility.process(overload_stream)

    def test_facility_unaccepted_category_raises_error(self):
        facility = ProcessingFacility(
            name="Organics_Only",
            capacity=Mass.tonnes(100.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.50,
                landfill_residue_rate=0.50,
            ),
        )

        stream = WasteStream.single_category(Mass.tonnes(20.0), WasteCategory.E_WASTE)
        with self.assertRaises(PhysicsViolationError):
            facility.process(stream)


if __name__ == "__main__":
    unittest.main()
