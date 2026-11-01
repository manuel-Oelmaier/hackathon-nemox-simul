import unittest

from quoting.air_weight import chargeable_kg, rate_air_leg, volume_weight_kg


class AirWeightTests(unittest.TestCase):
    def test_fra_ord_loose_cartons_use_volume_weight(self) -> None:
        # 12 cartons, 180 kg actual, 4.2 cbm. 4.2 × 167 = 701.4 kg.
        result = rate_air_leg(
            actual_kg=180,
            cbm=4.2,
            origin="FRA",
            destination="ORD",
            rate_eur_per_kg=1.85,
        )
        self.assertEqual(result["volume_weight_kg"], 701.4)
        self.assertEqual(result["chargeable_kg"], 701.4)
        self.assertEqual(result["rate_eur_per_kg"], 1.85)
        self.assertEqual(result["origin"], "FRA")
        self.assertEqual(result["destination"], "ORD")

    def test_dense_cargo_keeps_actual_weight(self) -> None:
        chargeable, volumetric = chargeable_kg(800, 1.0)
        self.assertEqual(volumetric, 167.0)
        self.assertEqual(chargeable, 800)

    def test_missing_volume_does_not_invent_weight(self) -> None:
        chargeable, volumetric = chargeable_kg(180, None)
        self.assertIsNone(volumetric)
        self.assertEqual(chargeable, 180)

    def test_zero_volume_uses_actual(self) -> None:
        chargeable, volumetric = chargeable_kg(180, 0)
        self.assertEqual(volumetric, 0.0)
        self.assertEqual(chargeable, 180)

    def test_volume_weight_formula(self) -> None:
        self.assertEqual(volume_weight_kg(4.2), 701.4)

    def test_rejects_negative_inputs(self) -> None:
        with self.assertRaises(ValueError):
            volume_weight_kg(-1)
        with self.assertRaises(ValueError):
            chargeable_kg(-1, 1.0)


if __name__ == "__main__":
    unittest.main()
