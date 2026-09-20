from __future__ import annotations

import unittest

from norfront_claw.guards import check_text, classify


class GuardsTest(unittest.TestCase):
    def test_safe_text_passes(self) -> None:
        v = check_text("Summarize https://example.com and list the headings")
        self.assertTrue(v.allowed)
        self.assertIsNone(v.kind)
        self.assertFalse(v.used_typesafe)

    def test_pay_is_blocked(self) -> None:
        v = check_text("checkout and pay with the saved card")
        self.assertFalse(v.allowed)
        self.assertEqual(v.kind, "pay")

    def test_signup_is_blocked(self) -> None:
        self.assertEqual(classify("please sign up for a new account"), "signup")

    def test_delete_account_is_blocked(self) -> None:
        self.assertEqual(classify("permanently delete this user account"), "delete")

    def test_allow_flag(self) -> None:
        v = check_text("place order for the listed SKU", allow_irreversible=True)
        self.assertTrue(v.allowed)
        self.assertEqual(v.kind, "pay")

    def test_no_typesafe(self) -> None:
        v = check_text("send this email to the customer")
        self.assertFalse(v.used_typesafe)


if __name__ == "__main__":
    unittest.main()
