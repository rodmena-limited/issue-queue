"""Assemble BASE_TEMPLATE from byte-preserved chunks."""

from issuedb.web._base_part1 import PART_1
from issuedb.web._base_part2 import PART_2
from issuedb.web._base_part3 import PART_3

BASE_TEMPLATE = PART_1 + PART_2 + PART_3
