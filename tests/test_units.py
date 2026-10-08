"""Unit tests for Mass, Energy, and SpecificEnergy units."""

import unittest
from ecotwin.exceptions import PhysicsViolationError
from ecotwin.units import Energy, EnergyUnit, Mass, MassUnit, SpecificEnergy


class TestUnits(unittest.TestCase):
    def test_mass_conversions(self):
        m_tonnes = Mass.tonnes(2.5)
        m_kg = m_tonnes.to_kg()
        self.assertEqual(m_kg.value, 2500.0)
        self.assertEqual(m_kg.unit, MassUnit.KG)

        m_back_tonnes = m_kg.to_tonnes()
        self.assertEqual(m_back_tonnes.value, 2.5)
        self.assertEqual(m_back_tonnes.unit, MassUnit.TONNES)

    def test_mass_arithmetic_and_comparisons(self):
        m1 = Mass.kg(500.0)
        m2 = Mass.tonnes(0.5)
        total = m1 + m2
        self.assertEqual(total.value, 1000.0)
        self.assertEqual(total.unit, MassUnit.KG)

        self.assertEqual(m1, m2)
        self.assertTrue(m1 <= m2)
        self.assertTrue(m1 >= m2)

        m3 = Mass.tonnes(1.0)
        self.assertTrue(m1 < m3)
        self.assertTrue(m3 > m1)

        diff = m3 - m1
        self.assertEqual(diff.to_kg().value, 500.0)

        scaled = m1 * 3
        self.assertEqual(scaled.value, 1500.0)
        rscaled = 3 * m1
        self.assertEqual(rscaled.value, 1500.0)

        ratio = m3 / m1
        self.assertAlmostEqual(ratio, 2.0)

    def test_mass_negative_and_nan_invalid(self):
        with self.assertRaises(PhysicsViolationError):
            Mass.kg(-10.0)
        with self.assertRaises(PhysicsViolationError):
            Mass.tonnes(float("nan"))
        with self.assertRaises(PhysicsViolationError):
            Mass.tonnes(float("inf"))

    def test_energy_conversions_and_arithmetic(self):
        e_kwh = Energy.kwh(2500.0)
        e_mwh = e_kwh.to_mwh()
        self.assertEqual(e_mwh.value, 2.5)
        self.assertEqual(e_mwh.unit, EnergyUnit.MWH)

        e_back_kwh = e_mwh.to_kwh()
        self.assertEqual(e_back_kwh.value, 2500.0)

        e1 = Energy.kwh(1000.0)
        e2 = Energy.mwh(1.0)
        self.assertEqual(e1, e2)

        total = e1 + e2
        self.assertEqual(total.value, 2000.0)

    def test_energy_negative_and_nan_invalid(self):
        with self.assertRaises(PhysicsViolationError):
            Energy.kwh(-5.0)
        with self.assertRaises(PhysicsViolationError):
            Energy.mwh(float("nan"))

    def test_specific_energy_calculation(self):
        # 10 tonnes of waste with 2000 kWh/tonne calorific content at 25% efficiency
        mass = Mass.tonnes(10.0)
        spec_e = SpecificEnergy.from_kwh_per_tonne(2000.0)
        
        # Energy = 10 tonnes * 2000 kWh/tonne * 0.25 = 5000 kWh = 5 MWh
        energy_kwh = spec_e.calculate_energy(mass, efficiency=0.25, output_unit=EnergyUnit.KWH)
        self.assertEqual(energy_kwh.value, 5000.0)
        self.assertEqual(energy_kwh.unit, EnergyUnit.KWH)

        energy_mwh = spec_e.calculate_energy(mass, efficiency=0.25, output_unit=EnergyUnit.MWH)
        self.assertEqual(energy_mwh.value, 5.0)
        self.assertEqual(energy_mwh.unit, EnergyUnit.MWH)

    def test_specific_energy_from_other_units(self):
        # 10 MJ/kg = (10 / 3.6) * 1000 kWh/tonne = 2777.777... kWh/tonne
        spec_from_mj = SpecificEnergy.from_mj_per_kg(3.6)
        self.assertAlmostEqual(spec_from_mj.kwh_per_tonne, 1000.0)

        spec_from_kg = SpecificEnergy.from_kwh_per_kg(2.0)
        self.assertEqual(spec_from_kg.kwh_per_tonne, 2000.0)

    def test_specific_energy_invalid_efficiency(self):
        spec = SpecificEnergy.from_kwh_per_tonne(1000.0)
        with self.assertRaises(PhysicsViolationError):
            spec.calculate_energy(Mass.tonnes(1.0), efficiency=1.5)
        with self.assertRaises(PhysicsViolationError):
            spec.calculate_energy(Mass.tonnes(1.0), efficiency=-0.1)


if __name__ == "__main__":
    unittest.main()
