"""Focused checks for PP-IDENTITY-001 scheduling, duration and fail-closed behavior."""
import asyncio
import unittest

from modules.pubpartner_identity_checkpoint import checkpoint, scheduled


def packet():
    return {
        "fcp1": {
            "f": {"id": "alex"},
            "u": {"id": "owner"},
            "m": [],
            "guide": [],
            "safe": [],
            "history": [],
            "source_policy": {"immutable": True},
        },
        "llm_prompt_text": "@FCP1\nu={}" + "\nf={\\\"id\\\":\\\"alex\\\"}",
        "memory_count": 0,
        "guidance_count": 0,
    }


class IdentityCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_fourth_seventh_and_not_second_third(self):
        self.assertEqual([n for n in range(1, 11) if scheduled(n)], [1, 4, 7, 10])

    async def test_full_wait_and_receipt_fields(self):
        clock_value = [0.0]
        async def sleep(seconds):
            clock_value[0] += seconds
        result = await checkpoint(packet(), 1, clock=lambda: clock_value[0], sleep=sleep)
        self.assertTrue(result["full_refresh"])
        self.assertGreaterEqual(clock_value[0], 1.0)
        self.assertEqual(result["friend_id"], "alex")

    async def test_lightweight_turn_does_not_wait(self):
        async def sleep(seconds):
            self.fail("Lightweight turn should not sleep")
        result = await checkpoint(packet(), 2, sleep=sleep)
        self.assertFalse(result["full_refresh"])

    async def test_missing_identity_fails_closed(self):
        with self.assertRaises(ValueError):
            await checkpoint({"fcp1": {"f": {}}, "llm_prompt_text": "hi"}, 1)

    async def test_bad_response_number_fails(self):
        with self.assertRaises(ValueError):
            await checkpoint(packet(), 0)


if __name__ == "__main__":
    unittest.main()
