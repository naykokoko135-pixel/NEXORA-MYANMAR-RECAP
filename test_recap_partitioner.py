import unittest

from recap_partitioner import RecapPartitionError, plan_three_part_srt


def stamp(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"


def sample_srt(total_seconds=2760):
    cues = []
    for index, start in enumerate(range(0, total_seconds, 60), 1):
        end = min(start + 60, total_seconds)
        cues.extend([
            str(index),
            f"{stamp(start)} --> {stamp(end)}",
            f"မြန်မာ narration cue {index}",
            "",
        ])
    return "\n".join(cues)


class RecapPartitionerTests(unittest.TestCase):
    def test_splits_46_minute_srt_into_three_15_to_20_minute_parts(self):
        parts = plan_three_part_srt(sample_srt())
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(900 <= part["duration_seconds"] <= 1200 for part in parts))
        self.assertAlmostEqual(sum(part["duration_seconds"] for part in parts), 2760)
        self.assertTrue(all(part["srt_text"].startswith("1\n00:00:") for part in parts))
        self.assertIn("မြန်မာ narration cue", "".join(part["srt_text"] for part in parts))

    def test_part_boundaries_do_not_duplicate_subtitle_cues(self):
        parts = plan_three_part_srt(sample_srt())
        all_cues = []
        for part in parts:
            for block in part["srt_text"].strip().split("\n\n"):
                lines = block.splitlines()
                all_cues.append(lines[2])
        self.assertEqual(len(all_cues), len(set(all_cues)))
        self.assertEqual(len(all_cues), 46)

    def test_rejects_duration_outside_longform_limits(self):
        with self.assertRaises(RecapPartitionError):
            plan_three_part_srt(sample_srt(2700))

    def test_rejects_sparse_srt_when_no_valid_part_boundaries_exist(self):
        srt = (
            "1\n00:00:00,000 --> 00:16:00,000\nPart one\n\n"
            "2\n00:16:00,000 --> 00:32:00,000\nPart two\n\n"
            "3\n00:32:00,000 --> 00:46:00,000\nPart three\n"
        )
        with self.assertRaises(RecapPartitionError):
            plan_three_part_srt(srt)


if __name__ == "__main__":
    unittest.main()
