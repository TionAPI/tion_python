#!/usr/bin/env python3
import sys
from s3 import s3 as s3device

s3 = s3device()
s3.pair(sys.argv[1])
